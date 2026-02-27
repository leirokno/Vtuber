# AINN Stack
### AI-Powered 24/7 Live Broadcast Framework

Spin up your own autonomous live news channel streaming to Twitch, YouTube,
and any RTMP target — fully local, no cloud required.

    RSS Feeds → LLM Script → TTS Audio → Video Render → RTMP Out
                                                       ↓
                                             Twitch / YouTube / Owncast

---

## What it does

- Monitors 33+ RSS feeds across categories (news, markets, tech, incidents, science, crypto)
- Detects new stories by GUID with persistent dedup — never replays the same story
- Generates anchor narration scripts via your local LLM (Ollama / OpenAI / Anthropic)
- Synthesises speech with Piper TTS — fully offline, multiple voice models included
- Renders broadcast video with lower-thirds, news ticker, and story imagery
- Streams 24/7 to multiple RTMP targets simultaneously (Twitch + YouTube + Owncast)
- Runs on consumer hardware — tested on a single Linux box with a mid-range GPU

---

## Quickstart

### 1. Requirements

- Linux (native or WSL2)
- Python 3.10+
- FFmpeg:       sudo apt install ffmpeg
- Ollama:       curl -fsSL https://ollama.ai/install.sh | sh
- Piper TTS:    https://github.com/rhasspy/piper/releases

### 2. Install

    git clone https://github.com/YOUR_USERNAME/ainn-stack
    cd ainn-stack
    python3 -m venv .venv && source .venv/bin/activate
    pip install -r requirements.txt

### 3. Download a TTS voice

    mkdir -p models/piper
    wget -P models/piper \
      https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx
    wget -P models/piper \
      https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json

### 4. Configure

    cp config.example.yaml config.yaml
    # Edit config.yaml:
    #   - Add your RSS feeds
    #   - Set your RTMP stream keys (Twitch / YouTube / Owncast)
    #   - Set your Ollama model name

### 5. Start your LLM

    ollama pull llama3
    ollama serve

### 6. Launch

    source .venv/bin/activate
    python main.py

---

## Architecture

    main.py
      └── BroadcastPipeline
            ├── RSSMonitor          — feed polling, GUID dedup, category/priority routing
            ├── AnchorCyclerBase    — STUB: plug in your LLM persona engine here
            ├── MemoryRingBase      — STUB: plug in your semantic dedup layer here
            ├── LocalTTS            — Piper TTS synthesis
            ├── ImageGenerator      — story backdrop generation
            ├── VisualStack         — lower-thirds + ticker rendering
            └── VideoLoop           — FFmpeg encode + RTMP push

### Plug-in points

The framework ships with two stub classes you replace with your own implementations.

AnchorCyclerBase in broadcast_pipeline.py:

    def generate_script(self, story: dict) -> str:
        # Call your LLM here.
        # story keys: title, summary, link, category, source
        ...

MemoryRingBase in broadcast_pipeline.py:

    def is_duplicate(self, guid, title) -> (bool, str): ...
    def mark_seen(self, guid, title): ...

---

## Feed categories and priority system

| Priority | Categories       | Behaviour                    |
|----------|-----------------|------------------------------|
| 1        | core, incidents  | Always jumps the queue       |
| 2        | markets, tech    | Standard rotation            |
| 3        | science, crypto, dev | Fills gaps              |
| 4        | seo, niche       | Background filler            |
| 5        | esoterica, cinema | Low-priority colour         |

Stories older than 48 hours are automatically rejected.

---

## Multi-platform streaming

Add targets to config.yaml:

    rtmp_targets:
      - name: "Twitch"
        url: "rtmp://live.twitch.tv/app/YOUR_KEY"
        enabled: true
      - name: "YouTube"
        url: "rtmp://a.rtmp.youtube.com/live2/YOUR_KEY"
        enabled: true

Or use the HLS relay method — see stream/launch_broadcast.sh.

---

## License

AINN Stack is licensed under the AINN Commercial Source License (ACSL) 1.0.

- Free for personal, non-commercial, and evaluation use
- Free for open-source projects
- Commercial use requires a paid license
- Does NOT convert — remains proprietary unless explicitly re-licensed

See LICENSE for full terms.
Commercial licensing: [your email]

---

## Roadmap

- [ ] Web dashboard (stream health, story queue, anchor controls)
- [ ] Webhook triggers (push breaking news instantly)
- [ ] Multi-language TTS support
- [ ] Docker container + compose stack
- [ ] Cloud deploy guide (fly.io / Railway)

---

## Contributing

PRs welcome for bug fixes and non-commercial enhancements.
Commercial feature contributions require a CLA.
