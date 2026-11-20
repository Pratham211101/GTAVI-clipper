"""Local FastAPI studio backend for Stream Clips + YouTube/Instagram direct upload."""

import datetime
import hashlib
import mimetypes
import os
import re
import subprocess
import threading
import time
import urllib.parse
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI, HTTPException, Request, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import brains, discover, pipeline, settings, uploader
from .common import (
    DATA,
    ENV_DIR,
    Problem,
    add_log_listener,
    keywords_for,
    read_json,
    remove_log_listener,
    write_json,
)

JOBS_FILE = ENV_DIR / "jobs.json"
UPLOADS_FILE = ENV_DIR / "uploads.json"
AGENT_QUEUE_FILE = ENV_DIR / "agent_queue.json"
SCHEDULE_FILE = ENV_DIR / "schedule_queue.json"
DIST_DIR = Path(__file__).resolve().parent.parent.parent / "app" / "dist"

app = FastAPI(title="StreamClips AI Studio API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_jobs_lock = threading.Lock()
_jobs = read_json(JOBS_FILE, []) or []
# Mark any previously interrupted running jobs as failed on fresh start
for _j in _jobs:
    if _j.get("status") in ("running", "queued"):
        _j["status"] = "interrupted"

_schedule_lock = threading.Lock()
_schedule = read_json(SCHEDULE_FILE, []) or []
for _s in _schedule:
    if _s.get("status") == "uploading":
        _s["status"] = "scheduled"


def _save_schedule():
    ENV_DIR.mkdir(parents=True, exist_ok=True)
    write_json(SCHEDULE_FILE, _schedule[:100])


def _save_jobs():
    ENV_DIR.mkdir(parents=True, exist_ok=True)
    write_json(JOBS_FILE, _jobs[:30])


def _clip_id(path_str: str) -> str:
    return hashlib.sha1(str(Path(path_str).resolve()).encode("utf-8")).hexdigest()[:12]


def _gpu_info():
    gpu_name = None
    try:
        proc = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=3,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            gpu_name = proc.stdout.strip().splitlines()[0].strip()
    except Exception:
        pass
    return {
        "cuda_available": bool(gpu_name),
        "gpu_name": gpu_name or "CPU Mode",
        "whisper_device": "cuda (float16)" if gpu_name else "cpu",
        "encoder": "h264_nvenc" if gpu_name else "libx264",
    }


def _pretty_title_from_stem(stem: str) -> str:
    clean = re.sub(r"^\d+_", "", stem).replace("-", " ").strip()
    return clean.title() if clean else stem


def list_all_clips():
    """Scan C:\\Users\\<user>\\StreamClips for all generated vertical clips."""
    uploads_db = read_json(UPLOADS_FILE, {}) or {}
    clips = []
    if not DATA.exists():
        return clips

    for clips_json_path in sorted(DATA.rglob("clips.json"), reverse=True):
        folder = clips_json_path.parent
        if ".cache" in folder.parts:
            continue
        meta_doc = read_json(clips_json_path, {}) or {}
        source = meta_doc.get("source") or {}
        records = meta_doc.get("clips") or []
        by_file = {r.get("file"): r for r in records if isinstance(r, dict) and r.get("file")}

        # Infer date / topic / creator folder structure: DATA/<date>/<topic>/<creator__title>
        try:
            rel_parts = folder.relative_to(DATA).parts
        except ValueError:
            rel_parts = ()
        date_str = rel_parts[0] if len(rel_parts) >= 1 else ""
        topic_str = rel_parts[1].replace("-", " ").title() if len(rel_parts) >= 2 else (source.get("topic") or "")
        creator = source.get("name") or (rel_parts[2].split("__")[0].replace("-", " ").title() if len(rel_parts) >= 3 else "Creator")
        stream_title = source.get("title") or folder.name

        mp4_files = sorted(folder.glob("*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True)
        for mp4 in mp4_files:
            rec = by_file.get(mp4.name, {})
            cid = _clip_id(str(mp4))
            check_jpg = folder / "checks" / f"{mp4.stem}.jpg"
            stat = mp4.stat()
            tags = rec.get("hashtags") or []
            clips.append({
                "id": cid,
                "file": mp4.name,
                "path": str(mp4),
                "folder": str(folder),
                "video_url": f"/api/media?path={urllib.parse.quote(str(mp4))}",
                "check_url": f"/api/media?path={urllib.parse.quote(str(check_jpg))}" if check_jpg.exists() else None,
                "title": rec.get("title") or _pretty_title_from_stem(mp4.stem),
                "caption": rec.get("caption") or "",
                "hashtags": tags,
                "type": rec.get("type") or "clip",
                "score": rec.get("score") or 85,
                "why": rec.get("why") or "",
                "look": rec.get("look") or "stack",
                "start": rec.get("start"),
                "end": rec.get("end"),
                "seconds": rec.get("seconds") or 40,
                "size_mb": round(stat.st_size / 1e6, 1),
                "created_at": stat.st_mtime,
                "creator": creator,
                "stream_title": stream_title,
                "stream_url": source.get("url") or "",
                "topic": source.get("topic") or topic_str,
                "date": date_str,
                "uploads": uploads_db.get(cid) or {},
            })

    # Also catch any standalone mp4 folders without clips.json
    known_paths = {c["path"] for c in clips}
    for mp4 in sorted(DATA.rglob("*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True):
        if ".cache" in mp4.parts or str(mp4) in known_paths:
            continue
        folder = mp4.parent
        cid = _clip_id(str(mp4))
        check_jpg = folder / "checks" / f"{mp4.stem}.jpg"
        stat = mp4.stat()
        clips.append({
            "id": cid,
            "file": mp4.name,
            "path": str(mp4),
            "folder": str(folder),
            "video_url": f"/api/media?path={urllib.parse.quote(str(mp4))}",
            "check_url": f"/api/media?path={urllib.parse.quote(str(check_jpg))}" if check_jpg.exists() else None,
            "title": _pretty_title_from_stem(mp4.stem),
            "caption": "",
            "hashtags": [],
            "type": "clip",
            "score": 85,
            "why": "",
            "look": "stack",
            "start": None,
            "end": None,
            "seconds": 40,
            "size_mb": round(stat.st_size / 1e6, 1),
            "created_at": stat.st_mtime,
            "creator": folder.name,
            "stream_title": folder.name,
            "stream_url": "",
            "topic": "",
            "date": "",
            "uploads": uploads_db.get(cid) or {},
        })

    clips.sort(key=lambda c: c["created_at"], reverse=True)
    return clips


def _find_clip_by_id(clip_id: str):
    for c in list_all_clips():
        if c["id"] == clip_id:
            return c
    return None


def _record_upload(clip_id: str, platform: str, info: dict):
    uploads_db = read_json(UPLOADS_FILE, {}) or {}
    entry = uploads_db.get(clip_id, {})
    entry[platform] = {**info, "uploaded_at": datetime.datetime.now().isoformat()}
    uploads_db[clip_id] = entry
    ENV_DIR.mkdir(parents=True, exist_ok=True)
    write_json(UPLOADS_FILE, uploads_db)


class JobRequest(BaseModel):
    query: str
    topic: str = "GTA 6"
    clips: int = 3
    section: str = ""
    when: str = "week"
    brain: str = "smart"
    focus: str = ""
    cookies: str | None = None
    auto_upload_yt: bool = False
    auto_upload_ig: bool = False


class FindRequest(BaseModel):
    query: str = ""
    topic: str = "GTA 6"
    when: str = "week"
    count: int = 6


class ClipPatchRequest(BaseModel):
    id: str
    title: str | None = None
    caption: str | None = None
    hashtags: list[str] | None = None


class YouTubeSecretRequest(BaseModel):
    client_id: str | None = None
    client_secret: str | None = None
    raw_json: str | None = None


class InstagramConnectRequest(BaseModel):
    username: str
    password: str
    verification_code: str | None = None


class InstagramSessionRequest(BaseModel):
    session_id: str
    username: str | None = None


class UploadRequest(BaseModel):
    clip_id: str
    title: str | None = None
    caption: str | None = None
    hashtags: list[str] | None = None
    privacy: str = "public"


class ScheduleBatchRequest(BaseModel):
    clip_ids: list[str]
    platforms: list[str] = ["youtube", "instagram"]
    interval_minutes: int = 15
    start_delay_minutes: int = 0
    yt_native_schedule: bool = False
    skip_already_uploaded: bool = True
    privacy: str = "public"


def _execute_scheduled_item(item: dict):
    clip = _find_clip_by_id(item["clip_id"])
    if not clip:
        raise Problem(f"Clip not found: {item['clip_id']}")
    title = clip["title"]
    caption = clip["caption"] or ""
    tags = clip["hashtags"] or []
    desc = (caption + "\n" + " ".join(tags)).strip()
    results = {}
    errors = []

    for platform in item.get("platforms", []):
        try:
            if platform == "youtube":
                res = uploader.yt_upload(
                    clip["path"],
                    title,
                    desc,
                    tags,
                    privacy=item.get("privacy", "public"),
                    publish_at=item.get("yt_publish_at"),
                )
                _record_upload(clip["id"], "youtube", res)
                results["youtube"] = res
            elif platform == "instagram":
                full_ig = "\n\n".join(p for p in [title, caption, " ".join(tags)] if p).strip()
                res = uploader.ig_upload(clip["path"], full_ig)
                _record_upload(clip["id"], "instagram", res)
                results["instagram"] = res
        except Exception as exc:
            errors.append(f"{platform}: {exc}")

    return results, errors


def _scheduler_loop():
    while True:
        due_id = None
        now_ts = time.time()
        with _schedule_lock:
            pending = [s for s in _schedule if s.get("status") == "scheduled" and s.get("scheduled_ts", 0) <= now_ts]
            if pending:
                pending.sort(key=lambda s: s.get("scheduled_ts", 0))
                target = pending[0]
                target["status"] = "uploading"
                target["started_at"] = datetime.datetime.now().isoformat()
                due_id = target["id"]
                _save_schedule()

        if due_id:
            with _schedule_lock:
                item = next((s for s in _schedule if s["id"] == due_id), None)
                item_copy = dict(item) if item else None
            if item_copy:
                try:
                    results, errors = _execute_scheduled_item(item_copy)
                    with _schedule_lock:
                        item = next((s for s in _schedule if s["id"] == due_id), None)
                        if item:
                            item["results"] = results
                            item["finished_at"] = datetime.datetime.now().isoformat()
                            if errors and not results:
                                item["status"] = "failed"
                                item["error"] = " | ".join(errors)
                            elif errors:
                                item["status"] = "completed"
                                item["error"] = "Partial: " + " | ".join(errors)
                            else:
                                item["status"] = "completed"
                            _save_schedule()
                except Exception as exc:
                    with _schedule_lock:
                        item = next((s for s in _schedule if s["id"] == due_id), None)
                        if item:
                            item["status"] = "failed"
                            item["error"] = str(exc)
                            item["finished_at"] = datetime.datetime.now().isoformat()
                            _save_schedule()
        time.sleep(5)


_scheduler_thread = threading.Thread(target=_scheduler_loop, daemon=True)
_scheduler_thread.start()


def _run_job(job_id: str):
    with _jobs_lock:
        job = next((j for j in _jobs if j["id"] == job_id), None)
        if not job:
            return
        job["status"] = "running"
        job["started_at"] = datetime.datetime.now().isoformat()
        _save_jobs()

    req = job["params"]
    target_thread = threading.get_ident()

    def log_cb(line, kind):
        if threading.get_ident() != target_thread:
            return
        with _jobs_lock:
            job["logs"].append({"line": line, "kind": kind})
            if len(job["logs"]) > 250:
                job["logs"] = job["logs"][-250:]
            # Update current step hint
            low = line.lower()
            if "searching" in low or "looking" in low:
                job["step"] = "Finding stream"
            elif "downloading the audio" in low or "reusing downloaded audio" in low:
                job["step"] = "Audio ready"
            elif "listening" in low or "heard " in low:
                job["step"] = "CUDA Whisper listening"
            elif "smart hybrid" in low or "picked " in low:
                job["step"] = "Picking viral moments"
            elif "clip " in low or "saved " in low:
                job["step"] = "NVENC rendering clips"

    def add_local_log(msg, kind="info"):
        with _jobs_lock:
            job["logs"].append({"line": msg, "kind": kind})

    add_log_listener(log_cb)
    try:
        query = (req.get("query") or "").strip()
        topic = (req.get("topic") or "GTA 6").strip()
        when = req.get("when") or "week"
        cfg = settings.load({
            "search_when": when,
            "clips": int(req.get("clips") or 3),
        })
        words = keywords_for(topic, None)

        if query.startswith("http://") or query.startswith("https://"):
            urls = [query]
            add_local_log(f"Using direct stream URL: {query}", "info")
        else:
            search_q = f"{query} {topic} stream".strip() if query else f"{topic} stream"
            add_local_log(f"Searching YouTube for '{search_q}' ({when})...", "step")
            found = discover.find(topic, words, cfg, count=5, search=search_q, cookies=req.get("cookies"))
            if not found and when == "today":
                cfg["search_when"] = "week"
                found = discover.find(topic, words, cfg, count=5, search=search_q, cookies=req.get("cookies"))
            if not found and query:
                # Try broader search without topic constraint
                found = discover.find(None, [], cfg, count=5, search=f"{query} {topic}".strip(), cookies=req.get("cookies"))
            if not found:
                raise Problem(f"No stream found for '{query}' ({topic}). Try pasting the YouTube stream URL directly.")
            best_stream = found[0]
            urls = [best_stream["url"]]
            add_local_log(f"Found stream: {best_stream['name']} - {best_stream['title']} ({best_stream['url']})", "good")

        brain_mode = req.get("brain") or "smart"
        if brain_mode not in ("smart", "agent", "auto"):
            brain_mode = "smart"

        opts = SimpleNamespace(
            cookies=req.get("cookies"),
            section=(req.get("section") or "").strip() or None,
            new_only=False,
            topic=topic,
            focus=(req.get("focus") or "").strip() or None,
            brain_resolved=brains.choose(brain_mode),
            model=None,
            repick=False,
            fast=True,
            cam_box=None,
            keep_audio=True,
        )

        result = pipeline.process(urls[0], opts, cfg)
        made_clips = result.get("clips") or []
        outdir = Path(result["outdir"])
        created_ids = [_clip_id(str(outdir / c["file"])) for c in made_clips]

        # Optional auto-upload
        if req.get("auto_upload_yt") or req.get("auto_upload_ig"):
            with _jobs_lock:
                job["step"] = "Uploading clips"
            for cid in created_ids:
                clip_obj = _find_clip_by_id(cid)
                if not clip_obj:
                    continue
                full_desc = (clip_obj["caption"] + "\n" + " ".join(clip_obj["hashtags"])).strip()
                if req.get("auto_upload_yt"):
                    try:
                        add_local_log(f"Uploading {clip_obj['file']} to YouTube Shorts...", "step")
                        res_yt = uploader.yt_upload(clip_obj["path"], clip_obj["title"], full_desc, clip_obj["hashtags"])
                        _record_upload(cid, "youtube", res_yt)
                        add_local_log(f"YouTube Short live: {res_yt['url']}", "good")
                    except Exception as u_exc:
                        add_local_log(f"YouTube upload skipped/failed: {u_exc}", "warn")
                if req.get("auto_upload_ig"):
                    try:
                        add_local_log(f"Uploading {clip_obj['file']} to Instagram Reels...", "step")
                        res_ig = uploader.ig_upload(clip_obj["path"], f"{clip_obj['title']}\n\n{full_desc}")
                        _record_upload(cid, "instagram", res_ig)
                        add_local_log(f"Instagram Reel live: {res_ig.get('url') or res_ig.get('pk')}", "good")
                    except Exception as u_exc:
                        add_local_log(f"Instagram upload skipped/failed: {u_exc}", "warn")

        with _jobs_lock:
            job["status"] = "completed"
            job["step"] = f"Done ({len(made_clips)} clips)"
            job["result_clips"] = created_ids
            job["outdir"] = str(outdir)
            job["finished_at"] = datetime.datetime.now().isoformat()
            _save_jobs()

    except brains.NeedAgent as need_more:
        waiting_list = [{"prompt": str(q), "answer": str(a)} for q, a in need_more.waiting]
        queue_doc = read_json(AGENT_QUEUE_FILE, []) or []
        queue_doc.append({
            "job_id": job_id,
            "query": req.get("query"),
            "topic": req.get("topic"),
            "waiting": waiting_list,
            "created_at": datetime.datetime.now().isoformat(),
        })
        write_json(AGENT_QUEUE_FILE, queue_doc)
        add_local_log(f"Waiting for Antigravity Agent to pick moments ({len(waiting_list)} prompt part(s) queued).", "warn")
        with _jobs_lock:
            job["status"] = "waiting_for_agent"
            job["step"] = "Waiting for Agent Picks"
            job["waiting_prompts"] = waiting_list
            _save_jobs()

    except Exception as exc:
        add_local_log(f"Job failed: {exc}", "bad")
        with _jobs_lock:
            job["status"] = "failed"
            job["step"] = "Failed"
            job["error"] = str(exc)
            job["finished_at"] = datetime.datetime.now().isoformat()
            _save_jobs()
    finally:
        remove_log_listener(log_cb)


@app.get("/api/status")
def api_status():
    return {
        "gpu": _gpu_info(),
        "youtube": uploader.yt_status(),
        "instagram": uploader.ig_status(),
        "data_dir": str(DATA),
        "agent_queue_count": len(read_json(AGENT_QUEUE_FILE, []) or []),
    }


@app.get("/api/clips")
def api_clips():
    return {"clips": list_all_clips()}


@app.patch("/api/clips")
def api_patch_clip(req: ClipPatchRequest):
    clip = _find_clip_by_id(req.id)
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")
    folder = Path(clip["folder"])
    clips_json = folder / "clips.json"
    doc = read_json(clips_json, {}) or {}
    records = doc.get("clips") or []
    updated = False
    for r in records:
        if r.get("file") == clip["file"]:
            if req.title is not None:
                r["title"] = req.title
            if req.caption is not None:
                r["caption"] = req.caption
            if req.hashtags is not None:
                r["hashtags"] = [t if t.startswith("#") else f"#{t}" for t in req.hashtags if t.strip()]
            updated = True
            break
    if not updated:
        records.append({
            "file": clip["file"],
            "title": req.title if req.title is not None else clip["title"],
            "caption": req.caption if req.caption is not None else clip["caption"],
            "hashtags": req.hashtags if req.hashtags is not None else clip["hashtags"],
            "type": clip["type"],
            "score": clip["score"],
            "why": clip["why"],
            "look": clip["look"],
            "seconds": clip["seconds"],
        })
        doc["clips"] = records
    write_json(clips_json, doc)
    return {"ok": True, "clip": _find_clip_by_id(req.id)}


@app.get("/api/media")
def api_media(path: str, request: Request):
    file_path = Path(path).resolve()
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Media file not found")
    # Restrict access strictly inside DATA output folder
    try:
        file_path.relative_to(DATA.resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied")

    media_type, _ = mimetypes.guess_type(str(file_path))
    media_type = media_type or "application/octet-stream"
    file_size = file_path.stat().st_size
    range_header = request.headers.get("range")
    if not range_header:
        return FileResponse(str(file_path), media_type=media_type)

    m = re.match(r"bytes=(\d+)-(\d*)", range_header)
    if not m:
        return FileResponse(str(file_path), media_type=media_type)
    start = int(m.group(1))
    end = int(m.group(2)) if m.group(2) else file_size - 1
    end = min(end, file_size - 1)
    if start > end or start >= file_size:
        return Response(status_code=416)

    chunk_size = end - start + 1

    def iterfile():
        with open(file_path, "rb") as f:
            f.seek(start)
            remaining = chunk_size
            while remaining > 0:
                chunk = f.read(min(1024 * 256, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
                yield chunk

    headers = {
        "Content-Range": f"bytes {start}-{end}/{file_size}",
        "Accept-Ranges": "bytes",
        "Content-Length": str(chunk_size),
    }
    return StreamingResponse(iterfile(), status_code=206, headers=headers, media_type=media_type)


@app.post("/api/find")
def api_find(req: FindRequest):
    cfg = settings.load({"search_when": req.when})
    words = keywords_for(req.topic, None)
    search_q = f"{req.query.strip()} {req.topic.strip()} stream".strip()
    try:
        streams = discover.find(req.topic, words, cfg, count=req.count, search=search_q)
        if not streams and req.query.strip():
            streams = discover.find(None, [], cfg, count=req.count, search=f"{req.query.strip()} {req.topic.strip()}".strip())
        return {"streams": streams}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/api/jobs")
def api_get_jobs():
    with _jobs_lock:
        return {"jobs": list(_jobs)}


@app.post("/api/jobs")
def api_create_job(req: JobRequest):
    job_id = hashlib.sha1(f"{time.time()}_{req.query}".encode()).hexdigest()[:10]
    job = {
        "id": job_id,
        "params": req.model_dump(),
        "status": "queued",
        "step": "Starting",
        "logs": [],
        "result_clips": [],
        "created_at": datetime.datetime.now().isoformat(),
    }
    with _jobs_lock:
        _jobs.insert(0, job)
        _save_jobs()
    t = threading.Thread(target=_run_job, args=(job_id,), daemon=True)
    t.start()
    return {"job": job}


@app.post("/api/jobs/{job_id}/resume")
def api_resume_job(job_id: str):
    with _jobs_lock:
        job = next((j for j in _jobs if j["id"] == job_id), None)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        job["status"] = "queued"
        job["step"] = "Resuming"
        _save_jobs()
    t = threading.Thread(target=_run_job, args=(job_id,), daemon=True)
    t.start()
    return {"job": job}


@app.get("/api/auth/status")
def api_auth_status():
    return {"youtube": uploader.yt_status(), "instagram": uploader.ig_status()}


@app.post("/api/auth/youtube/secret")
async def api_yt_secret(req: YouTubeSecretRequest):
    try:
        status = uploader.yt_save_secret(req.client_id, req.client_secret, req.raw_json)
        return {"ok": True, "youtube": status}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/auth/youtube/secret/file")
async def api_yt_secret_file(file: UploadFile = File(...)):
    try:
        content = (await file.read()).decode("utf-8")
        status = uploader.yt_save_secret(raw_json=content)
        return {"ok": True, "youtube": status}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


def _yt_redirect_uri(request: Request) -> str:
    port = request.url.port or 8765
    return f"http://localhost:{port}/api/auth/youtube/callback"


@app.post("/api/auth/youtube/connect")
def api_yt_connect(request: Request):
    try:
        redirect_uri = _yt_redirect_uri(request)
        auth_url = uploader.yt_start_auth(redirect_uri)
        return {"ok": True, "auth_url": auth_url, "redirect_uri": redirect_uri}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/api/auth/youtube/callback")
def api_yt_callback(request: Request, code: str = None, error: str = None):
    if error:
        return HTMLResponse(
            f"<html><body style='font-family:sans-serif;background:#0b0d13;color:#fecaca;padding:40px'>"
            f"<h2>YouTube Authorization Failed</h2><p>{error}</p></body></html>",
            status_code=400,
        )
    if not code:
        return HTMLResponse(
            "<html><body style='font-family:sans-serif;background:#0b0d13;color:#fecaca;padding:40px'>"
            "<h2>Missing authorization code</h2></body></html>",
            status_code=400,
        )
    try:
        redirect_uri = _yt_redirect_uri(request)
        st = uploader.yt_finish_auth(str(request.url), redirect_uri, code=code)
        ch = st.get("channel") or "YouTube"
        return HTMLResponse(
            f"<html><body style='font-family:sans-serif;background:#0b0d13;color:#a7f3d0;padding:40px;text-align:center'>"
            f"<h2>YouTube Connected: {ch}</h2>"
            f"<p>You can close this window and return to StreamClips Studio.</p>"
            f"<script>setTimeout(() => window.close(), 1200);</script>"
            f"</body></html>"
        )
    except Exception as exc:
        return HTMLResponse(
            f"<html><body style='font-family:sans-serif;background:#0b0d13;color:#fecaca;padding:40px'>"
            f"<h2>Authorization Error</h2><p>{exc}</p></body></html>",
            status_code=400,
        )


@app.post("/api/auth/youtube/disconnect")
def api_yt_disconnect():
    return {"ok": True, "youtube": uploader.yt_disconnect()}


@app.post("/api/auth/instagram/connect")
def api_ig_connect(req: InstagramConnectRequest):
    try:
        status = uploader.ig_connect(req.username, req.password, req.verification_code)
        return {"ok": True, "instagram": status}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/auth/instagram/session")
def api_ig_session(req: InstagramSessionRequest):
    try:
        status = uploader.ig_connect_session(req.session_id, req.username)
        return {"ok": True, "instagram": status}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/auth/instagram/disconnect")
def api_ig_disconnect():
    return {"ok": True, "instagram": uploader.ig_disconnect()}


@app.post("/api/upload/youtube")
def api_upload_youtube(req: UploadRequest):
    clip = _find_clip_by_id(req.clip_id)
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")
    title = req.title or clip["title"]
    caption = req.caption if req.caption is not None else clip["caption"]
    tags = req.hashtags if req.hashtags is not None else clip["hashtags"]
    desc = (caption + "\n" + " ".join(tags)).strip()
    try:
        res = uploader.yt_upload(clip["path"], title, desc, tags, privacy=req.privacy)
        _record_upload(clip["id"], "youtube", res)
        return {"ok": True, "result": res, "clip": _find_clip_by_id(clip["id"])}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/upload/instagram")
def api_upload_instagram(req: UploadRequest):
    clip = _find_clip_by_id(req.clip_id)
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")
    title = req.title or clip["title"]
    caption = req.caption if req.caption is not None else clip["caption"]
    tags = req.hashtags if req.hashtags is not None else clip["hashtags"]
    full_caption = "\n\n".join(p for p in [title, caption, " ".join(tags)] if p).strip()
    try:
        res = uploader.ig_upload(clip["path"], full_caption)
        _record_upload(clip["id"], "instagram", res)
        return {"ok": True, "result": res, "clip": _find_clip_by_id(clip["id"])}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/api/schedule")
def api_get_schedule():
    with _schedule_lock:
        return {"schedule": list(_schedule)}


@app.post("/api/schedule")
def api_create_schedule(req: ScheduleBatchRequest):
    valid_platforms = [p for p in req.platforms if p in ("youtube", "instagram")]
    if not valid_platforms:
        raise HTTPException(status_code=400, detail="Select at least one platform (youtube or instagram)")
    interval_sec = max(0, int(req.interval_minutes)) * 60
    all_clips = {c["id"]: c for c in list_all_clips()}

    with _schedule_lock:
        now = time.time()
        if len(req.clip_ids) == 1 and req.start_delay_minutes == -1:
            pending_times = [s["scheduled_ts"] for s in _schedule if s.get("status") == "scheduled"]
            base_ts = (max(pending_times) if pending_times else now) + max(60, interval_sec)
        else:
            base_ts = now + max(0, int(req.start_delay_minutes)) * 60

        added = []
        slot_idx = 0
        for cid in req.clip_ids:
            clip = all_clips.get(cid)
            if not clip:
                continue
            target_platforms = list(valid_platforms)
            if req.skip_already_uploaded:
                existing_uploads = clip.get("uploads") or {}
                target_platforms = [p for p in target_platforms if p not in existing_uploads]
            if not target_platforms:
                continue

            slot_ts = base_ts + slot_idx * interval_sec
            slot_iso = datetime.datetime.fromtimestamp(slot_ts).isoformat()

            if req.yt_native_schedule and "youtube" in target_platforms and slot_ts > now + 90:
                yt_pub_iso = datetime.datetime.fromtimestamp(slot_ts, tz=datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                yt_id = hashlib.sha1(f"{time.time()}_{cid}_yt_{slot_idx}".encode()).hexdigest()[:10]
                yt_item = {
                    "id": yt_id,
                    "clip_id": cid,
                    "clip_title": clip["title"],
                    "creator": clip["creator"],
                    "platforms": ["youtube"],
                    "scheduled_ts": now + slot_idx * 5,
                    "scheduled_at": datetime.datetime.fromtimestamp(now + slot_idx * 5).isoformat(),
                    "yt_publish_at": yt_pub_iso,
                    "publish_display_at": slot_iso,
                    "privacy": req.privacy,
                    "status": "scheduled",
                    "results": {},
                }
                _schedule.append(yt_item)
                added.append(yt_item)

                other_platforms = [p for p in target_platforms if p != "youtube"]
                if other_platforms:
                    ig_id = hashlib.sha1(f"{time.time()}_{cid}_ig_{slot_idx}".encode()).hexdigest()[:10]
                    ig_item = {
                        "id": ig_id,
                        "clip_id": cid,
                        "clip_title": clip["title"],
                        "creator": clip["creator"],
                        "platforms": other_platforms,
                        "scheduled_ts": slot_ts,
                        "scheduled_at": slot_iso,
                        "yt_publish_at": None,
                        "publish_display_at": slot_iso,
                        "privacy": req.privacy,
                        "status": "scheduled",
                        "results": {},
                    }
                    _schedule.append(ig_item)
                    added.append(ig_item)
            else:
                sid = hashlib.sha1(f"{time.time()}_{cid}_{slot_idx}".encode()).hexdigest()[:10]
                item = {
                    "id": sid,
                    "clip_id": cid,
                    "clip_title": clip["title"],
                    "creator": clip["creator"],
                    "platforms": target_platforms,
                    "scheduled_ts": slot_ts,
                    "scheduled_at": slot_iso,
                    "yt_publish_at": None,
                    "publish_display_at": slot_iso,
                    "privacy": req.privacy,
                    "status": "scheduled",
                    "results": {},
                }
                _schedule.append(item)
                added.append(item)

            slot_idx += 1

        _schedule.sort(key=lambda s: s.get("scheduled_ts", 0))
        _save_schedule()
        return {"ok": True, "added": len(added), "schedule": list(_schedule)}


@app.delete("/api/schedule/{sched_id}")
def api_delete_schedule(sched_id: str):
    with _schedule_lock:
        before = len(_schedule)
        _schedule[:] = [s for s in _schedule if s.get("id") != sched_id]
        _save_schedule()
        return {"ok": len(_schedule) < before, "schedule": list(_schedule)}


@app.post("/api/schedule/clear")
def api_clear_schedule():
    with _schedule_lock:
        _schedule[:] = [s for s in _schedule if s.get("status") in ("scheduled", "uploading")]
        _save_schedule()
        return {"ok": True, "schedule": list(_schedule)}


# Serve React SPA if built
if DIST_DIR.exists():
    assets_dir = DIST_DIR / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    @app.get("/{full_path:path}")
    def serve_spa(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="API endpoint not found")
        target = DIST_DIR / full_path
        if full_path and target.exists() and target.is_file():
            return FileResponse(str(target))
        return FileResponse(str(DIST_DIR / "index.html"))


def start_server(port: int = 8765, open_browser: bool = False):
    import uvicorn
    import webbrowser

    if open_browser:
        threading.Timer(1.2, lambda: webbrowser.open(f"http://localhost:{port}")).start()
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")
