"""
TTS Local Module

Provides text-to-speech synthesis using Piper TTS.
Supports caching to avoid regenerating audio for identical text.
"""

import hashlib
import logging
import subprocess
from pathlib import Path
from typing import Optional, Dict

PIPER_BIN = str(Path('/home/remvelchio/.local/bin/piper')) if Path('/home/remvelchio/.local/bin/piper').exists() else 'piper'


class LocalTTS:
    def __init__(
        self,
        model_path: str = "/home/remvelchio/agent/models/piper/en_US-lessac-medium.onnx",
        config_path: str = "/home/remvelchio/agent/models/piper/en_US-lessac-medium.onnx.json",
        cache_dir: str = "/home/remvelchio/agent/tmp/audio",
        voice_map: Optional[Dict] = None,
    ):
        self.model_path = model_path
        self.config_path = config_path
        self.voice_map = voice_map or {}
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger(__name__)

    def _cache_key(self, text: str, pitch: float, voice: Optional[str]) -> str:
        return hashlib.md5(f"{voice}:{pitch}:{text}".encode("utf-8")).hexdigest()

    def _select_voice(self, voice: Optional[str]):
        if voice and voice in self.voice_map:
            v = self.voice_map[voice]
            return v.get("model_path", self.model_path), v.get("config_path", self.config_path)
        return self.model_path, self.config_path

    def synthesize(self, text: str, pitch: float = 1.0, voice: Optional[str] = None) -> Optional[str]:
        if not text or not text.strip():
            return None

        model_path, config_path = self._select_voice(voice)

        if not Path(model_path).exists():
            self.logger.error("Piper model missing: %s", model_path)
            return None
        if not Path(config_path).exists():
            self.logger.error("Piper config missing: %s", config_path)
            return None

        key = self._cache_key(text, pitch, voice)
        out_path = self.cache_dir / f"tts_{key}.wav"

        if out_path.exists() and out_path.stat().st_size > 0:
            return str(out_path)

        tmp_path = out_path.with_suffix(".wav.tmp")
        if tmp_path.exists():
            tmp_path.unlink()

        cmd = [
            PIPER_BIN,
            "--model", model_path,
            "--config", config_path,
            "--output_file", str(tmp_path),
        ]
        result = subprocess.run(
            cmd,
            input=text,
            text=True,
            capture_output=True,
        )

        if result.returncode != 0:
            self.logger.error(
                "Piper failed (rc=%s). stderr=%s",
                result.returncode,
                (result.stderr or "").strip()
            )
            return None

        if not tmp_path.exists() or tmp_path.stat().st_size == 0:
            self.logger.error(
                "Piper did not create audio output: %s. stderr=%s",
                tmp_path,
                (result.stderr or "").strip()
            )
            return None

        tmp_path.replace(out_path)
        return str(out_path)
