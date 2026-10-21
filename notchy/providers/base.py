"""Tipe data live-activity — platform-agnostic."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class NowPlaying:
    available: bool = False
    identity: str = ""
    title: str = ""
    artist: str = ""
    album: str = ""
    playing: bool = False
    position: float = 0.0
    length: float = 0.0
    art_url: str = ""       # file:// | http(s):// | data: | path kosong
    can_next: bool = True
    can_prev: bool = True
    shuffle: bool = False
    loop_status: str = "None"   # None | Track | Playlist
    can_shuffle: bool = False   # apakah pemutar mendukung set Shuffle
    can_loop: bool = False      # apakah pemutar mendukung set LoopStatus
    can_seek: bool = True
    _control: object = field(default=None, repr=False)

    @property
    def progress(self) -> float:
        if self.length <= 0:
            return 0.0
        return max(0.0, min(1.0, self.position / self.length))


@dataclass
class SystemState:
    volume: int = 0
    muted: bool = False
    battery_percent: int = 0
    battery_present: bool = False
    charging: bool = False
    cpu_percent: float = 0.0
    ram_percent: float = 0.0
    brightness: int = -1        # -1 = tidak tersedia
    time_str: str = "--:--"
    date_str: str = ""


class MediaController:
    """Kontrak kontrol pemutar (play/pause/next/prev/seek/shuffle/loop)."""

    def play_pause(self) -> None: ...
    def next(self) -> None: ...
    def previous(self) -> None: ...
    def seek(self, seconds: float) -> None: ...
    def set_shuffle(self, enabled: bool) -> None: ...
    def cycle_loop(self) -> None: ...
