# 🎬 AI YouTube Video Generator

An AI-powered tool that generates short videos from a topic:
- Script written by Google Gemini
- Voiceover via gTTS / ElevenLabs / pyttsx3
- Stock footage from Pexels
- Video assembled with MoviePy

Runs as a FastAPI service with a built-in web UI, plus a one-shot CLI script.

## 🚀 Features
- Generate a script from a topic
- Convert the script to voice
- Fetch matching stock video clips
- Render everything into a video, trackable via a job status API
- Minimal web UI to kick off a job and download the result

## 🛠 Tech Stack
- Python, FastAPI
- Google Gemini (script generation)
- gTTS / ElevenLabs / pyttsx3 (text-to-speech)
- Pexels API (stock footage)
- MoviePy (video rendering, requires ffmpeg)

## 🔐 Environment Variables

Copy `.env.example` to `.env` and fill in:

| Variable | Required | Notes |
|---|---|---|
| `GOOGLE_API_KEY` | yes | Gemini API key, used for script generation |
| `PEXELS_API_KEY` | yes | Used to fetch stock footage |
| `TTS_ENGINE` | no | `gtts` (default recommendation), `pyttsx3`, or `elevenlabs` |
| `ELEVENLABS_API_KEY` | only if `TTS_ENGINE=elevenlabs` | |
| `B2_KEY_ID`, `B2_APPLICATION_KEY`, `B2_BUCKET_NAME`, `B2_ENDPOINT` | no | Backblaze B2 credentials — see [Persistent video storage](#-persistent-video-storage-backblaze-b2-optional) below |

## ▶️ Run locally

```bash
pip install -r requirements.txt
uvicorn app.api:app --reload
```

Open http://127.0.0.1:8000 for the web UI, or http://127.0.0.1:8000/docs for the API.

One-shot CLI version (no API, generates a video for a single topic and exits):

```bash
python -m app.main
```

## 📡 API

- `POST /generate?topic=...` — starts a generation job in the background, returns `{ job_id, status_url }`
- `GET /status/{job_id}` — poll job status (`queued` → `generating_script` → `generating_audio` → `fetching_videos` → `rendering_video` → `done`/`failed`)
- `GET /download/{job_id}` — download the finished video once status is `done`
- `GET /video_by_topic?topic=...` — search Pexels stock footage directly, without running the full pipeline
- `GET /health` — health check

Job state is kept in a local SQLite file (`assets/jobs.db`), so it survives process restarts and is shared correctly across worker processes — but it still lives on local disk, so a full redeploy on an ephemeral-disk host resets it. Fine for a single-instance demo, not a substitute for a real queue/DB under sustained load.

## 💾 Persistent video storage (Backblaze B2, optional)

By default, finished videos are written to local disk (`assets/videos/`). On free hosting tiers that disk is ephemeral — it's wiped on every redeploy or restart — so a video generated right before a restart can become unreachable. Setting the four `B2_*` env vars turns on an alternate path: the finished video is uploaded to a Backblaze B2 bucket and the local copy is deleted, and `/download/{job_id}` redirects to a fresh temporary signed link (valid 24h from the request, regenerated every time) instead of serving the local file. No credit card needed to sign up.

Setup:
1. Create a free account at [backblaze.com](https://www.backblaze.com) and create a bucket (private is fine — the app never needs it to be public, since it hands out short-lived signed links).
2. Create an **Application Key** scoped to that bucket (B2 dashboard → App Keys).
3. On the bucket's details page, copy its S3-compatible endpoint (e.g. `https://s3.us-west-004.backblazeb2.com`).
4. Set `B2_KEY_ID`, `B2_APPLICATION_KEY`, `B2_BUCKET_NAME`, `B2_ENDPOINT` in `.env` (local) or the Render dashboard (deployed).

Leave these unset and the app behaves exactly as before, serving from local disk.

## 🚀 Deploy (free)

The app is a single Docker image (`Dockerfile` in the repo root) — [Render](https://render.com) has the simplest free tier for this shape of app (Docker web service, no credit card required).

1. Push this repo to GitHub.
2. On Render, **New → Blueprint**, point it at the repo — it will pick up `render.yaml`. (Or **New → Web Service** manually, environment: Docker.)
3. Set the required env vars in the Render dashboard (`GOOGLE_API_KEY`, `PEXELS_API_KEY` are marked `sync: false` in `render.yaml` so Render prompts for them instead of storing them in git).
4. Deploy. Render builds the Dockerfile (installs ffmpeg + espeak-ng for TTS) and runs `uvicorn` bound to `$PORT` automatically.

Free-tier caveats worth knowing:
- The instance spins down after 15 minutes idle and cold-starts on the next request — the first hit after idle will be slow.
- Disk is ephemeral: generated videos live only as long as the container instance does, unless you set up [Backblaze B2 storage](#-persistent-video-storage-backblaze-b2-optional) (recommended for anything beyond quick local testing).
- `TTS_ENGINE=gtts` is set by default in `render.yaml` since it needs no native library, only outbound internet — `pyttsx3` also works in the container (espeak-ng is installed) if you'd rather avoid the Google TTS dependency.

Render's free tier is thin for this workload (512 MB RAM, 0.1 CPU) — moviepy/ffmpeg rendering can be slow or OOM on anything beyond short, low-res clips. See [Higher-compute free alternatives](#-higher-compute-free-alternatives) below if you hit that ceiling.

## 🖥️ Higher-compute free alternatives

If Render's 512 MB/0.1 CPU is too tight, two options give meaningfully more free compute for the rendering step (current as of late 2026 — [Fly.io](https://fly.io) and [Hugging Face Spaces](https://huggingface.co/spaces) both dropped their free compute tiers this year, so they're no longer options here):

- **[Oracle Cloud "Always Free"](https://www.oracle.com/cloud/free/)** — an actual VM (Ampere A1, ARM), 2–4 OCPU / 12–24 GB RAM depending on account type, no time limit, no request-based throttling. The most raw compute of any free option by far. Trade-off: it's a real VM, not a PaaS — you `docker run` this image yourself and manage the box (firewall, TLS, restarts) instead of `git push`-to-deploy. Needs a card on file for identity verification (not charged on the free tier); Ampere A1 capacity can be briefly unavailable in some regions at signup.
- **[Google Cloud Run](https://cloud.google.com/run)** — serverless containers, 180,000 vCPU-seconds + 360,000 GiB-seconds + 2M requests free per month, and scales to zero (idle time is free, unlike Render's flat instance-hours). You can configure well beyond Render's ceiling per instance (multiple vCPUs, several GB RAM), so a lot of renders fit in the free budget. Needs a GCP billing account (card required, not charged within free tier). Important for this app specifically: Cloud Run only allocates CPU to a request by default, and our `/generate` returns immediately while rendering continues in a background task — that background work needs "CPU always allocated" turned on for the service (still free-tier eligible), or the render step restructured as a Cloud Run **Job** instead of a Service.

Neither is pushed-button like the Render blueprint here; both need some setup specific to the platform.

## Output Video

# Sample output (Topic - Dangerous power of AI)
https://www.youtube.com/watch?v=SOeBVRSr4Bo
