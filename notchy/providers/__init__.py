"""Pemilihan provider sesuai OS."""
from __future__ import annotations

import sys
from dataclasses import dataclass

from .base import NowPlaying, SystemState


@dataclass
class Providers:
    media: object
    system: object


def make_providers() -> Providers:
    if sys.platform.startswith("win"):
        from .windows import WindowsMedia, WindowsSystem

        return Providers(media=WindowsMedia(), system=WindowsSystem())
    if sys.platform == "darwin":
        # macOS belum didukung; pakai jalur Linux (MPRIS tidak ada → idle)
        from .linux import LinuxMedia, LinuxSystem

        return Providers(media=LinuxMedia(), system=LinuxSystem())
    from .linux import LinuxMedia, LinuxSystem

    return Providers(media=LinuxMedia(), system=LinuxSystem())


__all__ = ["Providers", "make_providers", "NowPlaying", "SystemState"]
