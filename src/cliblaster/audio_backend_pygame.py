"""
Audio backend using pygame-ce.

For YouTube URLs, uses yt-dlp + bundled ffmpeg (via imageio-ffmpeg) to download
and convert to MP3 — the only format reliably supported by pygame on Windows.
"""

import os
import sys
import tempfile
import subprocess
import shutil
import pygame

from cliblaster.audio_backend import AudioBackend


def _get_ffmpeg() -> str:
    """Return the path to the bundled ffmpeg binary from imageio-ffmpeg."""
    try:
        import imageio_ffmpeg
        path = imageio_ffmpeg.get_ffmpeg_exe()
        if os.path.exists(path):
            return path
    except Exception:
        pass
    # Fallback: system ffmpeg
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        return ffmpeg
    raise RuntimeError(
        "ffmpeg not found. Please install imageio-ffmpeg:\n"
        "  pip install imageio-ffmpeg"
    )


class PygameBackend(AudioBackend):
    """Audio backend using pygame-ce (pygame.mixer.music)."""

    def __init__(self) -> None:
        if not pygame.mixer.get_init():
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=2048)
        self._tmp_dir: str | None = None

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _is_youtube_url(self, path: str) -> bool:
        return "youtube.com/watch" in path or "youtu.be/" in path

    def _cleanup_tmp(self) -> None:
        """Delete the temp directory from the previous download."""
        if self._tmp_dir and os.path.isdir(self._tmp_dir):
            try:
                shutil.rmtree(self._tmp_dir, ignore_errors=True)
            except Exception:
                pass
        self._tmp_dir = None

    def _download_as_mp3(self, youtube_url: str) -> str:
        """
        Download a YouTube video's audio and convert it to MP3 using
        yt-dlp + ffmpeg.  Returns the path to the resulting .mp3 file.
        """
        self._cleanup_tmp()
        tmp_dir = tempfile.mkdtemp(prefix="cliblaster_")
        self._tmp_dir = tmp_dir
        out_template = os.path.join(tmp_dir, "audio.%(ext)s")

        ffmpeg_path = _get_ffmpeg()

        cmd = [
            sys.executable, "-m", "yt_dlp",
            "--extract-audio",
            "--audio-format", "mp3",
            "--audio-quality", "5",          # VBR ~130 kbps – good quality
            "--ffmpeg-location", ffmpeg_path,
            "--output", out_template,
            "--no-playlist",
            "--quiet",
            "--no-warnings",
            youtube_url,
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, timeout=180)
        except subprocess.TimeoutExpired:
            raise ValueError("Download timed out (>3 min). Check your internet connection.")

        if result.returncode != 0:
            err = result.stderr.decode("utf-8", errors="replace").strip()
            raise ValueError(f"yt-dlp error: {err[:400] or '(no output)'}")

        mp3_path = os.path.join(tmp_dir, "audio.mp3")
        if not os.path.exists(mp3_path) or os.path.getsize(mp3_path) == 0:
            # yt-dlp might name it differently — scan the dir
            for fname in os.listdir(tmp_dir):
                fp = os.path.join(tmp_dir, fname)
                if os.path.isfile(fp) and os.path.getsize(fp) > 0:
                    return fp
            raise ValueError("yt-dlp produced no audio file.")

        return mp3_path

    # ------------------------------------------------------------------ #
    # AudioBackend protocol
    # ------------------------------------------------------------------ #

    def load(self, path: str) -> None:
        """Load audio from a local file path or a YouTube URL."""
        if self._is_youtube_url(path):
            mp3_path = self._download_as_mp3(path)
            try:
                pygame.mixer.music.load(mp3_path)
            except pygame.error as e:
                raise ValueError(f"pygame could not load downloaded MP3: {e}")
        else:
            if not os.path.exists(path):
                raise FileNotFoundError(f"Audio file not found: {path}")
            try:
                pygame.mixer.music.load(path)
            except pygame.error as e:
                raise ValueError(f"Unsupported audio format: {e}")

    def play(self) -> None:
        pygame.mixer.music.play()

    def pause(self) -> None:
        pygame.mixer.music.pause()

    def resume(self) -> None:
        pygame.mixer.music.unpause()

    def stop(self) -> None:
        pygame.mixer.music.stop()
        self._cleanup_tmp()

    def set_volume(self, volume: float) -> None:
        clamped = max(0.0, min(1.0, volume))
        pygame.mixer.music.set_volume(clamped)

    def get_volume(self) -> float:
        return pygame.mixer.music.get_volume()
