"""
AINN Stack — Broadcast Pipeline
Core orchestrator: RSS → script generation → TTS → video → RTMP out.

Plug in your own:
  - AnchorCycler  (anchor_cycler.py)  — persona/LLM script engine
  - MemoryRing    (memory_ring.py)    — semantic dedup backend
  - Telemetry     (optional)          — observability layer

See config.example.yaml for all tunable parameters.
"""

import logging
import os
import re
import subprocess
import threading
import time
import uuid
from datetime import datetime
from typing import Dict, Optional

from image_gen import ImageGenerator
from rss_monitor import RSSMonitor
from tts_local import LocalTTS
from video_loop import make_loop
from visual_renderer import VisualStack

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Stub interfaces — replace these with your own implementations
# ---------------------------------------------------------------------------

class AnchorCyclerBase:
    """
    Replace this with your own anchor/persona engine.
    Minimum contract: generate_script(story) -> str
    """
    def __init__(self, config: dict):
        self.anchors = config.get("anchors", {}).get("cycle_order", [])
        self._idx = 0

    @property
    def current_anchor(self) -> dict:
        if not self.anchors:
            return {"name": "Anchor", "color": "#FFFFFF", "pitch": 1.0}
        return self.anchors[self._idx % len(self.anchors)]

    def advance(self):
        self._idx += 1

    def generate_script(self, story: dict) -> str:
        """
        Override this method with your LLM call.
        story keys: title, summary, link, category, source
        Returns: plain-text narration script
        """
        title   = story.get("title", "Untitled")
        summary = story.get("summary", "")
        anchor  = self.current_anchor.get("name", "Anchor")
        return (
            f"This is {anchor} with breaking news. "
            f"{title}. {summary}"
        ).strip()


class MemoryRingBase:
    """
    Replace with your own persistent semantic dedup layer.
    Minimum contract: is_duplicate(guid, title) -> (bool, str)
                      mark_seen(guid, title)
    """
    def __init__(self):
        self._seen: set = set()

    def is_duplicate(self, guid: str, title: str):
        return (guid in self._seen), "in-memory"

    def mark_seen(self, guid: str, title: str):
        self._seen.add(guid)


# ---------------------------------------------------------------------------
# Broadcast states
# ---------------------------------------------------------------------------

class BroadcastState:
    IDLE        = "idle"
    GENERATING  = "generating"
    RENDERING   = "rendering"
    STREAMING   = "streaming"
    ERROR       = "error"


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

class BroadcastPipeline:
    def __init__(self, config: dict):
        self.config  = config
        self.state   = BroadcastState.IDLE
        self._lock   = threading.Lock()
        self._stop   = threading.Event()

        # --- RSS monitor ---
        rss_cfg = config.get("rss", {})
        if isinstance(rss_cfg, list):
            feed_urls        = rss_cfg
            polling_interval = 90
            debounce_timeout = 10
        else:
            feed_urls        = (
                rss_cfg.get("feeds")
                or rss_cfg.get("urls")
                or rss_cfg.get("url")
            )
            polling_interval = rss_cfg.get("polling_interval", 90)
            debounce_timeout = rss_cfg.get("debounce_timeout", 10)

        self.rss = RSSMonitor(
            feed_urls=feed_urls,
            polling_interval=polling_interval,
            debounce_timeout=debounce_timeout,
        )

        # --- Pluggable components ---
        self.anchors = AnchorCyclerBase(config)   # swap for your AnchorCycler
        self.memory  = MemoryRingBase()            # swap for your MemoryRing

        # --- A/V components ---
        self.tts      = LocalTTS(config.get("tts", {}))
        self.visuals  = VisualStack(config.get("visuals", {}))
        self.image_gen = ImageGenerator(config.get("image_gen", {}))

        # --- RTMP targets ---
        self.rtmp_targets = config.get("rtmp_targets", [])

        # --- State ---
        self.current_story: Optional[Dict] = None
        self.last_poll_time: float = 0.0

        logger.info("BroadcastPipeline initialised")

    # -----------------------------------------------------------------------
    def run(self):
        """Main blocking loop."""
        logger.info("Broadcast loop starting")
        while not self._stop.is_set():
            try:
                self._tick()
            except Exception as e:
                logger.error(f"Pipeline tick error: {e}", exc_info=True)
                self.state = BroadcastState.ERROR
                time.sleep(5)

    def stop(self):
        self._stop.set()

    # -----------------------------------------------------------------------
    def _tick(self):
        now = time.time()

        # Poll RSS on interval
        if now - self.last_poll_time >= self.rss.polling_interval:
            self.last_poll_time = now
            story = self.rss.check_for_update()
            if story:
                self._handle_story(story)
                return

        # Check debounce-cleared pending story
        if self.rss.has_pending_story():
            story = self.rss.get_pending_story()
            if story:
                self._handle_story(story)
                return

        time.sleep(1)

    # -----------------------------------------------------------------------
    def _handle_story(self, story: dict):
        guid  = story.get("guid", "")
        title = story.get("title", "")

        dup, reason = self.memory.is_duplicate(guid, title)
        if dup:
            logger.debug(f"Skipping duplicate: {title[:60]} ({reason})")
            return

        logger.info(f"[{story.get('category','?').upper()}] {title[:80]}")

        with self._lock:
            self.state         = BroadcastState.GENERATING
            self.current_story = story

        try:
            script  = self.anchors.generate_script(story)
            anchor  = self.anchors.current_anchor

            audio_path = self._synthesise(script, anchor)
            image_path = self._render_image(story, anchor)
            video_path = self._render_video(audio_path, image_path, story)

            self.memory.mark_seen(guid, title)
            self.anchors.advance()

            self._push_to_rtmp(video_path)
            self.state = BroadcastState.STREAMING

        except Exception as e:
            logger.error(f"Story handling failed: {e}", exc_info=True)
            self.state = BroadcastState.ERROR

    # -----------------------------------------------------------------------
    def _synthesise(self, script: str, anchor: dict) -> str:
        out = os.path.join("tmp", "audio", f"{uuid.uuid4().hex}.wav")
        os.makedirs(os.path.dirname(out), exist_ok=True)
        self.tts.synthesise(
            text=script,
            output_path=out,
            pitch=anchor.get("pitch", 1.0),
        )
        return out

    def _render_image(self, story: dict, anchor: dict) -> str:
        out = os.path.join(
            "tmp", "images",
            f"story_{datetime.now().strftime('%Y%m%d-%H%M%S')}.png"
        )
        os.makedirs(os.path.dirname(out), exist_ok=True)
        self.image_gen.generate(story=story, anchor=anchor, output_path=out)
        return out

    def _render_video(self, audio_path: str, image_path: str,
                      story: dict) -> str:
        out = os.path.join(
            "tmp", "video",
            f"loop_{datetime.now().strftime('%Y%m%d-%H%M%S')}.mp4"
        )
        os.makedirs(os.path.dirname(out), exist_ok=True)
        ticker = self.visuals.render_ticker(story)
        lower  = self.visuals.render_lower_third(story)
        make_loop(
            audio_path=audio_path,
            image_path=image_path,
            output_path=out,
            ticker_text=ticker,
            lower_third=lower,
        )
        return out

    def _push_to_rtmp(self, video_path: str):
        for target in self.rtmp_targets:
            url = target.get("url", "")
            if not url:
                continue
            cmd = [
                "ffmpeg", "-hide_banner", "-loglevel", "warning",
                "-re", "-i", video_path,
                "-c", "copy", "-f", "flv", url,
            ]
            logger.info(f"Pushing to {url.split('/')[2]}")
            subprocess.Popen(cmd)
