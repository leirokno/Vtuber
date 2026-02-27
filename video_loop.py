import subprocess
from pathlib import Path
from typing import Optional

def _get_audio_duration(audio_path: str) -> Optional[float]:
    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            audio_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return float(result.stdout.strip())
    except Exception:
        return None

def _escape_drawtext(text: str) -> str:
    return (
        text.replace('\\', '\\\\')
            .replace(':', '\\:')
            .replace("'", "\\'")
            .replace('%', '\\%')
    )

    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            audio_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return float(result.stdout.strip())
    except Exception:
        return None

def make_loop(
    image_path: str,
    out_path: str,
    seconds: Optional[int] = 6,
    fps: int = 30,
    audio_path: Optional[str] = None,
    ticker_text: Optional[str] = None,
    font_path: str = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ticker_height: int = 60,
    ticker_font_size: int = 28,
) -> str:
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)

    if audio_path and seconds is None:
        dur = _get_audio_duration(audio_path)
        if dur:
            seconds = int(dur) + 1

    cmd = [
        "ffmpeg", "-y",
        "-loop", "1",
        "-i", image_path,
    ]

    if audio_path:
        cmd.extend(["-i", audio_path])

    filter_parts = ["zoompan=z='min(1.05,1+0.0005*on)':d=1:s=1024x576"]
    if ticker_text:
        safe_text = _escape_drawtext(ticker_text)
        if not Path(font_path).exists():
            font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        filter_parts.append(
            f"drawbox=x=0:y=h-{ticker_height}:w=iw:h={ticker_height}:color=black@0.55:t=fill"
        )
        # Scroll ticker right-to-left
        filter_parts.append(
            f"drawtext=fontfile={font_path}:text='{safe_text}':fontcolor=white:"
            f"fontsize={ticker_font_size}:x=w-mod(t*120\,(w+tw)):y=h-{ticker_height}+14:"
            "shadowcolor=black@0.6:shadowx=2:shadowy=2"
        )
    filter_str = ",".join(filter_parts)
    cmd.extend([
        "-t", str(seconds),
        "-r", str(fps),
        "-vf", filter_str,
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
    ])

    if audio_path:
        cmd.extend([
            "-c:a", "aac",
            "-b:a", "128k",
            "-shortest"
        ])
    else:
        cmd.append("-an")

    cmd.append(out_path)

    subprocess.run(cmd, check=True)
    return out_path
