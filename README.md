# AINN Stack
### AI-Powered 24/7 Live Broadcast Framework

Spin up your own autonomous live news channel streaming to Twitch, YouTube,
and any RTMP target — fully local, no cloud required.

RSS Feeds → LLM Script → TTS Audio → Video Render → RTMP Out
                                           ↓
                                 Twitch / YouTube / Owncast

## What it does
- RSS monitoring with category/priority routing
- Story dedup (GUID-based)
- Script generation plug-in point (use any LLM)
- Local TTS (Piper) + video rendering (FFmpeg)
- RTMP streaming to multiple targets

## Quickstart
1) Install dependencies:
- Python 3.10+
- ffmpeg
- Piper TTS
- (Optional) Ollama for local LLM

2) Setup:
    python3 -m venv .venv && source .venv/bin/activate
    pip install -r requirements.txt
    cp config.example.yaml config.yaml

3) Run:
    python main.py

## License
Licensed under the AINN Commercial Source License (ACSL) 1.0.
Non-commercial use is allowed. Commercial use requires a paid license.
See LICENSE for details.
