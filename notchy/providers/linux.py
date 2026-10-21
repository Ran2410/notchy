"""Provider Linux: MPRIS (D-Bus) + ALSA + /sys + /proc.

Padanan boring.notch (REA): NowPlayingController/MediaRemote → MPRIS,
VolumeManager → amixer, BatteryActivityManager → power_supply.
"""
from __future__ import annotations

import glob
import os
import threading
import re
import subprocess

from .base import NowPlaying, SystemState

try:
    import dbus
    from dbus.exceptions import DBusException
except ImportError:  # pragma: no cover
    dbus = None
    DBusException = Exception

_VOL_RE = re.compile(r"\[(\d{1,3})%\]")


class LinuxMedia:
    def __init__(self) -> None:
        self._bus = dbus.SessionBus() if dbus else None
        self._obj = None
        self._state = NowPlaying()

    @property
    def state(self) -> NowPlaying:
        return self._state

    def _players(self) -> list[str]:
        if not self._bus:
            return []
        names = [str(n) for n in self._bus.list_names()]
        players = [n for n in names if n.startswith("org.mpris.MediaPlayer2.")]
        prio = ("spotify", "spotifyd", "mpd", "cmus", "vlc", "audacious",
                "rhythmbox", "lollypop", "amberol", "chromium", "firefox", "mpv", "brave")

        def key(n: str):
            low = n.lower()
            for i, p in enumerate(prio):
                if p in low:
                    return (i, n)
            return (len(prio), n)

        return sorted(players, key=key)

    def refresh(self) -> NowPlaying:
        players = self._players()
        if not players:
            self._state = NowPlaying()
            self._obj = None
            return self._state
        try:
            obj = self._bus.get_object(players[0], "/org/mpris/MediaPlayer2")
            props = dbus.Interface(obj, "org.freedesktop.DBus.Properties")
            meta = props.Get("org.mpris.MediaPlayer2.Player", "Metadata")
            status = str(props.Get("org.mpris.MediaPlayer2.Player", "PlaybackStatus"))
            pos = float(props.Get("org.mpris.MediaPlayer2.Player", "Position")) / 1e6
        except DBusException:
            self._state = NowPlaying()
            return self._state

        def meta_get(key: str, default: str = "") -> str:
            v = meta.get(key, default)
            if v is None:
                return default
            if isinstance(v, (list, dbus.Array)) or (hasattr(v, "__iter__") and not isinstance(v, str)):
                try:
                    joined = ", ".join(str(x) for x in v)
                    return joined or default
                except Exception:
                    return default
            return str(v)

        identity = players[0].rsplit(".", 1)[-1]
        try:
            identity = str(props.Get("org.mpris.MediaPlayer2", "Identity")) or identity
        except DBusException:
            pass

        shuffle = False
        loop_status = "None"
        can_shuffle = True
        can_loop = True
        # probe: baca properti opsional — Chrome/YouTube tidak menyediakannya
        try:
            shuffle = bool(props.Get("org.mpris.MediaPlayer2.Player", "Shuffle"))
        except DBusException:
            can_shuffle = False
        try:
            loop_status = str(props.Get("org.mpris.MediaPlayer2.Player", "LoopStatus"))
        except DBusException:
            can_loop = False
        can_seek = True
        try:
            can_seek = bool(props.Get("org.mpris.MediaPlayer2.Player", "CanSeek"))
        except DBusException:
            pass

        self._obj = obj
        self._state = NowPlaying(
            available=True,
            identity=identity,
            title=meta_get("xesam:title", "(no title)"),
            artist=meta_get("xesam:artist", ""),
            album=meta_get("xesam:album", ""),
            playing=(status == "Playing"),
            position=pos,
            length=float(meta.get("mpris:length", 0) or 0) / 1e6,
            art_url=meta_get("mpris:artUrl", ""),
            shuffle=shuffle,
            loop_status=loop_status,
            can_shuffle=can_shuffle,
            can_loop=can_loop,
            can_seek=can_seek,
        )
        self._trackid = meta.get("mpris:trackid", "")
        return self._state

    def _iface(self):
        if not self._obj or not dbus:
            return None
        return dbus.Interface(self._obj, "org.mpris.MediaPlayer2.Player")

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

    def seek(self, seconds: float) -> None:
        if not self._obj:
            return
        trackid = getattr(self, "_trackid", "")
        if not trackid:
            return
        try:
            iface = dbus.Interface(self._obj, "org.mpris.MediaPlayer2.Player")
            iface.SetPosition(dbus.ObjectPath(str(trackid)), dbus.Int64(int(seconds * 1e6)))
        except DBusException:
            pass

    def set_shuffle(self, enabled: bool) -> None:
        if not self._obj:
            return
        try:
            props = dbus.Interface(self._obj, "org.freedesktop.DBus.Properties")
            props.Set("org.mpris.MediaPlayer2.Player", "Shuffle", dbus.Boolean(enabled))
        except DBusException:
            pass

    def cycle_loop(self) -> None:
        """None → Playlist → Track → None (padanan tombol repeat)."""
        if not self._obj:
            return
        order = {"None": "Playlist", "Playlist": "Track", "Track": "None"}
        nxt = order.get(getattr(self._state, "loop_status", "None"), "None")
        try:
            props = dbus.Interface(self._obj, "org.freedesktop.DBus.Properties")
            props.Set("org.mpris.MediaPlayer2.Player", "LoopStatus", dbus.String(nxt))
        except DBusException:
            pass


class LinuxSystem:
    def __init__(self) -> None:
        self._prev_idle = 0
        self._prev_total = 0

    def read(self, state: SystemState) -> SystemState:
        # volume (ALSA)
        try:
            out = subprocess.run(
                ["amixer", "get", "Master"], capture_output=True, text=True, timeout=1.5
            ).stdout
            m = _VOL_RE.findall(out)
            if m:
                state.volume = int(m[-1])
        except Exception:
            pass

        # baterai
        bats = sorted(glob.glob("/sys/class/power_supply/BAT*"))
        if bats:
            try:
                state.battery_present = True
                state.battery_percent = int(open(os.path.join(bats[0], "capacity")).read().strip())
                status = open(os.path.join(bats[0], "status")).read().strip().lower()
                state.charging = status in ("charging", "full", "not charging")
            except Exception:
                state.battery_present = False

        # CPU delta
        try:
            parts = open("/proc/stat").read().splitlines()[0].split()
            nums = [int(x) for x in parts[1:]]
            idle = nums[3] + (nums[4] if len(nums) > 4 else 0)
            total = sum(nums)
            d_total = total - self._prev_total
            d_idle = idle - self._prev_idle
            if d_total > 0:
                state.cpu_percent = max(0.0, min(100.0, (1.0 - d_idle / d_total) * 100.0))
            self._prev_idle, self._prev_total = idle, total
        except Exception:
            pass

        # RAM
        try:
            mem = {}
            for line in open("/proc/meminfo"):
                k, v = line.split(":", 1)
                mem[k.strip()] = int(v.strip().split()[0])
            total = mem.get("MemTotal", 0)
            avail = mem.get("MemAvailable", 0)
            if total:
                state.ram_percent = max(0.0, min(100.0, (1.0 - avail / total) * 100.0))
        except Exception:
            pass

        # brightness (sysfs backlight)
        try:
            cands = sorted(glob.glob("/sys/class/backlight/*/brightness"))
            if cands:
                base = os.path.dirname(cands[0])
                cur = int(open(os.path.join(base, "brightness")).read().strip())
                mx = int(open(os.path.join(base, "max_brightness")).read().strip())
                if mx > 0:
                    state.brightness = int(round(cur * 100.0 / mx))
        except Exception:
            pass

        import datetime
        now = datetime.datetime.now()
        state.time_str = now.strftime("%H:%M")
        state.date_str = now.strftime("%a %d %b")
        return state

    def set_volume(self, value: int) -> None:
        value = max(0, min(100, int(value)))
        try:
            subprocess.run(["amixer", "set", "Master", f"{value}%"], capture_output=True, timeout=1.5)
        except Exception:
            pass


# ---------------------------------------------------------------- notifikasi
class NotificationMonitor:
    """Menguping notifikasi desktop (org.freedesktop.Notifications.Notify).

    Dipakai untuk sneak-peek di island (padanan 'Instant Notifications').
    Berjalan di thread sendiri; callback dipanggil dari thread itu — pemanggil
    wajib meneruskan ke main loop Qt (lihat IslandWindow).
    """

    def __init__(self, callback) -> None:
        self._callback = callback
        self._stop = False
        self._thread = None

    def start(self) -> None:
        if not dbus:
            return
        self._thread = threading.Thread(target=self._run, daemon=True, name="notchy-notif")
        self._thread.start()

    def stop(self) -> None:
        self._stop = True

    def _run(self) -> None:
        try:
            bus = dbus.SessionBus()
            bus.add_match_string(
                "type='method_call',interface='org.freedesktop.Notifications',member='Notify'",
                eavesdrop=True,
            )
            bus.add_message_filter(self._on_message)
            while not self._stop:
                bus.process(0.25)
        except Exception:
            # eavesdrop bisa ditolak beberapa konfigurasi — fitur mati sendiri
            return

    def _on_message(self, bus, msg) -> None:
        try:
            args = msg.get_args_list()
            # Notify(app, replaces_id, app_icon, summary, body, actions, hints, timeout)
            if len(args) >= 5:
                summary = str(args[3] or "").strip()
                body = str(args[4] or "").strip()
                if summary or body:
                    self._callback(summary, body)
        except Exception:
            pass
