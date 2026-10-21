"""Pemilihan provider sesuai OS."""
from __future__ import annotations

import sys
from dataclasses import dataclass

from .base import NowPlaying, SystemState


@dataclass
class Providers:
    media: object
    system: object
    audio_out: object


def make_providers() -> Providers:
    if sys.platform.startswith("win"):
        from .windows import AudioOutputMonitor, WindowsMedia, WindowsSystem

        return Providers(media=WindowsMedia(), system=WindowsSystem(),
                         audio_out=AudioOutputMonitor())
    from .linux import AudioOutputMonitor, LinuxMedia, LinuxSystem

    return Providers(media=LinuxMedia(), system=LinuxSystem(),
                     audio_out=AudioOutputMonitor())


__all__ = ["Providers", "make_providers", "NowPlaying", "SystemState"]
