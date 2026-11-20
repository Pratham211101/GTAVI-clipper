"""Direct upload and account connection helpers for YouTube Shorts and Instagram Reels."""

import json
import os
import threading
from pathlib import Path

from .common import ENV_DIR, Problem, read_json, write_json

YT_SECRET_FILE = ENV_DIR / "youtube_client_secret.json"
YT_TOKEN_FILE = ENV_DIR / "youtube_token.json"
IG_SESSION_FILE = ENV_DIR / "instagram_session.json"
IG_ACCOUNT_FILE = ENV_DIR / "instagram_account.json"

YT_SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]

_yt_lock = threading.Lock()
_ig_lock = threading.Lock()
_active_yt_flow = None

os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")
os.environ.setdefault("OAUTHLIB_RELAX_TOKEN_SCOPE", "1")


def _ensure_env_dir():
    ENV_DIR.mkdir(parents=True, exist_ok=True)


def _yt_credentials():
    if not YT_TOKEN_FILE.exists():
        return None
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    try:
        creds = Credentials.from_authorized_user_file(str(YT_TOKEN_FILE), YT_SCOPES)
    except Exception:
        return None
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            YT_TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
        except Exception:
            return None
    return creds if creds and creds.valid else None


def yt_status():
    """Return YouTube OAuth connection status and active channel name."""
    has_secret = YT_SECRET_FILE.exists()
    creds = _yt_credentials()
    if not creds:
        return {"connected": False, "channel": None, "channel_id": None, "has_secret": has_secret}
    try:
        from googleapiclient.discovery import build

        youtube = build("youtube", "v3", credentials=creds)
        resp = youtube.channels().list(part="snippet", mine=True).execute()
        items = resp.get("items") or []
        if items:
            snippet = items[0].get("snippet", {})
            return {
                "connected": True,
                "channel": snippet.get("title") or "YouTube Channel",
                "channel_id": items[0].get("id"),
                "has_secret": has_secret,
            }
        return {"connected": True, "channel": "Authorized Account", "channel_id": None, "has_secret": has_secret}
    except Exception as exc:
        return {"connected": False, "channel": None, "channel_id": None, "has_secret": has_secret, "error": str(exc)}


def yt_save_secret(client_id=None, client_secret=None, raw_json=None):
    """Save Google OAuth Desktop client credentials to ~/.streamclips/youtube_client_secret.json."""
    _ensure_env_dir()
    if raw_json:
        try:
            data = json.loads(raw_json) if isinstance(raw_json, str) else raw_json
        except ValueError as exc:
            raise Problem(f"Invalid client_secret JSON: {exc}") from exc
        if "installed" not in data and "web" not in data:
            raise Problem("JSON must contain an 'installed' or 'web' OAuth client object.")
    elif client_id and client_secret:
        data = {
            "installed": {
                "client_id": client_id.strip(),
                "client_secret": client_secret.strip(),
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                "redirect_uris": ["http://localhost"],
            }
        }
    else:
        raise Problem("Provide either raw client_secret.json or both client_id and client_secret.")
    write_json(YT_SECRET_FILE, data)
    return yt_status()


def yt_start_auth(redirect_uri: str) -> str:
    """Create a Google OAuth authorization URL without blocking on a local server."""
    if not YT_SECRET_FILE.exists():
        raise Problem("YouTube OAuth client secret not configured yet. Upload client_secret.json or enter Client ID & Secret first.")
    global _active_yt_flow
    with _yt_lock:
        from google_auth_oauthlib.flow import InstalledAppFlow

        os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
        os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"
        _ensure_env_dir()
        flow = InstalledAppFlow.from_client_secrets_file(
            str(YT_SECRET_FILE),
            scopes=YT_SCOPES,
            redirect_uri=redirect_uri,
        )
        auth_url, _ = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent",
        )
        _active_yt_flow = flow
        return auth_url


def yt_finish_auth(full_callback_url: str, redirect_uri: str, code: str = None):
    """Exchange the OAuth callback code for credentials and save youtube_token.json."""
    if not YT_SECRET_FILE.exists():
        raise Problem("YouTube OAuth client secret not found.")
    global _active_yt_flow
    with _yt_lock:
        from google_auth_oauthlib.flow import InstalledAppFlow

        os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
        os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"
        _ensure_env_dir()
        flow = _active_yt_flow
        if flow is None or flow.redirect_uri != redirect_uri:
            flow = InstalledAppFlow.from_client_secrets_file(
                str(YT_SECRET_FILE),
                scopes=YT_SCOPES,
                redirect_uri=redirect_uri,
            )
        if code:
            flow.fetch_token(code=code)
        else:
            flow.fetch_token(authorization_response=full_callback_url)
        YT_TOKEN_FILE.write_text(flow.credentials.to_json(), encoding="utf-8")
        _active_yt_flow = None
    return yt_status()


def yt_connect():
    """Run local browser OAuth flow and persist credentials (CLI helper)."""
    if not YT_SECRET_FILE.exists():
        raise Problem("YouTube OAuth client secret not configured yet. Upload client_secret.json or enter Client ID & Secret first.")
    with _yt_lock:
        from google_auth_oauthlib.flow import InstalledAppFlow

        _ensure_env_dir()
        flow = InstalledAppFlow.from_client_secrets_file(str(YT_SECRET_FILE), scopes=YT_SCOPES)
        creds = flow.run_local_server(port=0, open_browser=True)
        YT_TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
    return yt_status()


def yt_disconnect():
    """Remove saved YouTube OAuth token."""
    YT_TOKEN_FILE.unlink(missing_ok=True)
    return yt_status()


def yt_upload(video_path, title, description="", tags=None, privacy="public", publish_at=None):
    """Upload an MP4 video as a YouTube Short and return video ID and URL."""
    path = Path(video_path)
    if not path.exists():
        raise Problem(f"Video file not found: {path}")
    creds = _yt_credentials()
    if not creds:
        raise Problem("YouTube is not connected. Connect your YouTube account first.")

    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload

    clean_title = (title or path.stem).strip()[:100]
    desc = (description or "").strip()
    if "#shorts" not in clean_title.lower() and "#shorts" not in desc.lower():
        desc = (desc + "\n\n#Shorts").strip()
    clean_tags = [str(t).lstrip("#").strip() for t in (tags or []) if str(t).strip()][:15]
    if "shorts" not in [t.lower() for t in clean_tags]:
        clean_tags.append("Shorts")

    status_obj = {
        "privacyStatus": "private" if publish_at else (privacy if privacy in ("public", "unlisted", "private") else "public"),
        "selfDeclaredMadeForKids": False,
    }
    if publish_at:
        status_obj["publishAt"] = publish_at

    body = {
        "snippet": {
            "title": clean_title,
            "description": desc[:5000],
            "tags": clean_tags,
            "categoryId": "20",  # Gaming
        },
        "status": status_obj,
    }

    youtube = build("youtube", "v3", credentials=creds)
    media = MediaFileUpload(str(path), mimetype="video/mp4", chunksize=4 * 1024 * 1024, resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    response = None
    while response is None:
        _, response = request.next_chunk()
    video_id = response["id"]
    return {
        "id": video_id,
        "url": f"https://www.youtube.com/shorts/{video_id}",
        "privacy": body["status"]["privacyStatus"],
        "publish_at": publish_at,
    }


def ig_status():
    """Return Instagram session status."""
    meta = read_json(IG_ACCOUNT_FILE, {}) or {}
    connected = IG_SESSION_FILE.exists() and bool(meta.get("username"))
    return {
        "connected": connected,
        "username": meta.get("username") if connected else None,
    }


def _ig_client():
    from instagrapi import Client

    cl = Client()
    if IG_SESSION_FILE.exists():
        try:
            cl.load_settings(str(IG_SESSION_FILE), override_app_version=True)
            return cl
        except Exception:
            pass
    return cl


def ig_connect(username, password, verification_code=None):
    """Log into Instagram via instagrapi and persist the session."""
    if not username or not password:
        raise Problem("Instagram username and password are required.")
    with _ig_lock:
        _ensure_env_dir()
        cl = _ig_client()
        try:
            cl.login(username.strip(), password, verification_code=(verification_code or "").strip())
        except Exception as exc:
            msg = str(exc)
            low = msg.lower()
            if "two-factor" in low or "2fa" in low or "verification" in low:
                raise Problem(f"Instagram 2FA required: enter your verification code and try again. ({msg})") from exc
            if "out of date" in low or "upgrade your app" in low:
                raise Problem(
                    "Instagram blocked the mobile app login ('out of date'). "
                    "Use the 'Session ID Cookie' tab right above to connect instantly using your browser sessionid!"
                ) from exc
            raise Problem(f"Instagram login failed: {msg}") from exc
        cl.dump_settings(str(IG_SESSION_FILE))
        write_json(IG_ACCOUNT_FILE, {"username": username.strip()})
    return ig_status()


def ig_connect_session(session_id: str, username: str = None):
    """Connect Instagram using a browser `sessionid` cookie (bypasses mobile login version checks)."""
    import urllib.parse

    raw = urllib.parse.unquote((session_id or "").strip())
    if not raw:
        raise Problem("Instagram sessionid cookie is required.")
    with _ig_lock:
        _ensure_env_dir()
        cl = _ig_client()
        try:
            ok = cl.login_by_sessionid(raw)
            if not ok:
                raise Problem("Instagram rejected that sessionid cookie. Make sure you are logged in and copied the full value.")
            resolved_user = (username or "").strip()
            if not resolved_user:
                try:
                    info = cl.account_info()
                    resolved_user = getattr(info, "username", "") or ""
                except Exception:
                    resolved_user = ""
            resolved_user = resolved_user or "instagram_user"
        except Problem:
            raise
        except Exception as exc:
            raise Problem(f"Instagram sessionid login failed: {exc}") from exc
        cl.dump_settings(str(IG_SESSION_FILE))
        write_json(IG_ACCOUNT_FILE, {"username": resolved_user})
    return ig_status()


def ig_disconnect():
    """Clear stored Instagram session."""
    IG_SESSION_FILE.unlink(missing_ok=True)
    IG_ACCOUNT_FILE.unlink(missing_ok=True)
    return ig_status()


def ig_upload(video_path, caption=""):
    """Upload a vertical MP4 video as an Instagram Reel."""
    path = Path(video_path)
    if not path.exists():
        raise Problem(f"Video file not found: {path}")
    status = ig_status()
    if not status["connected"]:
        raise Problem("Instagram is not connected. Connect your Instagram account first.")

    with _ig_lock:
        import subprocess
        import tempfile

        cl = _ig_client()
        try:
            cl.get_timeline_feed()
        except Exception as exc:
            raise Problem(f"Instagram session expired or invalid. Please reconnect your account. ({exc})") from exc

        thumb_path = Path(tempfile.gettempdir()) / f"{path.stem}_ig_thumb.jpg"
        try:
            subprocess.run(
                ["ffmpeg", "-y", "-v", "error", "-nostdin", "-ss", "1.0", "-i", str(path),
                 "-frames:v", "1", "-q:v", "2", str(thumb_path)],
                check=False,
                capture_output=True,
            )
            if not thumb_path.exists():
                subprocess.run(
                    ["ffmpeg", "-y", "-v", "error", "-nostdin", "-i", str(path),
                     "-frames:v", "1", "-q:v", "2", str(thumb_path)],
                    check=False,
                    capture_output=True,
                )
            kwargs = {"thumbnail": thumb_path} if thumb_path.exists() else {}
            media = cl.clip_upload(path, caption or "", **kwargs)
        finally:
            thumb_path.unlink(missing_ok=True)

        cl.dump_settings(str(IG_SESSION_FILE))
        code = getattr(media, "code", None)
        pk = str(getattr(media, "pk", ""))
        url = f"https://www.instagram.com/reel/{code}/" if code else None
        return {"pk": pk, "code": code, "url": url}
