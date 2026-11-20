# Stream Clips AI Studio (Clipper + YouTube Shorts & Instagram Reels Uploader)

Turn long livestreams (YouTube, Twitch, Kick) into ready-to-post 9:16 vertical clips with automatic facecam stacking, title bars, word-by-word captions, and 1-click uploading/scheduling to **YouTube Shorts** and **Instagram Reels**.

---

## 1. Prerequisites

Install these on your computer first:

- **Python 3.9+**
- **FFmpeg & FFprobe**
- **Deno** (or Node.js) — required by `yt-dlp` for YouTube downloads

**Windows (PowerShell):**
```powershell
winget install Python.Python.3.12
winget install Gyan.FFmpeg
winget install DenoLand.Deno
```

**macOS:**
```bash
brew install ffmpeg deno
```

*(Open a new terminal after installing so `python`, `ffmpeg`, and `deno` are on your `PATH`.)*

---

## 2. One-Time Setup

From inside this folder, run:

```powershell
python scripts\streamclips.py setup
```
*(macOS/Linux: `python3 scripts/streamclips.py setup`)*

Wait until it prints **`READY`**. This creates a private Python environment in `~/.streamclips/venv`, installs all dependencies (`faster-whisper`, `fastapi`, `instagrapi`, `google-api-python-client`, `yt-dlp`, etc.), and downloads the speech and face-detection models.

### Optional: Enable NVIDIA GPU (CUDA) for Faster Whisper Transcription
If you have an **NVIDIA GPU** on Windows and want Whisper to run on CUDA cores instead of CPU:

```powershell
# If you have `uv` installed:
uv pip install --python "$HOME\.streamclips\venv\Scripts\python.exe" nvidia-cublas-cu12 nvidia-cudnn-cu12

# Or if using pip inside the venv:
& "$HOME\.streamclips\venv\Scripts\python.exe" -m pip install nvidia-cublas-cu12 nvidia-cudnn-cu12
```
*(If you don't have an NVIDIA GPU, it automatically falls back to CPU Whisper and your system's available video encoder.)*

---

## 3. Launch the React Studio Web App

The frontend (`app/dist`) is already pre-built, so you don't need `npm install` to run it. Start the Studio server with:

```powershell
python scripts\streamclips.py server --port 8765 --open
```

This opens **`http://localhost:8765`** in your browser where you can:
1. **Connect YouTube Shorts:**
   - Create a free Google Cloud project, enable **YouTube Data API v3**, create a **Desktop App** OAuth 2.0 Client ID, and add your Google account under **OAuth consent screen → Test users**.
   - Download `client_secret.json`, upload it in the **Connect YouTube** modal, and click **Authorize in Browser**.
2. **Connect Instagram Reels:**
   - Click **Connect Instagram** and use the **Session ID Cookie (Recommended)** tab (log into `instagram.com` in your browser → `F12` → **Application** → **Cookies** → copy `sessionid`), or sign in with Username & Password.
3. **1-Click Generate Clips:**
   - Enter any streamer name (e.g. `Kai Cenat`, `IShowSpeed`) or paste a stream URL, set topic & clip count, and click **1-Click Generate**.
4. **1-Click Upload / Drip Schedule:**
   - Post individual clips or batch upload/schedule all clips to YouTube Shorts (supports native YouTube `publishAt` cloud scheduling) and Instagram Reels (background drip queue while the server is running).

---

## 4. Command-Line Usage (Optional)

You can also run everything from the terminal or an AI coding CLI:

```powershell
# Find today's biggest streams for a topic
python scripts\streamclips.py find --topic "GTA 6"

# Clip a stream directly (uses smart hybrid picker + hardware encoding)
python scripts\streamclips.py clip "https://www.youtube.com/watch?v=..." --topic "GTA 6" --clips 3 --brain smart --fast

# Upload an existing clip or output folder
python scripts\streamclips.py upload "C:\Users\<you>\StreamClips\..." --to yt,insta
```

Clips and `POSTING.md` summaries are saved to `~/StreamClips/` (`C:\Users\<you>\StreamClips\`).
