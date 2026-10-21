"""Sumber data live-activity untuk Linux.

Padanan temuan REA boring.notch:
  NowPlayingController (MediaRemote)  → MPRIS D-Bus  (org.mpris.MediaPlayer2.*)
  VolumeManager / BrightnessManager   → amixer + /sys/class/backlight
  BatteryActivityManager              → /sys/class/power_supply
  JSONLinesPipeHandler                → (opsional; v1 memakai poll D-Bus)
"""
from __future__ import annotations

import glob
import os
import re
import subprocess
from dataclasses import dataclass, field

import dbus
from dbus.exceptions import DBusException


# ---------------------------------------------------------------- MPRIS
@dataclass
class NowPlaying:
    available: bool = False
    identity: str = ""
    title: str = ""
    artist: str = ""
    album: str = ""
    playing: bool = False
    position: float = 0.0        # detik
    length: float = 0.0          # detik
    art_url: str = ""
    can_play: bool = True
    can_next: bool = True
    can_prev: bool = True
    bus_name: str = ""
    player: object = field(default=None, repr=False)

    @property
    def progress(self) -> float:
        if self.length <= 0:
            return 0.0
        return max(0.0, min(1.0, self.position / self.length))


class MprisProvider:
    """Polling pemutar musik via MPRIS — padanan MediaRemoteAdapter.framework."""

    def __init__(self) -> None:
        self._bus = dbus.SessionBus()
        self._state = NowPlaying()

    @property
    def state(self) -> NowPlaying:
        return self._state

    def _list_players(self) -> list[str]:
        names = [str(n) for n in self._bus.list_names()]
        players = [n for n in names if n.startswith("org.mpris.MediaPlayer2.")]
        # urutkan stabil; prioritaskan yang umum
        prio = ("spotify", "spotifyd", "mpd", "cmus", "vlc", "audacious",
                "rhythmbox", "lollypop", "amberol", "plasma", "chromium", "firefox", "mpv")
        def key(n: str) -> tuple[int, str]:
            low = n.lower()
            for i, p in enumerate(prio):
                if p in low:
                    return (i, n)
            return (len(prio), n)
        return sorted(players, key=key)

    def refresh(self) -> NowPlaying:
        players = self._list_players()
        if not players:
            self._state = NowPlaying()
            return self._state

        bus_name = players[0]
        try:
            obj = self._bus.get_object(bus_name, "/org/mpris/MediaPlayer2")
            props = dbus.Interface(obj, "org.freedesktop.DBus.Properties")
            meta = props.Get("org.mpris.MediaPlayer2.Player", "Metadata")
            status = str(props.Get("org.mpris.MediaPlayer2.Player", "PlaybackStatus"))
            pos = float(props.Get("org.mpris.MediaPlayer2.Player", "Position")) / 1e6
        except DBusException:
            self._state = NowPlaying()
            return self._state

        def meta_get(key: str, default: str = "") -> str:
            v = meta.get(key, default)
            try:
                if isinstance(v, dbus.Array) or isinstance(v, list):
                    return ", ".join(str(x) for x in v) if len(v) else default
                return str(v) if v is not None else default
            except Exception:
                return default

        length = float(meta.get("mpris:length", 0) or 0) / 1e6
        identity = bus_name.rsplit(".", 1)[-1]
        try:
            identity = str(props.Get("org.mpris.MediaPlayer2", "Identity")) or identity
        except DBusException:
            pass

        self._state = NowPlaying(
            available=True,
            identity=identity,
            title=meta_get("xesam:title", "(no title)"),
            artist=meta_get("xesam:artist", ""),
            album=meta_get("xesam:album", ""),
            playing=(status == "Playing"),
            position=pos,
            length=length,
            art_url=meta_get("mpris:artUrl", ""),
            bus_name=bus_name,
            player=obj,
        )
        return self._state

    # --- kontrol ---
    def _iface(self):
        if not self._state.player:
            return None
        return dbus.Interface(self._state.player, "org.mpris.MediaPlayer2.Player")

    def play_pause(self) -> None:
        iface = self._iface()
        if iface:
            try:
                iface.PlayPause()
            except DBusException:
                pass

    def next(self) -> None:
        iface = self._iface()
        if iface:
            try:
                iface.Next()
            except DBusException:
                pass

    def previous(self) -> None:
        iface = self._iface()
        if iface:
            try:
                iface.Previous()
            except DBusException:
                pass


# ---------------------------------------------------------------- volume
_VOL_RE = re.compile(r"\[(\d{1,3})%\]")


class VolumeProvider:
    def __init__(self) -> None:
        self.level = 0  # 0..100
        self.muted = False
        self.refresh()

    def refresh(self) -> int:
        try:
            out = subprocess.run(
                ["amixer", "get", "Master"], capture_output=True, text=True, timeout=1.5
            ).stdout
            m = _VOL_RE.findall(out)
            if m:
                self.level = int(m[-1])
            self.muted = "[off]" in out.split("Playback")[-1] if "Playback" in out else self.muted
        except Exception:
            pass
        return self.level

    def set_level(self, value: int) -> None:
        value = max(0, min(100, int(value)))
        try:
            subprocess.run(
                ["amixer", "set", "Master", f"{value}%"],
                capture_output=True, timeout=1.5,
            )
            self.level = value
            self.muted = False
        except Exception:
            pass

    def toggle_mute(self) -> None:
        try:
            subprocess.run(["amixer", "set", "Master", "toggle"], capture_output=True, timeout=1.5)
            self.refresh()
        except Exception:
            pass


# ---------------------------------------------------------------- baterai
class BatteryProvider:
    def __init__(self) -> None:
        self.present = False
        self.percent = 0
        self.charging = False
        self.refresh()

    def refresh(self) -> None:
        bases = sorted(glob.glob("/sys/class/power_supply/BAT*"))
        if not bases:
            self.present = False
            return
        base = bases[0]
        try:
            self.present = True
            self.percent = int(open(os.path.join(base, "capacity")).read().strip())
            status = open(os.path.join(base, "status")).read().strip().lower()
            self.charging = status in ("charging", "full", "not charging")
        except Exception:
            self.present = False


# ---------------------------------------------------------------- clock
class ClockProvider:
    def __init__(self) -> None:
        self.time_str = ""
        self.date_str = ""
        self.refresh()

    def refresh(self) -> tuple[str, str]:
        import datetime
        now = datetime.datetime.now()
        self.time_str = now.strftime("%H:%M")
        self.date_str = now.strftime("%a %d %b")
        return self.time_str, self.date_str


# ---------------------------------------------------------------- sistem
class SystemProvider:
    """CPU & RAM — padanan widget sistem ala Alcove (CPU/RAM tiles)."""

    def __init__(self) -> None:
        self.cpu_percent = 0.0
        self.ram_percent = 0.0
        self._prev_idle = 0
        self._prev_total = 0
        self.refresh()

    def refresh(self) -> None:
        # CPU dari /proc/stat (delta antar sampling)
        try:
            parts = open("/proc/stat").read().splitlines()[0].split()
            nums = [int(x) for x in parts[1:]]
            idle = nums[3] + (nums[4] if len(nums) > 4 else 0)
            total = sum(nums)
            d_total = total - self._prev_total
            d_idle = idle - self._prev_idle
            if d_total > 0:
                self.cpu_percent = max(0.0, min(100.0, (1.0 - d_idle / d_total) * 100.0))
            self._prev_idle, self._prev_total = idle, total
        except Exception:
            pass
        try:
            mem = {}
            for line in open("/proc/meminfo"):
                k, v = line.split(":", 1)
                mem[k.strip()] = int(v.strip().split()[0])
            total = mem.get("MemTotal", 0)
            avail = mem.get("MemAvailable", 0)
            if total:
                self.ram_percent = max(0.0, min(100.0, (1.0 - avail / total) * 100.0))
        except Exception:
            pass
