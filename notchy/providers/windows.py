"""Provider Windows: SMTC (Global System Media Transport Controls) + Core Audio.

Media  : winsdk  — Windows.Media.Control (padanan MediaRemote/MPRIS)
Volume : pycaw   — IAudioEndpointVolume (padanan VolumeManager)
Baterai/CPU/RAM : psutil

Catatan: modul ini diuji sintaks/struktur di Linux; jalur runtime penuh
membutuhkan Windows 10 1809+ dengan paket `winsdk`, `pycaw`, `comtypes`, `psutil`.
Semua impor dibungkus try/except supaya satu fitur yang gagal tidak mematikan app.
"""
from __future__ import annotations

import asyncio
import datetime
import os
import threading

from .base import NowPlaying, SystemState

try:
    import psutil
except ImportError:  # pragma: no cover
    psutil = None


# ---------------------------------------------------------------- asyncio jembatan
class _AsyncRunner:
    """Loop asyncio background — untuk memanggil API WinRT async dari thread UI."""

    def __init__(self) -> None:
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(
            target=self._loop.run_forever, daemon=True, name="notchy-winrt"
        )
        self._thread.start()

    def run(self, coro, timeout: float = 4.0):
        return asyncio.run_coroutine_threadsafe(coro, self._loop).result(timeout)


# ---------------------------------------------------------------- media (SMTC)
class WindowsMedia:
    def __init__(self) -> None:
        self._state = NowPlaying()
        self._runner = _AsyncRunner()
        self._art_seq = 0

    @property
    def state(self) -> NowPlaying:
        return self._state

    def refresh(self) -> NowPlaying:
        try:
            self._state = self._runner.run(self._snapshot())
        except Exception:
            pass
        return self._state

    async def _snapshot(self) -> NowPlaying:
        from winsdk.windows.media.control import (
            GlobalSystemMediaTransportControlsSessionManager as SessionManager,
        )

        mgr = await SessionManager.request_async()
        session = mgr.get_current_session()
        if session is None:
            return NowPlaying()

        info = await session.try_get_media_properties_async()
        timeline = session.get_timeline_properties()
        playback = session.get_playback_info()
        status = int(playback.playback_status)

        # 4 == PLAYING pada GlobalSystemMediaTransportControlsSessionPlaybackStatus
        playing = status == 4

        pos = timeline.position.total_seconds() if timeline else 0.0
        end = timeline.end_time.total_seconds() if timeline else 0.0

        app_id = ""
        try:
            app_id = session.source_app_user_model_id or ""
        except Exception:
            pass
        identity = os.path.splitext(os.path.basename(app_id))[0] or "Windows"

        art_url = await self._cache_art(info)

        return NowPlaying(
            available=True,
            identity=identity,
            title=str(info.title or "(no title)"),
            artist=str(info.artist or ""),
            album=str(info.album_title or ""),
            playing=playing,
            position=pos,
            length=end,
            art_url=art_url,
        )

    async def _cache_art(self, info) -> str:
        """Simpan thumbnail SMTC ke cache lokal → path file (skema art seragam)."""
        try:
            ref = info.thumbnail
            if ref is None:
                return ""
            stream = await ref.open_read_async()
            if stream is None or stream.size == 0:
                return ""
            from winsdk.windows.storage.streams import DataReader

            reader = DataReader(stream)
            await reader.load_async(min(stream.size, 6 * 1024 * 1024))
            n = reader.unconsumed_buffer_length
            data = bytes(reader.read_bytes(n))
            if not data:
                return ""
            cache = os.path.join(os.path.expanduser("~"), ".cache", "notchy", "art")
            os.makedirs(cache, exist_ok=True)
            self._art_seq += 1
            path = os.path.join(cache, f"smtc-{self._art_seq:04d}.img")
            tmp = path + ".part"
            with open(tmp, "wb") as f:
                f.write(data)
            os.replace(tmp, path)
            return path
        except Exception:
            return ""

    def play_pause(self) -> None:
        self._fire("try_toggle_play_pause_async")

    def next(self) -> None:
        self._fire("try_skip_next_async")

    def previous(self) -> None:
        self._fire("try_skip_previous_async")

    def _fire(self, method: str) -> None:
        async def go() -> None:
            from winsdk.windows.media.control import (
                GlobalSystemMediaTransportControlsSessionManager as SessionManager,
            )
            mgr = await SessionManager.request_async()
            session = mgr.get_current_session()
            if session is not None:
                await getattr(session, method)()

        try:
            self._runner.run(go(), timeout=1.5)
        except Exception:
            pass


# ---------------------------------------------------------------- sistem
class WindowsSystem:
    def __init__(self) -> None:
        self._volume = None
        try:
            from ctypes import POINTER, cast

            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import IAudioEndpointVolume, AudioUtilities

            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            self._volume = cast(interface, POINTER(IAudioEndpointVolume))
        except Exception:
            self._volume = None

    def read(self, state: SystemState) -> SystemState:
        # volume
        if self._volume is not None:
            try:
                state.volume = int(round(self._volume.GetMasterVolumeLevelScalar() * 100))
                state.muted = bool(self._volume.GetMute())
            except Exception:
                pass

        # baterai / cpu / ram
        if psutil is not None:
            try:
                bat = psutil.sensors_battery()
                if bat is not None:
                    state.battery_present = True
                    state.battery_percent = int(bat.percent)
                    state.charging = bool(bat.power_plugged)
            except Exception:
                pass
            try:
                state.cpu_percent = float(psutil.cpu_percent(interval=None))
                state.ram_percent = float(psutil.virtual_memory().percent)
            except Exception:
                pass

        now = datetime.datetime.now()
        state.time_str = now.strftime("%H:%M")
        state.date_str = now.strftime("%a %d %b")
        return state

    def set_volume(self, value: int) -> None:
        value = max(0, min(100, int(value)))
        if self._volume is not None:
            try:
                self._volume.SetMasterVolumeLevelScalar(value / 100.0, None)
            except Exception:
                pass
