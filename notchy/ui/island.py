"""Island window Qt — cross-platform (Linux X11/Xwayland + Windows).

Padanan temuan REA boring.notch:
  BoringNotchSkyLightWindow → frameless + stay-on-top + top-center
  NotchState closed↔open     → QPropertyAnimation geometry (OutCubic)
  openNotchOnHover           → enter/leave event
  closeNotchTask             → QTimer penutupan otomatis
"""
from __future__ import annotations

import sys

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QRect, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QCursor, QPainter, QPen
from PySide6.QtWidgets import QApplication, QMenu, QWidget

from .. import config as C
from ..providers import make_providers
from ..services import DownloadsService, LyricsResult, LyricsService, WeatherService
from ..timer import TimerController
from .activities import Activities
from .style import ISLAND_QSS

SHADOW_PAD = 0  # tanpa shadow — island = kotak murni


class IslandWindow(QWidget):
    # diteruskan dari thread notifikasi D-Bus ke main loop Qt
    notif_received = Signal(str, str)

    def __init__(self) -> None:
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setObjectName("Island")
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, False)
        self.setWindowTitle("notchy")

        import os as _os
        from PySide6.QtGui import QIcon as _QIcon

        _icon_path = _os.path.normpath(_os.path.join(
            _os.path.dirname(_os.path.abspath(__file__)), "..", "..", "assets", "notchy-icon.png"))
        if _os.path.isfile(_icon_path):
            self.setWindowIcon(_QIcon(_icon_path))

        self.providers = make_providers()
        from ..providers.base import SystemState

        self.sys_state = SystemState()
        self.timer_controller = TimerController(self)

        # Prioritas 2
        self.weather = WeatherService()
        self.downloads = DownloadsService()
        self.lyrics = LyricsService()
        self._lyrics_track = ""
        self._bat_low_alerted = False
        self._bat_full_alerted = False
        self._last_charging = None

        self.activities = Activities(timer=self.timer_controller, parent=self)
        self.activities.setObjectName("island-bg")
        self.setStyleSheet(ISLAND_QSS)

        # tata letak isi di dalam padding bayangan
        self._layout_content(C.CLOSED_W, C.CLOSED_H)

        # animasi morph
        self._anim = QPropertyAnimation(self, b"geometry")
        self._anim.setDuration(C.ANIM_MS)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim.valueChanged.connect(self._on_anim_frame)
        # setelah morph selesai, cek posisi kursor (leaveEvent bisa terlewat
        # saat jendela bergeser selama animasi)
        self._anim.finished.connect(self._verify_pointer)

        self._t = 0.0
        self._target = 0.0
        self._pinned = False
        self._pointer_inside = False

        self._close_timer = QTimer(self)
        self._close_timer.setSingleShot(True)
        self._close_timer.setInterval(C.CLOSE_DELAY_MS)
        self._close_timer.timeout.connect(self._close_now)

        self._poll_media = QTimer(self)
        self._poll_media.setInterval(C.POLL_MPRIS_MS)
        self._poll_media.timeout.connect(self._do_poll_media)
        self._poll_media.start()

        self._poll_sys = QTimer(self)
        self._poll_sys.setInterval(C.POLL_SYS_MS)
        self._poll_sys.timeout.connect(self._do_poll_sys)
        self._poll_sys.start()

        self._poll_clock = QTimer(self)
        self._poll_clock.setInterval(1000)
        self._poll_clock.timeout.connect(self._do_poll_clock)
        self._poll_clock.start()

        # jaring pengaman: pastikan panel menutup walau leaveEvent terlewat
        self._pointer_watch = QTimer(self)
        self._pointer_watch.setInterval(800)
        self._pointer_watch.timeout.connect(self._verify_pointer)
        self._pointer_watch.start()

        # Prioritas 2 — cuaca / unduhan
        self._poll_weather = QTimer(self)
        self._poll_weather.setInterval(C.WEATHER_POLL_MS)
        self._poll_weather.timeout.connect(self._do_poll_weather)
        self._poll_weather.start()

        self._poll_downloads = QTimer(self)
        self._poll_downloads.setInterval(C.DOWNLOADS_POLL_MS)
        self._poll_downloads.timeout.connect(self._do_poll_downloads)
        self._poll_downloads.start()

        # monitor audio output (headset/earphone)
        self._poll_audio = QTimer(self)
        self._poll_audio.setInterval(C.AUDIO_POLL_MS)
        self._poll_audio.timeout.connect(self._do_poll_audio)
        self._poll_audio.start()

        # hasil fetch lirik (thread → poll)
        self._poll_lyrics = QTimer(self)
        self._poll_lyrics.setInterval(600)
        self._poll_lyrics.timeout.connect(self._do_poll_lyrics)
        self._poll_lyrics.start()

        self.activities.play_pause_clicked.connect(self.providers.media.play_pause)
        self.activities.next_clicked.connect(self.providers.media.next)
        self.activities.prev_clicked.connect(self.providers.media.previous)
        self.activities.volume_changed.connect(self._on_volume_slider)
        self.activities.seek_requested.connect(self._on_seek)
        self.activities.lyrics_seek.connect(self._on_lyrics_seek)
        self.activities.shuffle_clicked.connect(self._on_shuffle)
        self.activities.loop_clicked.connect(self._on_loop)
        self._last_np = None

        # --- HUD volume/brightness: deteksi perubahan dari luar (tombol keyboard) ---
        self._last_vol: int | None = None
        self._last_bright: int | None = None
        self._vol_set_at = 0.0  # timestamp set_volume via slider → redam HUD

        # --- monitor headset/earphone (Bluetooth + jack) ---
        try:
            self.providers.audio_out.start()
        except Exception:
            pass

        # --- toast notifikasi desktop (Linux) ---
        self.notif_received.connect(self._on_notif)
        self._notif_mon = None
        try:
            from ..providers.linux import NotificationMonitor

            if sys.platform.startswith("linux"):
                self._notif_mon = NotificationMonitor(self._emit_notif)
                self._notif_mon.start()
        except Exception:
            self._notif_mon = None

        self._do_poll_media()
        self._do_poll_sys()
        self._do_poll_clock()
        self._do_poll_weather()
        self._do_poll_downloads()
        self.setGeometry(self._place_top_center(C.CLOSED_W, C.CLOSED_H))

    # ------------------------------------------------------------ layout
    def _layout_content(self, w: int, h: int) -> None:
        self.activities.setGeometry(SHADOW_PAD, SHADOW_PAD, w, h)
        self._apply_radius(h)

    def _apply_radius(self, h: int) -> None:
        # radius = min(24, h/2): pill penuh saat closed (h=40 → r=20),
        # rounded-rect saat open. Cache agar tidak restyle tiap frame animasi.
        r = int(min(C.RADIUS_ISLAND, max(0, h) / 2))
        if getattr(self, "_last_radius", None) == r:
            return
        self._last_radius = r
        self.activities.setStyleSheet(
            "QWidget#island-bg {"
            " background-color: #0c0c12;"
            " background: qlineargradient(x1:0,y1:0,x2:0,y2:1,"
            "   stop:0 #1c1c26, stop:0.42 #0e0e14, stop:1 #0a0a0f);"
            " border: 1px solid rgba(255,255,255,0.10);"
            f" border-radius: {r}px; }}"
        )

    def _place_top_center(self, w: int, h: int) -> QRect:
        screen = QApplication.primaryScreen()
        geo = screen.availableGeometry() if screen else QRect(0, 0, 1920, 1080)
        total_w = w + SHADOW_PAD * 2
        total_h = h + SHADOW_PAD * 2
        x = geo.x() + max(C.SIDE_MIN_MARGIN, (geo.width() - total_w) // 2)
        y = geo.y() + C.TOP_MARGIN
        return QRect(x, y, total_w, total_h)

    def _current_size(self) -> tuple[int, int]:
        w = C.CLOSED_W + (C.OPEN_W - C.CLOSED_W) * self._t
        h = C.CLOSED_H + (C.OPEN_H - C.CLOSED_H) * self._t
        return int(round(w)), int(round(h))

    def _on_anim_frame(self, _rect) -> None:
        rect: QRect = self.geometry()
        self._layout_content(rect.width() - SHADOW_PAD * 2, rect.height() - SHADOW_PAD * 2)

    # ------------------------------------------------------------ animasi
    def _animate_to(self, target: float) -> None:
        self._stop_pill_pop()
        target = 1.0 if target > 0.5 else 0.0
        if target == self._target and abs(self._t - target) < 0.001:
            return
        self._target = target
        t0 = self._t
        start = self._current_size()
        self._t = target
        end = self._current_size()
        self._t = t0

        self._anim.stop()
        self._anim.setStartValue(self._place_top_center(*start))
        self._anim.setEndValue(self._place_top_center(*end))
        # opacity konten dianimasikan bertahap lewat timer kecil
        self._anim.start()
        self._morph_opacity(t0, target)

    def _morph_opacity(self, t0: float, t1: float) -> None:
        self._opacity_t0 = t0
        self._opacity_t1 = t1
        self._opacity_step = 0
        if not hasattr(self, "_opacity_timer"):
            self._opacity_timer = QTimer(self)
            self._opacity_timer.setInterval(16)
            self._opacity_timer.timeout.connect(self._opacity_tick)
        self._opacity_timer.start()

    def _opacity_tick(self) -> None:
        steps = max(1, C.ANIM_MS // 16)
        self._opacity_step = getattr(self, "_opacity_step", 0) + 1
        u = min(1.0, self._opacity_step / steps)
        e = 1.0 - (1.0 - u) ** C.EASE_POWER
        self._t = self._opacity_t0 + (self._opacity_t1 - self._opacity_t0) * e
        self.activities.set_opacity_for(self._t)
        if u >= 1.0:
            self._t = self._opacity_t1
            self._opacity_timer.stop()

    def _pill_pop(self) -> None:
        """Pill sedikit membesar-mengecil (OutBack) saat headset tersambung."""
        if self._t > 0.05 or self._pinned:
            return
        from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QRect, QSequentialAnimationGroup

        base = self.geometry()
        grow = QRect(base.x() - 6, base.y() - 2,
                     base.width() + 12, base.height() + 4)
        seq = QSequentialAnimationGroup(self)
        a1 = QPropertyAnimation(self, b"geometry")
        a1.setDuration(170)
        a1.setStartValue(base)
        a1.setEndValue(grow)
        a1.setEasingCurve(QEasingCurve.OutBack)
        a2 = QPropertyAnimation(self, b"geometry")
        a2.setDuration(240)
        a2.setStartValue(grow)
        a2.setEndValue(base)
        a2.setEasingCurve(QEasingCurve.OutCubic)
        a1.valueChanged.connect(lambda _v: self._on_anim_frame(None))
        a2.valueChanged.connect(lambda _v: self._on_anim_frame(None))
        seq.addAnimation(a1)
        seq.addAnimation(a2)
        self._pop_anim = seq
        seq.start()

    def _stop_pill_pop(self) -> None:
        pop = getattr(self, "_pop_anim", None)
        if pop is not None and pop.state() != QPropertyAnimation.Stopped:
            pop.stop()
            self._pop_anim = None
            self.setGeometry(self._place_top_center(C.CLOSED_W, C.CLOSED_H))
            self._layout_content(C.CLOSED_W, C.CLOSED_H)

    def expand(self) -> None:
        self._close_timer.stop()
        self._animate_to(1.0)

    def collapse(self) -> None:
        if self._pinned:
            return
        self._animate_to(0.0)

    def toggle_pin(self) -> None:
        self._pinned = not self._pinned
        if self._pinned:
            self._animate_to(1.0)
        else:
            self.collapse()

    # ------------------------------------------------------------ event
    def enterEvent(self, ev) -> None:
        self._pointer_inside = True
        self._close_timer.stop()
        self._animate_to(1.0)
        super().enterEvent(ev)

    def leaveEvent(self, ev) -> None:
        # SELALU catat bahwa kursor keluar — dulu event ini dibuang saat animasi
        # berjalan, sehingga _pointer_inside nyangkut True dan panel tak pernah
        # menutup sendiri.
        self._pointer_inside = False
        self._close_timer.start()
        super().leaveEvent(ev)

    def changeEvent(self, ev) -> None:
        # klik app lain → window kehilangan aktivasi → tutup panel
        from PySide6.QtCore import QEvent

        if ev.type() == QEvent.ActivationChange and not self.isActiveWindow():
            # user beralih ke app lain → tutup seketika, abaikan pin
            self._pinned = False
            self._pointer_inside = False
            self._close_timer.stop()
            self._animate_to(0.0)
        super().changeEvent(ev)

    def _verify_pointer(self) -> None:
        """Sinkronkan state kursor dengan posisi nyata, lalu jadwalkan tutup.

        Penting: koreksi state yang nyangkut (mis. leaveEvent terlewat saat
        morph) — jangan hanya menambah timer bila flag sudah False.
        """
        if self._t <= 0.01:
            return
        inside = self.geometry().contains(QCursor.pos())
        self._pointer_inside = inside
        if inside or self._pinned:
            self._close_timer.stop()
        else:
            self._close_timer.start()

    def _close_now(self) -> None:
        # double-check: jangan tutup bila kursor masih di atas island
        if self.geometry().contains(QCursor.pos()):
            self._pointer_inside = True
            return
        if not self._pointer_inside:
            self._pinned = False
            self.collapse()

    def mousePressEvent(self, ev) -> None:
        if ev.button() == Qt.LeftButton and self._t < 0.15:
            self.toggle_pin()
        super().mousePressEvent(ev)

    def keyPressEvent(self, ev) -> None:
        # panah kiri/kanan juga memindah tab saat panel terbuka
        if ev.key() in (Qt.Key_Left, Qt.Key_Right):
            self.activities.switch_tab(-1 if ev.key() == Qt.Key_Left else 1)
            ev.accept()
            return
        super().keyPressEvent(ev)

    def contextMenuEvent(self, ev) -> None:
        menu = QMenu(self)
        quit_act = menu.addAction("Quit notchy")
        quit_act.triggered.connect(QApplication.quit)
        menu.exec(ev.globalPos())

    def paintEvent(self, ev) -> None:
        # tanpa shadow — cukup hairline highlight dari QSS border
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        pen = QPen(QColor(255, 255, 255, 28), 1.0)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        h = self.height() - SHADOW_PAD * 2
        r = min(C.RADIUS_ISLAND, max(0, h) / 2)
        p.drawRoundedRect(
            SHADOW_PAD + 0.5, SHADOW_PAD + 0.5,
            self.width() - SHADOW_PAD * 2 - 1,
            self.height() - SHADOW_PAD * 2 - 1,
            r, r,
        )
        p.end()

    # ------------------------------------------------------------ poll
    def _do_poll_media(self) -> None:
        np = self.providers.media.refresh()
        self._last_np = np
        self.activities.update_media(np)
        self._maybe_request_lyrics(np)

    def _maybe_request_lyrics(self, np) -> None:
        if not getattr(np, "available", False) or not np.title:
            return
        key = f"{np.title}|{np.artist}|{int(np.length or 0)}"
        if key == self._lyrics_track:
            return
        self._lyrics_track = key
        self.lyrics.request(np)
        self.activities.set_lyrics(LyricsResult(
            status="loading", title=np.title, artist=np.artist or ""))

    def _do_poll_lyrics(self) -> None:
        res = self.lyrics.poll()
        if res is not None:
            self.activities.set_lyrics(res)

    def _on_lyrics_seek(self, seconds: float) -> None:
        self.providers.media.seek(seconds)

    def _on_seek(self, frac: float) -> None:
        np = self._last_np
        if np and np.available and np.length > 0:
            self.providers.media.seek(frac * np.length)

    def _on_shuffle(self) -> None:
        np = self._last_np
        if np and np.available:
            self.providers.media.set_shuffle(not np.shuffle)

    def _on_loop(self) -> None:
        np = self._last_np
        if np and np.available:
            self.providers.media.cycle_loop()

    def _do_poll_sys(self) -> None:
        import time as _time

        self.sys_state = self.providers.system.read(self.sys_state)
        st = self.sys_state

        # HUD volume: perubahan dari tombol keyboard / mixer lain
        if self._last_vol is not None and st.volume != self._last_vol:
            if _time.monotonic() - self._vol_set_at > C.HUD_SUPPRESS_MS / 1000.0:
                self.activities.sneak_peek("hud-vol", f"Volume  {st.volume}%", "♪",
                                           C.HUD_MS, 20)
        self._last_vol = st.volume

        # HUD brightness (bila sysfs tersedia)
        if st.brightness >= 0:
            if self._last_bright is not None and st.brightness != self._last_bright:
                self.activities.sneak_peek("hud-bright", f"Brightness  {st.brightness}%",
                                           "☀", C.HUD_MS, 20)
            self._last_bright = st.brightness

        self._check_battery_alerts(st)
        self.activities.update_system(st)

    def _check_battery_alerts(self, st) -> None:
        if not st.battery_present:
            return
        # transisi pengisian
        if self._last_charging is not None and st.charging != self._last_charging:
            if st.charging:
                self.activities.sneak_peek("toast", "Mengisi daya", "⚡", C.HUD_MS, 18)
            else:
                self.activities.sneak_peek("toast", "Daya dicabut", "●", C.HUD_MS, 18)
        self._last_charging = st.charging

        # baterai lemah / penuh (sekali per sesi)
        if st.battery_percent <= C.BATTERY_LOW and not st.charging:
            if not self._bat_low_alerted:
                self._bat_low_alerted = True
                self.activities.sneak_peek(
                    "toast", f"Baterai lemah: {st.battery_percent}%", "●", C.TOAST_MS, 26)
        elif st.battery_percent >= C.BATTERY_REARM:
            self._bat_low_alerted = False

        if st.charging and st.battery_percent >= C.BATTERY_FULL:
            if not self._bat_full_alerted:
                self._bat_full_alerted = True
                self.activities.sneak_peek(
                    "toast", f"Baterai penuh: {st.battery_percent}%", "⚡", C.TOAST_MS, 26)
        elif st.battery_percent < 95 or not st.charging:
            self._bat_full_alerted = False

    def _do_poll_weather(self) -> None:
        self.weather.refresh_async()
        self.activities.update_weather(self.weather.data)

    def _do_poll_audio(self) -> None:
        try:
            events = self.providers.audio_out.poll()
        except Exception:
            return
        for kind, label in events:
            self._on_audio_event(kind, label)

    def _on_audio_event(self, kind: str, label: str) -> None:
        if kind == "plug":
            text = f"Headset tersambung · {label}"
        else:
            text = f"Headset dicabut · {label}"
        if self._t > 0.5:
            # panel sedang terbuka → cukup flash di footer, jangan ganggu tab
            self.activities.flash_footer(text)
        else:
            self.activities.headset_event(kind, label)
            self._pill_pop()

    def _do_poll_downloads(self) -> None:
        self.downloads.scan()
        for kind, name in self.downloads.take_events():
            if kind == "started":
                self.activities.sneak_peek("toast", f"Mengunduh: {name}", "⬇", C.TOAST_MS, 16)
            elif kind == "finished":
                self.activities.sneak_peek("toast", f"Unduhan selesai: {name}", "✓", C.TOAST_MS, 16)
        self.activities.update_downloads(list(self.downloads.active.values()))

    def _on_volume_slider(self, value: int) -> None:
        import time as _time

        self._vol_set_at = _time.monotonic()
        self.providers.system.set_volume(value)
        self._last_vol = value  # jangan HUD untuk perubahan dari slider sendiri

    def _emit_notif(self, summary: str, body: str) -> None:
        # dipanggil dari thread D-Bus → teruskan ke main loop Qt
        self.notif_received.emit(summary, body)

    def _on_notif(self, summary: str, body: str) -> None:
        text = summary if not body else f"{summary} — {body}"
        self.activities.sneak_peek("toast", text, "✦", C.TOAST_MS, 25)

    def _do_poll_clock(self) -> None:
        self.sys_state = self.providers.system.read(self.sys_state)
        self.activities.update_clock(self.sys_state)


def run_qt() -> int:
    if sys.platform.startswith("linux"):
        # Wayland murni tak bisa mem-posisikan window tanpa layer-shell;
        # X11/Xwayland menjaga pill tetap top-center (sama seperti versi GTK)
        import os

        os.environ.setdefault("QT_QPA_PLATFORM", "xcb")

    app = QApplication(sys.argv)
    app.setApplicationName("notchy")

    import os as _os
    from PySide6.QtGui import QIcon as _QIcon

    _icon_path = _os.path.normpath(_os.path.join(
        _os.path.dirname(_os.path.abspath(__file__)), "..", "..", "assets", "notchy-icon.png"))
    if _os.path.isfile(_icon_path):
        app.setWindowIcon(_QIcon(_icon_path))
    app.setQuitOnLastWindowClosed(True)

    win = IslandWindow()
    win.setWindowOpacity(0.0)
    win.show()

    # fade-in halus saat aplikasi mulai
    fade = QPropertyAnimation(win, b"windowOpacity")
    fade.setDuration(280)
    fade.setEasingCurve(QEasingCurve.OutCubic)
    fade.setStartValue(0.0)
    fade.setEndValue(1.0)
    fade.start()
    win._fade_in = fade  # cegah garbage collection

    return app.exec()
