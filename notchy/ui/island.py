"""Island window Qt — cross-platform (Linux X11/Xwayland + Windows).

Padanan temuan REA boring.notch:
  BoringNotchSkyLightWindow → frameless + stay-on-top + top-center
  NotchState closed↔open     → QPropertyAnimation geometry (OutCubic)
  openNotchOnHover           → enter/leave event
  closeNotchTask             → QTimer penutupan otomatis
"""
from __future__ import annotations

import sys

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QRect, Qt, QTimer
from PySide6.QtGui import QColor, QCursor, QPainter, QPen
from PySide6.QtWidgets import QApplication, QMenu, QWidget

from .. import config as C
from ..providers import make_providers
from .activities import Activities
from .style import ISLAND_QSS

SHADOW_PAD = 0  # tanpa shadow — island = kotak murni


class IslandWindow(QWidget):
    def __init__(self) -> None:
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setObjectName("Island")
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, False)
        self.setWindowTitle("notchy")

        self.providers = make_providers()
        from ..providers.base import SystemState

        self.sys_state = SystemState()

        self.activities = Activities(self)
        self.activities.setObjectName("island-bg")
        self.setStyleSheet(ISLAND_QSS)

        # tata letak isi di dalam padding bayangan
        self._layout_content(C.CLOSED_W, C.CLOSED_H)

        # animasi morph
        self._anim = QPropertyAnimation(self, b"geometry")
        self._anim.setDuration(C.ANIM_MS)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim.valueChanged.connect(self._on_anim_frame)

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

        self.activities.play_pause_clicked.connect(self.providers.media.play_pause)
        self.activities.next_clicked.connect(self.providers.media.next)
        self.activities.prev_clicked.connect(self.providers.media.previous)
        self.activities.volume_changed.connect(self.providers.system.set_volume)

        self._do_poll_media()
        self._do_poll_sys()
        self._do_poll_clock()
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
        # saat animasi morph jendela bergeser → leaveEvent palsu sering terpicu;
        # abaikan, dan verifikasi posisi kursor sebelum menjadwalkan tutup
        if self._anim.state() == QPropertyAnimation.Running:
            super().leaveEvent(ev)
            return
        self._pointer_inside = False
        self._close_timer.start()
        super().leaveEvent(ev)

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
        self.activities.update_media(np)

    def _do_poll_sys(self) -> None:
        self.sys_state = self.providers.system.read(self.sys_state)
        self.activities.update_system(self.sys_state)

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
    app.setQuitOnLastWindowClosed(True)

    win = IslandWindow()
    win.show()
    return app.exec()
