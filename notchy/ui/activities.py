"""Konten island Qt: compact cluster ↔ expanded bento (Alcove-style glass)."""
from __future__ import annotations

import math
import os
import random
import time

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .. import art as art_loader
from .. import config as C


def fmt_time(seconds: float) -> str:
    if not seconds or seconds < 0:
        return "0:00"
    m, s = divmod(int(seconds), 60)
    if m >= 60:
        h, m = divmod(m, 60)
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def color_from_text(text: str) -> str:
    h = 0
    for ch in text:
        h = (h * 131 + ord(ch)) & 0xFFFFFFFF
    palette = ["#4C6EF5", "#7C5CFF", "#E64980", "#F76707", "#0CA678", "#1098AD", "#AE3EC9"]
    return palette[h % len(palette)]


class ElidedLabel(QLabel):
    """QLabel dengan elipsis akhir — padanan Pango.EllipsizeMode.END di versi GTK."""

    def __init__(self, text: str = "", parent=None) -> None:
        super().__init__(text, parent)
        self._full_text = text
        # Abaikan sizeHint untuk lebar: teks yang berubah-ubah tidak boleh
        # membuat layout di sekitarnya ikut membesar/mengecil.
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)

    def set_full_text(self, text: str) -> None:
        self._full_text = text
        self._apply()

    def resizeEvent(self, ev) -> None:
        super().resizeEvent(ev)
        self._apply()

    def _apply(self) -> None:
        if not hasattr(self, "_full_text"):
            return
        metrics = self.fontMetrics()
        elided = metrics.elidedText(self._full_text, Qt.ElideRight, max(8, self.width()))
        super().setText(elided)

    def full_text(self) -> str:
        return getattr(self, "_full_text", self.text())


ASSETS_DIR = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "assets"))
LOGO_ICON = os.path.join(ASSETS_DIR, "notchy-icon.png")


class LyricRow(QWidget):
    """Baris lirik: latar pill digambar QPainter (satu-satunya background).
    Anak-anaknya (teks & waktu) murni transparan — tanpa QSS background."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._active = False
        self.setAttribute(Qt.WA_StyledBackground, False)
        self.setAutoFillBackground(False)

    def set_active(self, active: bool) -> None:
        if self._active != active:
            self._active = active
            self.update()

    def paintEvent(self, ev) -> None:
        if not self._active:
            return
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QColor, QPainter

        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(155, 135, 255, 51))   # 0.20 alpha
        p.drawRoundedRect(self.rect(), 9, 9)
        p.end()


class EyesWidget(QWidget):
    """Mata maskot untuk state idle (ala Nusa): berkedip, mengantuk, bangun saat hover."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedSize(30, 22)
        self._t = 0.0
        self._blink_at = 2.5 + random.random() * 2.5
        self._blink = 0.0
        self._open = 1.0
        self._last_wake = time.monotonic()
        self._timer = QTimer(self)
        self._timer.setInterval(60)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    def wake(self) -> None:
        self._last_wake = time.monotonic()
        self._open = 1.0
        self.update()

    def _tick(self) -> None:
        self._t += 0.06
        if self._t > self._blink_at:
            self._blink = 1.0
            self._blink_at = self._t + 2.8 + random.random() * 3.2
        if self._blink > 0:
            self._blink = max(0.0, self._blink - 0.14)
        idle_for = time.monotonic() - self._last_wake
        target = 0.32 if idle_for > 35 else 1.0
        self._open += (target - self._open) * 0.07
        self.update()

    def paintEvent(self, ev) -> None:
        from PySide6.QtCore import QPointF, QRectF, Qt
        from PySide6.QtGui import QColor, QPainter

        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        w, h = self.width(), self.height()
        openness = max(0.12, self._open * (1.0 - 0.88 * self._blink))
        eye_w = 9.0
        eye_h = 12.0 * openness
        look = math.sin(self._t * 0.8) * 1.4
        for cx in (w * 0.32, w * 0.68):
            rect = QRectF(cx - eye_w / 2, h / 2 - eye_h / 2, eye_w, max(1.6, eye_h))
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(228, 225, 233, 235))
            p.drawRoundedRect(rect, eye_w / 2, eye_w / 2)
            if openness > 0.55:
                pr = 2.1
                p.setBrush(QColor(24, 22, 34, 255))
                p.drawEllipse(QPointF(cx + look, h / 2), pr, pr)
        p.end()


class EventOverlay(QWidget):
    """Efek 'wow' event headset: sonar rings + kilau sapuan + headphone
    yang menggambar diri mengelilingi logo. Digambar manual (QPainter),
    tanpa QGraphicsEffect agar tidak bentrok dengan effect milik parent."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self._kind = "plug"
        self._u = 0.0
        self._start = 0.0
        self._dur = 2.4
        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._tick)
        self.hide()

    def play(self, kind: str, ms: int = 2400) -> None:
        self._kind = kind
        self._start = time.monotonic()
        self._dur = max(0.4, ms / 1000.0)
        self._u = 0.0
        self._timer.start()
        self.show()
        self.raise_()
        self.update()

    def _tick(self) -> None:
        u = (time.monotonic() - self._start) / self._dur
        if u >= 1.0:
            self._timer.stop()
            self.hide()
            return
        self._u = u
        self.update()

    @staticmethod
    def _accent(kind: str):
        from PySide6.QtGui import QColor

        return QColor(110, 139, 255) if kind == "plug" else QColor(255, 107, 157)

    def paintEvent(self, ev) -> None:
        if self._u <= 0.0:
            return
        from PySide6.QtCore import QPointF, QRectF, Qt
        from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPen, QRadialGradient

        u = self._u
        w, h = self.width(), self.height()
        accent = self._accent(self._kind)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)

        # 1) kilau menyapu sepanjang pill
        direction = 1.0 if self._kind == "plug" else -1.0
        pos = (-0.25 + u * 1.5) if direction > 0 else (1.25 - u * 1.5)
        gx = pos * w
        grad = QLinearGradient(gx - 70, 0, gx + 70, 0)
        grad.setColorAt(0.0, QColor(accent.red(), accent.green(), accent.blue(), 0))
        grad.setColorAt(0.5, QColor(accent.red(), accent.green(), accent.blue(), 42))
        grad.setColorAt(1.0, QColor(accent.red(), accent.green(), accent.blue(), 0))
        p.fillRect(0, 0, w, h, grad)

        # 2) sonar rings dari logo
        cx, cy = 25.0, h / 2.0
        for i in range(3):
            tt = (u * 1.9 + i * 0.27) % 1.0
            r = 10.0 + tt * 72.0
            a = int(150 * (1.0 - tt))
            pen = QPen(QColor(accent.red(), accent.green(), accent.blue(), a), 1.6)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(QPointF(cx, cy), r, r)

        # 3) headphone menggambar diri mengelilingi logo (wipe reveal)
        reveal = min(1.0, u / 0.42)
        p.save()
        from PySide6.QtCore import QRectF as _R
        p.setClipRect(_R(0, 0, 14 + 34 * reveal, h))
        self._draw_headphone(p, cx, cy, accent)
        p.restore()

        # 4) glow lembut di belakang logo
        pulse = max(0.0, 1.0 - abs(u * 2.4 - 0.6))
        if pulse > 0.01:
            rg = QRadialGradient(cx, cy, 42)
            rg.setColorAt(0.0, QColor(accent.red(), accent.green(), accent.blue(),
                                      int(120 * pulse)))
            rg.setColorAt(1.0, QColor(accent.red(), accent.green(), accent.blue(), 0))
            p.setPen(Qt.NoPen)
            p.setBrush(rg)
            p.drawEllipse(QPointF(cx, cy), 42, 42)

        p.end()

    @staticmethod
    def _draw_headphone(p, cx: float, cy: float, accent) -> None:
        import math as _m

        from PySide6.QtCore import QPointF as _P, QRectF as _R, Qt as _Qt
        from PySide6.QtGui import QPainterPath as _Path, QPen as _Pen, QColor as _C

        r = 12.5
        pen = _Pen(accent, 2.6)
        pen.setCapStyle(_Qt.RoundCap)
        p.setPen(pen)
        p.setBrush(_Qt.NoBrush)
        rect = _R(cx - r, cy - r, 2 * r, 2 * r)
        p.drawArc(rect, 200 * 16, -220 * 16)
        p.setPen(_Qt.NoPen)
        p.setBrush(_C(accent.red(), accent.green(), accent.blue(), 235))
        for ang in (200.0, -20.0):
            rad = _m.radians(ang)
            x = cx + r * _m.cos(rad)
            y = cy - r * _m.sin(rad)
            p.drawRoundedRect(_R(x - 2.8, y - 4.6, 5.6, 9.2), 2.4, 2.4)


class Activities(QWidget):
    volume_changed = Signal(int)
    play_pause_clicked = Signal()
    next_clicked = Signal()
    prev_clicked = Signal()
    seek_requested = Signal(float)      # 0..1 dari progress bar
    shuffle_clicked = Signal()
    loop_clicked = Signal()
    lyrics_seek = Signal(float)         # detik absolut dari klik baris lirik

    def __init__(self, timer=None, parent=None) -> None:
        super().__init__(parent)
        # WA_StyledBackground: wajib agar QSS #island-bg terpaint pada QWidget custom
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.timer = timer
        self._has_media = False
        self._playing = False
        self._art_url = ""
        self._art_loaded_url = ""
        self._art_size = 104
        self._sys_hint = "…"
        self._wave_level = 0.0
        self._frac = 0.0

        # --- display prioritas pill: peek (toast/hud) > timer > musik ---
        self._base_title = "notchy"
        self._base_icon = "●"
        self._peek: dict[str, tuple] = {}   # kind -> (prio, text, icon, expire_ms)
        self._peek_timer = QTimer(self)
        self._peek_timer.setSingleShot(True)
        self._peek_timer.timeout.connect(self._peek_expire)

        # Tanpa layout root: compact & expanded diposisikan manual di resizeEvent
        # supaya widget yang sedang di-fade tidak menghimpit yang lain (bug clip).
        self.compact = self._build_compact()
        self.expanded = self._build_expanded()
        self.compact.setParent(self)
        self.expanded.setParent(self)

        self._fx = EventOverlay(self)

        self._compact_fx = QGraphicsOpacityEffect(self.compact)
        self.compact.setGraphicsEffect(self._compact_fx)
        self._expanded_fx = QGraphicsOpacityEffect(self.expanded)
        self.expanded.setGraphicsEffect(self._expanded_fx)

        self._wave_timer = QTimer(self)
        self._wave_timer.setInterval(C.WAVE_TICK_MS)
        self._wave_timer.timeout.connect(self._wave_tick)

        # --- state animasi mikro ---
        self._pulse_phase = 0.0
        self._scrub_anim = None
        self._dl_phase = 0.0

        self._badge_pulse_t = QTimer(self)
        self._badge_pulse_t.setInterval(160)
        self._badge_pulse_t.timeout.connect(self._badge_pulse)

        self._wx_pulse_t = QTimer(self)
        self._wx_pulse_t.setInterval(140)
        self._wx_pulse_t.timeout.connect(self._wx_pulse)

        self._wx_pulse_t.start()

        self._dl_marquee_t = QTimer(self)
        self._dl_marquee_t.setInterval(40)
        self._dl_marquee_t.timeout.connect(self._dl_marquee_tick)

        self._progress_tick_t = QTimer(self)
        self._progress_tick_t.setInterval(250)
        self._progress_tick_t.timeout.connect(self._progress_tick)
        self._progress_tick_t.start()

        self._lyrics_tick_t = QTimer(self)
        self._lyrics_tick_t.setInterval(250)
        self._lyrics_tick_t.timeout.connect(self._lyrics_tick)
        self._lyrics_tick_t.start()

        self._timer_blink_t = QTimer(self)
        self._timer_blink_t.setInterval(550)
        self._timer_blink_on = False
        self._timer_blink_t.timeout.connect(self._timer_blink_tick)

        if self.timer is not None:
            self.timer.changed.connect(self._on_timer_changed)
            self.timer.finished.connect(lambda: self.sneak_peek(
                "toast", f"{self.timer.label} selesai", "⏱", C.TOAST_MS, 30))

        self.set_opacity_for(0.0)

    def _note_icons(self, height: int = 13, count: int = 3):
        """Deretan ikon not balok untuk baris lirik kosong (instrumental)."""
        key = (height, count)
        cached = getattr(self, "_note_pm_cache", None)
        if cached and cached[0] == key:
            return cached[1], cached[2]
        from PySide6.QtGui import QColor, QPainter

        pm0 = QPixmap(os.path.join(ASSETS_DIR, "music-icon.png"))
        if pm0.isNull():
            return None, None
        icon = pm0.scaledToHeight(height, Qt.SmoothTransformation)
        gap = 7
        total_w = count * icon.width() + (count - 1) * gap

        def compose(color: "QColor") -> "QPixmap":
            out = QPixmap(total_w, height)
            out.fill(Qt.transparent)
            p = QPainter(out)
            for i in range(count):
                p.drawPixmap(i * (icon.width() + gap), 0, icon)
            p.setCompositionMode(QPainter.CompositionMode_SourceIn)
            p.fillRect(out.rect(), color)
            p.end()
            return out

        # QColor(155,155,170,190) — light gray lembut; aktif biru sama dgn teks lirik
        dim = compose(QColor(155, 155, 170, 190))
        active = compose(QColor(110, 139, 255, 255))
        self._note_pm_cache = (key, dim, active)
        return dim, active

    def _logo_pixmap(self, height: int) -> QPixmap:
        pm = QPixmap(LOGO_ICON)
        if pm.isNull():
            return pm
        return pm.scaledToHeight(height, Qt.SmoothTransformation)

    # ============================================================ COMPACT
    def _build_compact(self) -> QWidget:
        row = QWidget()
        lay = QHBoxLayout(row)
        lay.setContentsMargins(12, 0, 12, 0)
        lay.setSpacing(9)

        # slot kiri: art album (saat playing) atau mata maskot (idle)
        self.compact_slot = QStackedWidget()
        self.compact_slot.setFixedSize(34, 34)

        self.compact_art = QLabel()
        self.compact_art.setObjectName("c-art")
        self.compact_art.setAlignment(Qt.AlignCenter)
        self.compact_art.setFixedSize(32, 32)
        self.compact_slot.addWidget(self.compact_art)

        self.compact_eyes = EyesWidget()
        self.compact_slot.addWidget(self.compact_eyes)
        lay.addWidget(self.compact_slot)

        # judul + subjudul
        col = QVBoxLayout()
        col.setSpacing(0)
        col.setContentsMargins(0, 0, 0, 0)
        self.compact_title = ElidedLabel("notchy")
        self.compact_title.setObjectName("c-title")
        self.compact_title.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        col.addWidget(self.compact_title)
        self.compact_sub = ElidedLabel("")
        self.compact_sub.setObjectName("c-sub")
        self.compact_sub.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        col.addWidget(self.compact_sub)
        lay.addLayout(col, 1)

        self.compact_wave = self._make_wave(4, base=16)
        lay.addWidget(self.compact_wave)

        self.compact_clock = QLabel("--:--")
        self.compact_clock.setObjectName("c-time-chip")
        self.compact_clock.setAlignment(Qt.AlignCenter)
        self.compact_clock.setFixedHeight(22)
        lay.addWidget(self.compact_clock)

        # referensi agar tetap aman saat update (tidak tampil di compact)
        self.compact_bat = QLabel("")
        self.compact_bat.hide()
        self.compact_temp = QLabel("")
        self.compact_temp.hide()
        return row

    # ============================================================ EXPANDED
    def _build_expanded(self) -> QWidget:
        box = QWidget()
        lay = QVBoxLayout(box)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(10)

        # ---------- header tab: ‹  [ikon judul ●○○]  › ----------
        header = QHBoxLayout()
        header.setSpacing(8)

        self.tab_prev = QLabel("‹")
        self.tab_prev.setObjectName("tab-arrow")
        self.tab_prev.setAlignment(Qt.AlignCenter)
        self.tab_prev.setFixedSize(30, 30)
        self.tab_prev.setToolTip("Tab sebelumnya")
        self.tab_prev.installEventFilter(self)
        self.tab_prev.setProperty("tab_delta", -1)
        header.addWidget(self.tab_prev)

        self.tab_logo = QLabel()
        self.tab_logo.setObjectName("tab-logo")
        pm = self._logo_pixmap(18)
        if not pm.isNull():
            self.tab_logo.setPixmap(pm)
        mid = QWidget()
        mlay = QHBoxLayout(mid)
        mlay.setContentsMargins(0, 0, 0, 0)
        mlay.setSpacing(8)
        mlay.addStretch(1)
        mlay.addWidget(self.tab_logo)
        self.tab_title = QLabel("Musik")
        self.tab_title.setObjectName("tab-title")
        self.tab_title.setAlignment(Qt.AlignCenter)
        mlay.addWidget(self.tab_title)
        mlay.addStretch(1)
        header.addWidget(mid, 1)

        self.tab_dots = QLabel("●○")
        self.tab_dots.setObjectName("tab-dots")
        self.tab_dots.setAlignment(Qt.AlignCenter)
        header.addWidget(self.tab_dots)

        self.tab_next = QLabel("›")
        self.tab_next.setObjectName("tab-arrow")
        self.tab_next.setAlignment(Qt.AlignCenter)
        self.tab_next.setFixedSize(30, 30)
        self.tab_next.setToolTip("Tab berikutnya")
        self.tab_next.installEventFilter(self)
        self.tab_next.setProperty("tab_delta", 1)
        header.addWidget(self.tab_next)

        lay.addLayout(header)

        # ---------- halaman tab ----------
        self.pages = QStackedWidget()
        self.pages.addWidget(self._build_page_music())
        self.pages.addWidget(self._build_page_system())
        self.pages.addWidget(self._build_page_info())
        lay.addWidget(self.pages, 1)

        # ---------- footer (tetap di semua tab) ----------
        footer = QFrame()
        footer.setObjectName("footer")
        flay = QHBoxLayout(footer)
        flay.setContentsMargins(12, 8, 12, 8)
        flay.setSpacing(10)

        self.footer_wave = self._make_wave(18, base=18)
        flay.addWidget(self.footer_wave)

        self.now_label = ElidedLabel("")
        self.now_label.setObjectName("foot-note")
        flay.addWidget(self.now_label, 1)

        clock_box = QVBoxLayout()
        clock_box.setSpacing(0)
        self.clock_label = QLabel("--:--")
        self.clock_label.setObjectName("big-clock")
        self.clock_label.setAlignment(Qt.AlignRight)
        self.clock_label.setFixedWidth(80)
        self.date_label = QLabel("")
        self.date_label.setObjectName("t-tiny")
        self.date_label.setAlignment(Qt.AlignRight)
        self.date_label.setFixedWidth(80)
        clock_box.addWidget(self.clock_label)
        clock_box.addWidget(self.date_label)
        flay.addLayout(clock_box)

        divider = QFrame()
        divider.setObjectName("divider")
        lay.addWidget(divider)

        lay.addWidget(footer)

        self._tab_index = 0
        self._tab_names = ("Musik", "Sistem", "Info")
        return box

    # ============================================================ PAGE: MUSIK
    def _build_music_normal(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        # header row ala design: ♪ NOW PLAYING · source   |   chip Lyrics
        toprow = QHBoxLayout()
        toprow.setSpacing(8)
        self.np_tag = QLabel("♪  NOW PLAYING")
        self.np_tag.setObjectName("np-tag")
        toprow.addWidget(self.np_tag)
        self.np_source = QLabel("—")
        self.np_source.setObjectName("np-src")
        toprow.addWidget(self.np_source)
        toprow.addStretch(1)

        self.lyrics_chip = QFrame()
        self.lyrics_chip.setObjectName("chip-btn")
        self.lyrics_chip.setCursor(Qt.PointingHandCursor)
        self.lyrics_chip.installEventFilter(self)
        self.lyrics_chip.setProperty("lyrics_toggle", True)
        _cl = QHBoxLayout(self.lyrics_chip)
        _cl.setContentsMargins(9, 0, 11, 0)
        _cl.setSpacing(6)
        _lic = QLabel()
        _lpm = QPixmap(os.path.join(ASSETS_DIR, "lyrics-icon.png"))
        if not _lpm.isNull():
            _lic.setPixmap(_lpm.scaledToHeight(12, Qt.SmoothTransformation))
        _cl.addWidget(_lic)
        _ltxt = QLabel("Lyrics")
        _ltxt.setObjectName("chip-btn-txt")
        _cl.addWidget(_ltxt)
        toprow.addWidget(self.lyrics_chip)
        lay.addLayout(toprow)

        hero = QFrame()
        hero.setObjectName("hero")
        hlay = QHBoxLayout(hero)
        hlay.setContentsMargins(14, 14, 14, 14)
        hlay.setSpacing(16)

        # art lebih besar (design: 104)
        self.art_label = QLabel("♪")
        self.art_label.setFixedSize(104, 104)
        self.art_label.setAlignment(Qt.AlignCenter)
        self.art_label.setStyleSheet(
            f"background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 {C.ACCENT_DEEP},"
            f" stop:1 #7C5CFF); border-radius: 18px; color: rgba(255,255,255,0.85);"
            f" font: 700 30px Sans;"
        )
        hlay.addWidget(self.art_label, 0, Qt.AlignVCenter)

        info = QVBoxLayout()
        info.setSpacing(5)

        top = QHBoxLayout()
        self.title = ElidedLabel("Tidak ada musik")
        self.title.setObjectName("h-title")
        top.addWidget(self.title, 1)
        self.badge = QLabel("IDLE")
        self.badge.setObjectName("badge")
        top.addWidget(self.badge, 0, Qt.AlignRight)
        info.addLayout(top)

        self.artist = ElidedLabel("Putar sesuatu di pemutar favoritmu")
        self.artist.setObjectName("h-sub")
        info.addWidget(self.artist)

        # chips meta: sumber · album · status
        chips = QHBoxLayout()
        chips.setSpacing(6)
        self.chip_source = QLabel("—")
        self.chip_source.setObjectName("t-chip")
        self.chip_album = QLabel("—")
        self.chip_album.setObjectName("t-chip")
        self.chip_state = QLabel("idle")
        self.chip_state.setObjectName("t-chip")
        for c in (self.chip_source, self.chip_album, self.chip_state):
            c.setAlignment(Qt.AlignCenter)
            c.setFixedSize(92, 22)
            chips.addWidget(c)
        chips.addStretch(1)
        # chips tidak ditampilkan lagi (design lebih bersih)

        info.addSpacing(6)

        # scrub seekable (klik / drag untuk lompat posisi)
        self.scrub = QFrame()
        self.scrub.setObjectName("scrub")
        self.scrub.setFixedHeight(6)
        self.scrub.setCursor(Qt.PointingHandCursor)
        self.scrub.installEventFilter(self)
        self.scrub_fill = QFrame(self.scrub)
        self.scrub_fill.setObjectName("scrub-fill")
        self.scrub_fill.setGeometry(0, 0, 0, 6)
        info.addWidget(self.scrub)

        times = QHBoxLayout()
        self.time_now = QLabel("0:00")
        self.time_now.setObjectName("t-tiny")
        self.time_now.setFixedWidth(40)
        self.time_len = QLabel("0:00")
        self.time_len.setObjectName("t-tiny")
        self.time_len.setFixedWidth(40)
        self.seek_hint = QLabel("")
        self.seek_hint.hide()
        times.addWidget(self.time_now)
        times.addStretch(1)
        times.addWidget(self.time_len)
        info.addLayout(times)

        hlay.addLayout(info, 1)
        lay.addWidget(hero)

        # baris kontrol ala design: ⇄ ⏮ [play besar] ⏭ ↻
        ctl_row = QHBoxLayout()
        ctl_row.setSpacing(12)

        self.btn_shuffle = QLabel("⇄")
        self.btn_shuffle.setObjectName("toggle-btn")
        self.btn_shuffle.setAlignment(Qt.AlignCenter)
        self.btn_shuffle.setFixedSize(40, 34)
        self.btn_shuffle.setToolTip("Shuffle")
        self.btn_shuffle.installEventFilter(self)
        self.btn_shuffle.setProperty("media_action", "shuffle")
        ctl_row.addWidget(self.btn_shuffle)

        btn_prev = QLabel("⏮")
        btn_prev.setObjectName("seg-btn")
        btn_prev.setAlignment(Qt.AlignCenter)
        btn_prev.setFixedSize(40, 34)
        btn_prev.setToolTip("Sebelumnya")
        btn_prev.installEventFilter(self)
        btn_prev.setProperty("sig", self.prev_clicked)
        ctl_row.addWidget(btn_prev)

        self.btn_play_big = QLabel("▶")
        self.btn_play_big.setObjectName("play-big")
        self.btn_play_big.setAlignment(Qt.AlignCenter)
        self.btn_play_big.setFixedSize(52, 52)
        self.btn_play_big.setToolTip("Play / Pause")
        self.btn_play_big.installEventFilter(self)
        self.btn_play_big.setProperty("sig", self.play_pause_clicked)
        ctl_row.addWidget(self.btn_play_big)

        btn_next = QLabel("⏭")
        btn_next.setObjectName("seg-btn")
        btn_next.setAlignment(Qt.AlignCenter)
        btn_next.setFixedSize(40, 34)
        btn_next.setToolTip("Berikutnya")
        btn_next.installEventFilter(self)
        btn_next.setProperty("sig", self.next_clicked)
        ctl_row.addWidget(btn_next)

        self.btn_loop = QLabel("↻")
        self.btn_loop.setObjectName("toggle-btn")
        self.btn_loop.setAlignment(Qt.AlignCenter)
        self.btn_loop.setFixedSize(40, 34)
        self.btn_loop.setToolTip("Repeat: None → Playlist → Track")
        self.btn_loop.installEventFilter(self)
        self.btn_loop.setProperty("media_action", "loop")
        ctl_row.addWidget(self.btn_loop)

        ctl_row.addStretch(1)
        lay.addLayout(ctl_row)

        # waveform besar sebagai centerpiece
        wave_card = QFrame()
        wave_card.setObjectName("footer")
        wlay = QHBoxLayout(wave_card)
        wlay.setContentsMargins(14, 10, 14, 10)
        wlay.setSpacing(10)
        self.music_wave = self._make_wave(34, base=40, bar_w=4)
        wlay.addStretch(1)
        wlay.addWidget(self.music_wave)
        wlay.addStretch(1)
        self.music_status = QLabel("")
        self.music_status.hide()
        lay.addWidget(wave_card)

        lay.addStretch(1)
        return page

    def _build_page_music(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self.music_stack = QStackedWidget()
        self.music_stack.addWidget(self._build_music_normal())
        self.music_stack.addWidget(self._build_music_lyrics())
        lay.addWidget(self.music_stack)
        return page

    # ============================================================ LIRIK
    def _build_music_lyrics(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        # ---------- header: art + judul/dot + artist/album + chip Music View ----------
        header = QHBoxLayout()
        header.setSpacing(10)

        self.art2 = QLabel("♪")
        self.art2.setFixedSize(40, 40)
        self.art2.setAlignment(Qt.AlignCenter)
        self.art2.setStyleSheet(
            f"background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 {C.ACCENT_DEEP},"
            f" stop:1 {C.ACCENT2}); border-radius: 10px; color: rgba(255,255,255,0.85);"
            f" font-weight: 700; font-size: 16px; font-family: Sans;")
        header.addWidget(self.art2)

        meta = QVBoxLayout()
        meta.setSpacing(1)
        trow = QHBoxLayout()
        trow.setSpacing(6)
        self.title2 = ElidedLabel("—")
        self.title2.setObjectName("lyr-title")
        trow.addWidget(self.title2, 1)
        self.dot2 = QLabel("●")
        self.dot2.setObjectName("lyr-dot")
        trow.addWidget(self.dot2)
        trow.addStretch(0)
        meta.addLayout(trow)
        self.artist2 = ElidedLabel("")
        self.artist2.setObjectName("lyr-sub")
        meta.addWidget(self.artist2)
        header.addLayout(meta, 1)

        self.btn_back = QFrame()
        self.btn_back.setObjectName("chip-btn")
        self.btn_back.setCursor(Qt.PointingHandCursor)
        self.btn_back.installEventFilter(self)
        self.btn_back.setProperty("lyrics_toggle", True)
        bl = QHBoxLayout(self.btn_back)
        bl.setContentsMargins(10, 0, 12, 0)
        bl.setSpacing(6)
        _bpm = QPixmap(os.path.join(ASSETS_DIR, "music-icon.png"))
        _bic = QLabel()
        if not _bpm.isNull():
            _bic.setPixmap(_bpm.scaledToHeight(12, Qt.SmoothTransformation))
        bl.addWidget(_bic)
        _btxt = QLabel("Music View")
        _btxt.setObjectName("chip-btn-txt")
        bl.addWidget(_btxt)
        header.addWidget(self.btn_back)
        lay.addLayout(header)

        # ---------- daftar lirik ----------
        self.lyrics_scroll = QScrollArea()
        self.lyrics_scroll.setWidgetResizable(True)
        self.lyrics_scroll.setFrameShape(QFrame.NoFrame)
        self.lyrics_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.lyrics_scroll.setObjectName("lyrics-scroll")
        self.lyrics_scroll.viewport().setAutoFillBackground(False)
        self.lyrics_scroll.setStyleSheet("background: transparent;")
        self.lyrics_content = QWidget()
        self.lyrics_content.setAttribute(Qt.WA_StyledBackground, True)
        self.lyrics_content.setStyleSheet("background: transparent;")
        self.lyrics_layout = QVBoxLayout(self.lyrics_content)
        self.lyrics_layout.setContentsMargins(0, 4, 6, 4)
        self.lyrics_layout.setSpacing(6)
        self.lyrics_layout.addStretch(1)
        self.lyrics_scroll.setWidget(self.lyrics_content)
        self._scroll_programmatic = False
        self._user_scroll_until = 0.0
        self.lyrics_scroll.verticalScrollBar().valueChanged.connect(
            self._on_lyrics_scrolled)
        lay.addWidget(self.lyrics_scroll, 1)

        # ---------- progress ----------
        prow = QHBoxLayout()
        prow.setSpacing(8)
        self.time2_now = QLabel("0:00")
        self.time2_now.setObjectName("t-tiny")
        self.time2_now.setFixedWidth(36)
        prow.addWidget(self.time2_now)
        self.scrub2 = QFrame()
        self.scrub2.setObjectName("scrub")
        self.scrub2.setFixedHeight(5)
        self.scrub2_fill = QFrame(self.scrub2)
        self.scrub2_fill.setObjectName("scrub-fill")
        self.scrub2_fill.setGeometry(0, 0, 0, 5)
        prow.addWidget(self.scrub2, 1)
        self.time2_len = QLabel("0:00")
        self.time2_len.setObjectName("t-tiny")
        self.time2_len.setFixedWidth(36)
        self.time2_len.setAlignment(Qt.AlignRight)
        prow.addWidget(self.time2_len)
        lay.addLayout(prow)

        # ---------- kontrol bawah + chip sinkron ----------
        brow = QHBoxLayout()
        brow.setSpacing(10)

        bprev = QLabel("⏮")
        bprev.setObjectName("seg-btn")
        bprev.setAlignment(Qt.AlignCenter)
        bprev.setFixedSize(36, 30)
        bprev.installEventFilter(self)
        bprev.setProperty("sig", self.prev_clicked)
        brow.addWidget(bprev)

        self.btn_play_small = QLabel("▶")
        self.btn_play_small.setObjectName("play-small")
        self.btn_play_small.setAlignment(Qt.AlignCenter)
        self.btn_play_small.setFixedSize(36, 36)
        self.btn_play_small.installEventFilter(self)
        self.btn_play_small.setProperty("sig", self.play_pause_clicked)
        brow.addWidget(self.btn_play_small)

        bnext = QLabel("⏭")
        bnext.setObjectName("seg-btn")
        bnext.setAlignment(Qt.AlignCenter)
        bnext.setFixedSize(36, 30)
        bnext.installEventFilter(self)
        bnext.setProperty("sig", self.next_clicked)
        brow.addWidget(bnext)

        self.eq_bars = self._make_wave(3, base=14)
        brow.addWidget(self.eq_bars)

        brow.addStretch(1)

        self.sync_chip = QFrame()
        self.sync_chip.setObjectName("sync-chip")
        sl = QHBoxLayout(self.sync_chip)
        sl.setContentsMargins(9, 0, 11, 0)
        sl.setSpacing(6)
        self.sync_dot = QLabel("●")
        self.sync_dot.setObjectName("sync-dot")
        sl.addWidget(self.sync_dot)
        self.sync_text = QLabel("Tersinkron · LRCLIB")
        self.sync_text.setObjectName("chip-btn-txt")
        sl.addWidget(self.sync_text)
        brow.addWidget(self.sync_chip)
        lay.addLayout(brow)

        # state
        self._lyrics_mode = False
        self._lyric_labels = []
        self._lyric_rows = []
        self._lyrics_synced = False
        self._lyric_idx = -1
        self._pos_base = 0.0
        self._pos_t = 0.0
        self._pos_playing = False
        return page

    # ------------------------------------------------------------ lirik API
    def set_lyrics(self, result) -> None:
        # abaikan konten identik (hindari rebuild + reset scroll)
        sig = (bool(getattr(result, "synced", False)),
               tuple(getattr(result, "lines", []) or []),
               getattr(result, "status", ""))
        if sig == getattr(self, "_lyrics_sig", None):
            return
        self._lyrics_sig = sig

        # bersihkan baris lama
        while self.lyrics_layout.count():
            item = self.lyrics_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self._lyric_labels = []
        self._lyric_rows = []
        self._lyric_idx = -1
        self._user_scroll_until = 0.0
        try:
            self._scroll_programmatic = True
            self.lyrics_scroll.verticalScrollBar().setValue(0)
        finally:
            self._scroll_programmatic = False

        self._lyrics_synced = bool(getattr(result, "synced", False))
        lines = getattr(result, "lines", []) or []
        status = getattr(result, "status", "")

        # chip status sinkron
        if status == "loading":
            self.sync_text.setText("Mencari lirik…")
            self.sync_dot.setStyleSheet("color: #FBBF24;")
        elif not lines:
            self.sync_text.setText("Tidak tersedia")
            self.sync_dot.setStyleSheet("color: #6E6B7A;")
        elif not self._lyrics_synced:
            self.sync_text.setText("Tanpa sinkron")
            self.sync_dot.setStyleSheet("color: #6E6B7A;")
        else:
            self.sync_text.setText("Tersinkron · LRCLIB")
            self.sync_dot.setStyleSheet("color: #4ADE80;")

        if not lines:
            hint = QLabel("Lirik belum tersedia untuk lagu ini." if status != "loading"
                          else "Sedang mencari lirik…")
            hint.setObjectName("lyric-line")
            hint.setWordWrap(True)
            self.lyrics_layout.addWidget(hint)
            self.lyrics_layout.addStretch(1)
            return

        dim_pm, _active_pm = self._note_icons(13, 3)
        for idx, (t_sec, text) in enumerate(lines):
            row = LyricRow()
            rl = QHBoxLayout(row)
            rl.setContentsMargins(10, 4, 10, 4)
            rl.setSpacing(8)

            accent = QFrame()
            accent.setObjectName("lyr-accent")
            accent.setFixedWidth(4)
            accent.setStyleSheet("background: #9B87FF; border: none;")
            accent.hide()
            rl.addWidget(accent)

            lbl = QLabel()
            lbl.setObjectName("lyric-line")
            lbl.setAutoFillBackground(False)
            lbl.setStyleSheet("background: transparent; border: none;")
            is_note = not (text or "").strip()
            if is_note and dim_pm is not None:
                lbl.setPixmap(dim_pm)
                lbl.setProperty("is_note", True)
                lbl.setFixedHeight(18)
            else:
                lbl.setText(text or " ")
                lbl.setWordWrap(True)
            rl.addWidget(lbl, 1)

            chip = QLabel(f'<span style="color:#4ADE80">●</span>  {fmt_time(t_sec)}')
            chip.setTextFormat(Qt.RichText)
            chip.setObjectName("lyr-time")
            chip.setAutoFillBackground(False)
            chip.setStyleSheet("background: transparent; border: none;")
            chip.hide()
            rl.addWidget(chip)

            row.setProperty("lyric_time", float(t_sec))
            if self._lyrics_synced:
                row.setCursor(Qt.PointingHandCursor)
                row.installEventFilter(self)
                lbl.installEventFilter(self)
                lbl.setProperty("lyric_time", float(t_sec))
            self.lyrics_layout.addWidget(row)
            self._lyric_rows.append((row, accent, lbl, chip, float(t_sec)))
            self._lyric_labels.append(lbl)

        self.lyrics_layout.addStretch(1)

    def _on_lyrics_scrolled(self, _value: int) -> None:
        if not getattr(self, "_scroll_programmatic", False):
            self._user_scroll_until = time.monotonic() + 6.0

    def _ensure_line_visible(self, widget) -> None:
        from PySide6.QtCore import QPoint as _QPoint

        bar = self.lyrics_scroll.verticalScrollBar()
        vp = self.lyrics_scroll.viewport()
        y = widget.mapTo(self.lyrics_content, _QPoint(0, 0)).y()
        line_h = max(1, widget.height())
        top = bar.value()
        bottom = top + vp.height()
        margin = 20
        if y < top + margin or (y + line_h) > bottom - margin:
            target = max(0, y - vp.height() // 3)
            try:
                self._scroll_programmatic = True
                bar.setValue(target)
            finally:
                self._scroll_programmatic = False

    def toggle_lyrics(self) -> None:
        self._lyrics_mode = not self._lyrics_mode
        self.music_stack.setCurrentIndex(1 if self._lyrics_mode else 0)
        if hasattr(self, "lyrics_chip"):
            self.lyrics_chip.setStyleSheet(
                "background: rgba(155,135,255,0.28);" if self._lyrics_mode else "")

    def _current_pos(self) -> float:
        if self._pos_playing:
            return self._pos_base + (time.monotonic() - self._pos_t)
        return self._pos_base

    def _lyrics_tick(self) -> None:
        if not self._lyrics_mode or not self._lyrics_synced or not self._lyric_rows:
            return
        pos = self._current_pos()
        idx = -1
        for i, (_row, _a, _l, _c, tsec) in enumerate(self._lyric_rows):
            if pos >= tsec:
                idx = i
            else:
                break
        if idx != self._lyric_idx:
            _dim, active_pm = self._note_icons(13, 3)
            self._clear_all_highlights()
            self._lyric_idx = idx
            if idx >= 0:
                row, accent, lbl, chip, _tsec = self._lyric_rows[idx]
                # satu-satunya background: digambar QPainter di LyricRow
                row.set_active(True)
                accent.show()
                chip.show()
                if lbl.property("is_note") and active_pm is not None:
                    lbl.setPixmap(active_pm)
                else:
                    lbl.setStyleSheet(
                        "background: transparent; border: none;"
                        "color: #F5F3FF; font-weight: 700;")
                if time.monotonic() > getattr(self, "_user_scroll_until", 0.0):
                    self._ensure_line_visible(row)

    def _clear_all_highlights(self) -> None:
        dim_pm, _active = self._note_icons(13, 3)
        for row, accent, lbl, chip, _tsec in getattr(self, "_lyric_rows", []):
            if hasattr(row, "set_active"):
                row.set_active(False)
            else:
                row.setStyleSheet("")
            accent.hide()
            chip.hide()
            if lbl.property("is_note"):
                if dim_pm is not None:
                    lbl.setPixmap(dim_pm)
            else:
                lbl.setStyleSheet("background: transparent; border: none;")
        self._lyric_idx = -1

    # ============================================================ PAGE: SISTEM
    def _build_page_system(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        tiles = QHBoxLayout()
        tiles.setSpacing(10)
        self.tile_vol = self._tile("VOL", "Volume", C.ACCENT)
        self.tile_bat = self._tile("BAT", "Battery", C.ACCENT_GREEN)
        self.tile_cpu = self._tile("CPU", "Processor", C.ACCENT2)
        self.tile_ram = self._tile("RAM", "Memory", C.ACCENT_WARM)

        self.vol_slider = QSlider(Qt.Horizontal)
        self.vol_slider.setRange(0, 100)
        self.vol_slider.setFixedHeight(16)
        self.vol_slider.valueChanged.connect(self.volume_changed.emit)
        self.tile_vol["body"].addWidget(self.vol_slider)

        for t in (self.tile_vol, self.tile_bat, self.tile_cpu, self.tile_ram):
            tiles.addWidget(t["frame"], 1)
        lay.addLayout(tiles)

        # strip timer — digabung ke Sistem (elemennya sedikit, tak perlu tab sendiri)
        tstrip = QFrame()
        tstrip.setObjectName("timer-strip")
        tlay = QHBoxLayout(tstrip)
        tlay.setContentsMargins(12, 8, 12, 8)
        tlay.setSpacing(8)

        self.timer_icon = QLabel("⏱")
        self.timer_icon.setObjectName("t-icon")
        tlay.addWidget(self.timer_icon)

        self.timer_label = QLabel("Timer")
        self.timer_label.setObjectName("t-label")
        tlay.addWidget(self.timer_label)

        self.timer_value = QLabel("00:00")
        self.timer_value.setObjectName("t-value")
        tlay.addWidget(self.timer_value)

        self.timer_prog = QFrame()
        self.timer_prog.setObjectName("scrub")
        self.timer_prog.setFixedHeight(4)
        self.timer_prog_fill = QFrame(self.timer_prog)
        self.timer_prog_fill.setObjectName("scrub-fill")
        self.timer_prog_fill.setGeometry(0, 0, 0, 4)
        tlay.addWidget(self.timer_prog, 1)

        for minutes, name in ((5, "5m"), (15, "15m"), (25, "25m"), (50, "50m")):
            chip = QLabel(name)
            chip.setObjectName("t-chip")
            chip.setAlignment(Qt.AlignCenter)
            chip.setFixedSize(34, 24)
            chip.installEventFilter(self)
            chip.setProperty("preset", minutes)
            tlay.addWidget(chip)

        for label, action, tip in (
            ("▶", "toggle", "Start / Pause"),
            ("⟲", "reset", "Reset"),
        ):
            btn = QLabel(label)
            btn.setObjectName("seg-btn")
            btn.setAlignment(Qt.AlignCenter)
            btn.setFixedSize(30, 24)
            btn.setToolTip(tip)
            btn.installEventFilter(self)
            btn.setProperty("timer_action", action)
            tlay.addWidget(btn)

        lay.addWidget(tstrip)

        note = QLabel("Nilai diperbarui otomatis · slider volume langsung bekerja")
        note.setObjectName("t-tiny")
        note.setAlignment(Qt.AlignCenter)
        lay.addWidget(note)
        lay.addStretch(1)
        return page

    def _badge_pulse(self) -> None:
        self._pulse_phase += 0.22
        a = 0.62 + 0.38 * (0.5 + 0.5 * math.sin(self._pulse_phase))
        self.badge.setStyleSheet(
            f"color: rgba(81,207,102,{a:.2f});"
            f" background: rgba(81,207,102,{0.14 * a:.2f});"
            " border-radius: 999px;")

    def _wx_pulse(self) -> None:
        # breathing halus pada ikon cuaca, hanya saat tab Info aktif
        if getattr(self, "pages", None) is None or self.pages.currentIndex() != 2:
            return
        self._pulse_phase += 0.16
        a = 0.65 + 0.35 * (0.5 + 0.5 * math.sin(self._pulse_phase))
        self.wx_icon.setStyleSheet(f"color: rgba(255,184,108,{a:.2f});")

    def _dl_marquee_tick(self) -> None:
        self._dl_phase += 0.055
        if self._dl_phase > 1.0:
            self._dl_phase -= 1.0
        bar_w = max(1, self.dl_prog.width())
        seg = max(24, int(bar_w * 0.30))
        x = int((bar_w + seg) * self._dl_phase) - seg
        x = max(0, min(bar_w - 1, x))
        w = min(seg, bar_w - x)
        self.dl_prog_fill.setGeometry(x, 0, w, 4)

    def _timer_blink_tick(self) -> None:
        if self.timer is None:
            self._timer_blink_t.stop()
            return
        danger = self.timer.active and self.timer.remaining <= 60
        if not danger:
            self._timer_blink_t.stop()
            self.timer_value.setStyleSheet("")
            return
        self._timer_blink_on = not self._timer_blink_on
        self.timer_value.setStyleSheet(
            "color: #FF6B9D;" if self._timer_blink_on else "")

    def _set_chips(self, np) -> None:
        if not hasattr(self, "chip_source"):
            return
        if np is None:
            self.chip_source.setText("—")
            self.chip_album.setText("—")
            self.chip_state.setText("idle")
            self.btn_shuffle.setStyleSheet("")
            self.btn_loop.setStyleSheet("")
            self.btn_loop.setText("↻")
            self.btn_shuffle.setEnabled(False)
            self.btn_loop.setEnabled(False)
            if hasattr(self, "btn_shuffle2"):
                self.btn_shuffle2.setEnabled(False)
                self.btn_shuffle2.setStyleSheet("")
                self.btn_loop2.setEnabled(False)
                self.btn_loop2.setStyleSheet("")
            return
        self.chip_source.setText(np.identity or "—")
        self.chip_album.setText((np.album or "no album")[:28] or "—")
        self.chip_state.setText("playing" if np.playing else "paused")
        # state toggle shuffle/loop — hormati dukungan pemutar
        on = "background: rgba(110,139,255,0.35); color: #F4F4F8;"
        player = np.identity or "pemutar ini"

        self.btn_shuffle.setEnabled(bool(np.can_shuffle))
        if np.can_shuffle:
            self.btn_shuffle.setToolTip("Shuffle")
            self.btn_shuffle.setStyleSheet(on if np.shuffle else "")
        else:
            self.btn_shuffle.setToolTip(
                f"Shuffle tidak didukung {player} (butuh Spotify/VLC/mpv)")
            self.btn_shuffle.setStyleSheet("color: rgba(255,255,255,0.25);")

        for dup_s, dup_l in ((getattr(self, "btn_shuffle2", None),
                              getattr(self, "btn_loop2", None)),):
            if dup_s is not None:
                dup_s.setEnabled(bool(np.can_shuffle))
                dup_s.setStyleSheet(on if (np.can_shuffle and np.shuffle) else
                                    ("" if np.can_shuffle else "color: rgba(255,255,255,0.25);"))
            if dup_l is not None:
                dup_l.setEnabled(bool(np.can_loop))
                dup_l.setStyleSheet(on if (np.can_loop and np.loop_status != "None") else
                                    ("" if np.can_loop else "color: rgba(255,255,255,0.25);"))
        self.btn_loop.setEnabled(bool(np.can_loop))
        if np.can_loop:
            loop_txt = {"None": "↻", "Track": "①", "Playlist": "∞"}.get(np.loop_status, "↻")
            self.btn_loop.setText(loop_txt)
            self.btn_loop.setToolTip("Repeat: None → Playlist → Track")
            self.btn_loop.setStyleSheet(on if np.loop_status != "None" else "")
        else:
            self.btn_loop.setText("↻")
            self.btn_loop.setToolTip(
                f"Repeat tidak didukung {player} (butuh Spotify/VLC/mpv)")
            self.btn_loop.setStyleSheet("color: rgba(255,255,255,0.25);")

    # ============================================================ PAGE: INFO
    def _build_page_info(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        # ---------- cuaca ----------
        wx = QFrame()
        wx.setObjectName("info-card")
        wx.setMinimumHeight(72)
        wl = QHBoxLayout(wx)
        wl.setContentsMargins(12, 8, 12, 8)
        wl.setSpacing(12)

        self.wx_icon = QLabel("·")
        self.wx_icon.setObjectName("wx-icon")
        self.wx_icon.setFixedWidth(34)
        self.wx_icon.setAlignment(Qt.AlignCenter)
        wl.addWidget(self.wx_icon)

        wcol = QVBoxLayout()
        wcol.setSpacing(1)
        self.wx_temp = QLabel("—")
        self.wx_temp.setObjectName("wx-temp")
        self.wx_temp.setMinimumHeight(30)
        wcol.addWidget(self.wx_temp)
        self.wx_text = QLabel("Cuaca belum tersedia")
        self.wx_text.setObjectName("wx-text")
        wcol.addWidget(self.wx_text)
        self.wx_city = QLabel("")
        self.wx_city.setObjectName("t-tiny")
        wcol.addWidget(self.wx_city)
        wl.addLayout(wcol, 1)
        lay.addWidget(wx)

        # prakiraan per jam
        hours = QFrame()
        hours.setObjectName("info-card")
        hl = QHBoxLayout(hours)
        hl.setContentsMargins(12, 6, 12, 6)
        hl.setSpacing(6)
        hours.setMinimumHeight(58)
        self.wx_hours = []
        for _ in range(5):
            chip = QVBoxLayout()
            chip.setSpacing(1)
            hour = QLabel("--:--")
            hour.setObjectName("t-tiny")
            hour.setAlignment(Qt.AlignCenter)
            icon = QLabel("·")
            icon.setObjectName("h-icon")
            icon.setAlignment(Qt.AlignCenter)
            temp = QLabel("—")
            temp.setObjectName("h-temp")
            temp.setAlignment(Qt.AlignCenter)
            chip.addWidget(hour)
            chip.addWidget(icon)
            chip.addWidget(temp)
            hl.addLayout(chip, 1)
            self.wx_hours.append((hour, icon, temp))
        lay.addWidget(hours)



        # ---------- unduhan ----------
        dl = QFrame()
        dl.setObjectName("info-card")
        dll = QVBoxLayout(dl)
        dll.setContentsMargins(12, 8, 12, 8)
        dll.setSpacing(3)
        dl.setMinimumHeight(60)
        dhead = QHBoxLayout()
        dicon = QLabel("⬇")
        dicon.setObjectName("info-tag")
        dhead.addWidget(dicon)
        dtag = QLabel("UNDUHAN")
        dtag.setObjectName("info-tag")
        dhead.addWidget(dtag)
        dhead.addStretch(1)
        self.dl_count = QLabel("")
        self.dl_count.setObjectName("t-tiny")
        self.dl_count.setMinimumWidth(56)
        self.dl_count.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        dhead.addWidget(self.dl_count)
        dll.addLayout(dhead)
        self.dl_name = ElidedLabel("Tidak ada unduhan aktif")
        self.dl_name.setObjectName("dl-name")
        dll.addWidget(self.dl_name)
        self.dl_prog = QFrame()
        self.dl_prog.setObjectName("scrub")
        self.dl_prog.setFixedHeight(4)
        self.dl_prog_fill = QFrame(self.dl_prog)
        self.dl_prog_fill.setObjectName("scrub-fill")
        self.dl_prog_fill.setGeometry(0, 0, 0, 4)
        dll.addWidget(self.dl_prog)
        lay.addWidget(dl)

        lay.addStretch(1)
        return page

    # ------------------------------------------------------------ update info
    def update_weather(self, wx) -> None:
        if not hasattr(self, "wx_temp"):
            return
        if wx is None or not getattr(wx, "ok", False):
            self.wx_temp.setText("—")
            self.wx_text.setText("Cuaca belum tersedia")
            self.wx_city.setText("")
            self.wx_icon.setText("·")
            return
        self.wx_icon.setText(wx.icon)
        self.wx_temp.setText(f"{wx.temp:.0f}°")
        self.wx_text.setText(wx.text)
        import datetime as _dt
        stamp = _dt.datetime.fromtimestamp(wx.updated).strftime("%H:%M") if wx.updated else "—"
        self.wx_city.setText(f"{wx.city} · diperbarui {stamp}" if wx.city else f"diperbarui {stamp}")
        if hasattr(self, "compact_temp"):
            self._temp_text = f"{wx.temp:.0f}°"
            if not self._has_media:
                self._refresh_idle_sub()
        # strip per jam
        hourly = getattr(wx, "hourly", []) or []
        from ..services import WMO
        for i, (hour, icon, temp) in enumerate(self.wx_hours):
            if i < len(hourly):
                h_label, h_temp, h_code = hourly[i]
                hour.setText(h_label)
                icon.setText(WMO.get(h_code, ("", "·"))[1])
                temp.setText(f"{h_temp:.0f}°")
            else:
                hour.setText("--:--")
                icon.setText("·")
                temp.setText("—")

    def update_downloads(self, active) -> None:
        if not hasattr(self, "dl_name"):
            return
        from ..services import human_size

        if not active:
            self._dl_marquee_t.stop()
            self.dl_name.set_full_text("Tidak ada unduhan aktif")
            self.dl_count.setText("")
            self.dl_prog_fill.setGeometry(0, 0, 0, 4)
            return
        dl = active[0]
        extra = f" · +{len(active) - 1} lagi" if len(active) > 1 else ""
        self.dl_name.set_full_text(f"{dl.name}{extra}")
        self.dl_count.setText(human_size(dl.size))
        if not self._dl_marquee_t.isActive():
            self._dl_phase = 0.0
            self._dl_marquee_t.start()

    # ------------------------------------------------------------ tab nav
    def switch_tab(self, delta: int) -> None:
        total = self.pages.count()
        self._set_tab((self._tab_index + int(delta)) % total)

    def _set_tab(self, index: int) -> None:
        index = max(0, min(self.pages.count() - 1, int(index)))
        if index == self._tab_index or getattr(self, "_tab_busy", False):
            return
        from PySide6.QtCore import QPoint, QPropertyAnimation
        from PySide6.QtCore import QEasingCurve

        self._tab_busy = True
        self._pending_tab = index
        self._tab_dir = 1 if index > self._tab_index else -1
        home = self.pages.pos()
        self._pages_home = home

        def phase_out_done() -> None:
            self.pages.setCurrentIndex(self._pending_tab)
            self._tab_index = self._pending_tab
            self.tab_title.setText(self._tab_names[self._tab_index])
            # flash halus pada judul tab
            self.tab_title.setStyleSheet("color: #6E8BFF;")
            QTimer.singleShot(320, lambda: self.tab_title.setStyleSheet(""))
            self.tab_dots.setText("".join(
                "●" if i == self._tab_index else "○" for i in range(self.pages.count())))
            start_pos = QPoint(home.x() + 48 * self._tab_dir, home.y())
            self.pages.move(start_pos)
            anim_in = QPropertyAnimation(self.pages, b"pos")
            anim_in.setDuration(240)
            anim_in.setEasingCurve(QEasingCurve.OutCubic)
            anim_in.setStartValue(start_pos)
            anim_in.setEndValue(home)
            anim_in.finished.connect(self._tab_anim_done)
            self._tab_group = anim_in
            anim_in.start()

        # slide-out ke arah navigasi, lalu slide-in dari arah sebaliknya
        anim_out = QPropertyAnimation(self.pages, b"pos")
        anim_out.setDuration(170)
        anim_out.setEasingCurve(QEasingCurve.InCubic)
        anim_out.setStartValue(home)
        anim_out.setEndValue(QPoint(home.x() - 48 * self._tab_dir, home.y()))
        anim_out.finished.connect(phase_out_done)
        self._tab_group = anim_out
        anim_out.start()

    def _tab_anim_done(self) -> None:
        self._tab_busy = False
        self.pages.move(self._pages_home)

    def wheelEvent(self, ev) -> None:
        # scroll juga bisa ganti tab
        if ev.angleDelta().y() < 0:
            self.switch_tab(1)
        else:
            self.switch_tab(-1)
        ev.accept()

    # ------------------------------------------------------------ helpers
    def _tile(self, tag: str, label: str, accent: str) -> dict:
        frame = QFrame()
        frame.setObjectName("tile")
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(6)

        head = QHBoxLayout()
        dot = QLabel("●")
        dot.setStyleSheet(f"color: {accent}; font: 700 8px Sans; background: transparent;")
        head.addWidget(dot)
        tag_lbl = QLabel(tag)
        tag_lbl.setObjectName("tile-tag")
        head.addWidget(tag_lbl)
        head.addStretch(1)
        lay.addLayout(head)

        val = QLabel("—")
        val.setObjectName("tile-val")
        lay.addWidget(val)

        body = QVBoxLayout()
        body.setSpacing(4)
        sub = QLabel(label)
        sub.setObjectName("tile-sub")
        body.addWidget(sub)
        lay.addLayout(body)
        lay.addStretch(1)
        return {"frame": frame, "val": val, "body": body}

    def _make_wave(self, count: int, base: int, bar_w: int = 3) -> QWidget:
        # Ukuran box dikunci (fixed): animasi tinggi bar TIDAK boleh mengubah
        # sizeHint container, jika tidak layout di sekitarnya ikut jitter.
        box = QWidget()
        box.setAttribute(Qt.WA_LayoutUsesWidgetRect, True)
        lay = QHBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(3)
        lay.setAlignment(Qt.AlignVCenter)
        bars = []
        for _ in range(count):
            bar = QFrame()
            bar.setObjectName("wave")
            bar.setFixedWidth(bar_w)
            bar.setFixedHeight(max(3, base // 3))
            lay.addWidget(bar, 0, Qt.AlignVCenter)
            bars.append(bar)
        total_w = count * bar_w + max(0, count - 1) * 3
        box.setFixedSize(total_w, base)
        box.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        if not hasattr(self, "_waves"):
            self._waves = []
        self._waves.append((bars, base))
        return box

    def eventFilter(self, obj, ev):
        # QLabel "button" seg: klik untuk kontrol musik
        if ev.type() == ev.Type.MouseButtonRelease and obj.property("sig"):
            sig = obj.property("sig")
            if sig:
                sig.emit()
            return True
        # ganti tab via panah kiri/kanan
        if ev.type() == ev.Type.MouseButtonRelease and obj.property("tab_delta") is not None:
            try:
                delta = int(obj.property("tab_delta"))
            except (TypeError, ValueError):
                delta = 0
            if delta:
                self.switch_tab(delta)
            return True
        # toggle tampilan lirik
        if ev.type() == ev.Type.MouseButtonRelease and obj.property("lyrics_toggle"):
            self.toggle_lyrics()
            return True
        # klik baris lirik → seek
        if (ev.type() == ev.Type.MouseButtonRelease
                and obj.property("lyric_time") is not None
                and getattr(self, "_lyrics_synced", False)):
            try:
                t_sec = float(obj.property("lyric_time"))
            except (TypeError, ValueError):
                t_sec = -1.0
            if t_sec >= 0:
                self.lyrics_seek.emit(t_sec)
                self._pos_base = t_sec
                self._pos_t = time.monotonic()
                self._clear_all_highlights()
                self._user_scroll_until = 0.0
            return True
        # shuffle / loop
        if ev.type() == ev.Type.MouseButtonRelease and obj.property("media_action"):
            action = str(obj.property("media_action"))
            if action == "shuffle":
                self.shuffle_clicked.emit()
            elif action == "loop":
                self.loop_clicked.emit()
            return True
        # seek pada progress bar
        if obj is getattr(self, "scrub", None):
            if ev.type() in (ev.Type.MouseButtonPress, ev.Type.MouseMove) and (
                ev.buttons() & Qt.LeftButton or ev.type() == ev.Type.MouseButtonPress
            ):
                w = max(1, self.scrub.width())
                frac = max(0.0, min(1.0, ev.position().x() / w))
                self.seek_requested.emit(frac)
                self._set_scrub(frac, animate=False)
                return True
        # preset timer (menit)
        if ev.type() == ev.Type.MouseButtonRelease and obj.property("preset"):
            minutes = int(obj.property("preset"))
            if self.timer is not None:
                self.timer.start(minutes * 60, "Timer")
                self.sneak_peek("toast", f"Timer {minutes} menit", "⏱", C.TOAST_MS, 15)
            return True
        # tombol aksi timer
        if ev.type() == ev.Type.MouseButtonRelease and obj.property("timer_action"):
            action = str(obj.property("timer_action"))
            if action == "toggle":
                self._timer_toggle()
            elif action == "reset":
                self._timer_reset()
            return True
        return super().eventFilter(obj, ev)

    # ------------------------------------------------------------ timer
    def _timer_toggle(self) -> None:
        if self.timer is None:
            return
        if self.timer.running:
            self.timer.pause()
        elif self.timer.active:
            self.timer.resume()
        else:
            self.timer.start(25 * 60, "Pomodoro")

    def _timer_reset(self) -> None:
        if self.timer is not None:
            self.timer.reset()

    def _on_timer_changed(self) -> None:
        if self.timer is None:
            return
        self.timer_label.setText(self.timer.label)
        self.timer_value.setText(self.timer.text())
        w = max(0, int(self.timer_prog.width() * self.timer.progress()))
        self.timer_prog_fill.setGeometry(0, 0, w, 4)
        if self.timer.active and self.timer.running and self.timer.remaining <= 60:
            if not self._timer_blink_t.isActive():
                self._timer_blink_t.start()
        else:
            self._timer_blink_t.stop()
            self.timer_value.setStyleSheet("")
        self._refresh_compact()

    # ------------------------------------------------------------ sneak-peek
    def sneak_peek(self, kind: str, text: str, icon: str = "●",
                   ms: int = C.TOAST_MS, prio: int = 10) -> None:
        """Tampilkan pesan sekilas di pill (toast / HUD). Prioritas lebih tinggi menang."""
        import time as _time

        old = self._peek.get(kind)
        if old and old[0] > prio:
            return
        self._peek[kind] = (prio, text, icon, int(_time.monotonic() * 1000) + ms)
        self._refresh_compact()
        # jadwalkan expiry paling dekat
        self._peek_timer.start(min(ms, C.TOAST_MS))

    def _peek_expire(self) -> None:
        import time as _time

        now = int(_time.monotonic() * 1000)
        expired = [k for k, v in self._peek.items() if v[3] <= now]
        for k in expired:
            self._peek.pop(k, None)
        self._refresh_compact()
        if self._peek:
            nearest = min(v[3] for v in self._peek.values()) - now
            self._peek_timer.start(max(50, nearest))

    def _refresh_compact(self) -> None:
        # prioritas: peek (toast/hud) > timer > musik
        # logo tetap di compact_dot (identitas) — hanya teks yang berganti
        if self._peek:
            _prio, text, _icon, _exp = max(self._peek.values(), key=lambda v: v[0])
            self.compact_title.set_full_text(text)
            return
        if self.timer is not None and self.timer.active:
            self.compact_title.set_full_text(f"{self.timer.label}  {self.timer.text()}")
            return
        self.compact_title.set_full_text(self._base_title)

    # ------------------------------------------------------------ morph
    def set_opacity_for(self, t: float) -> None:
        self._compact_fx.setOpacity(max(0.0, 1.0 - t * 1.7))
        self._expanded_fx.setOpacity(max(0.0, min(1.0, (t - 0.18) * 1.55)))
        self.compact.setEnabled(t < 0.55)
        self.expanded.setEnabled(t > 0.35)
        self._place_children()

    def _place_children(self) -> None:
        """Pusatkan compact di tinggi berapa pun; expanded selalu di ukuran penuhnya."""
        w, h = self.width(), self.height()
        ch = 24
        self.compact.setGeometry(0, max(0, (h - ch) // 2), w, ch)
        self.expanded.setGeometry(0, 0, w, max(h, C.OPEN_H - 24))
        if hasattr(self, "_fx"):
            self._fx.setGeometry(0, 0, w, h)
            if self._fx.isVisible():
                self._fx.raise_()

    # ------------------------------------------------------------ update
    def _set_thumb(self, path: str, url: str) -> None:
        if url != self._art_url:
            return  # basi
        if not path:
            return
        img = art_loader.load_thumbnail(path, self._art_size, radius=18)
        if img is None:
            return
        pix = QPixmap.fromImage(img)
        self.art_label.setPixmap(pix)
        self.art_label.setText("")
        self.art_label.setStyleSheet("background: transparent;")
        if hasattr(self, "art2"):
            self.art2.setPixmap(pix.scaled(40, 40, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            self.art2.setText("")
            self.art2.setStyleSheet("background: transparent;")
        if hasattr(self, "compact_art"):
            small = art_loader.load_thumbnail(path, 32, radius=9)
            if small is not None:
                self.compact_art.setPixmap(QPixmap.fromImage(small))
            self.compact_slot.setCurrentIndex(0)
        self._art_loaded_url = url

    def _art_fallback(self, color: str) -> None:
        self.art_label.setStyleSheet(
            f"background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 {color},"
            f" stop:1 #7C5CFF); border-radius: 16px;"
        )
        pm = self._logo_pixmap(52)
        if not pm.isNull():
            self.art_label.setText("")
            self.art_label.setPixmap(pm)
        else:
            self.art_label.setText("♪")
        if hasattr(self, "art2"):
            pm2 = self._logo_pixmap(26)
            self.art2.clear()
            if not pm2.isNull():
                self.art2.setPixmap(pm2)
                self.art2.setStyleSheet("background: transparent;")
            else:
                self.art2.setText("♪")
                self.art2.setStyleSheet(
                    f"background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 {C.ACCENT_DEEP},"
                    f" stop:1 #7C5CFF); border-radius: 12px; color: rgba(255,255,255,0.85);"
                    f" font-weight: 700; font-size: 20px; font-family: Sans;")
        if hasattr(self, "compact_art"):
            pmc = self._logo_pixmap(20)
            self.compact_art.clear()
            if not pmc.isNull():
                self.compact_art.setPixmap(pmc)
        self._art_loaded_url = ""

    def _update_art(self, art_url: str) -> None:
        url = art_url or ""
        if url and url == self._art_loaded_url:
            return
        if url != self._art_url:
            self._art_url = url
            if not url:
                self._art_fallback(C.ACCENT_DEEP)
                return
            if not self._art_loaded_url:
                self._art_fallback(C.ACCENT_DEEP)
            art_loader.fetch_async(url, lambda p, u=url: self._set_thumb(p, u))

    def update_media(self, np) -> None:
        self._has_media = bool(np.available and np.title)
        self._playing = bool(np.playing)
        self._pos_base = float(getattr(np, "position", 0.0) or 0.0)
        self._pos_t = time.monotonic()
        self._pos_playing = self._playing
        self._length = float(getattr(np, "length", 0.0) or 0.0)
        if self._has_media:
            label = np.title if not np.artist else f"{np.title} — {np.artist}"
            # sneak-peek saat lagu berganti (padanan sneakPeekEvent)
            if getattr(self, "_last_title", None) not in (None, np.title):
                self.sneak_peek("toast", label, "♪", C.TOAST_MS, 15)
            self._last_title = np.title
            self._base_title = np.title or "notchy"
            if hasattr(self, "compact_title"):
                self.compact_slot.setCurrentIndex(0)
                self.compact_title.set_full_text(np.title or "(no title)")
                sub_src = np.identity or "media"
                self.compact_sub.set_full_text(
                    f"{sub_src} · {'playing' if np.playing else 'paused'}")
            self._base_icon = "▶" if np.playing else "▶"
            self.title.set_full_text(np.title or "(no title)")
            if np.artist and np.album:
                self.artist.set_full_text(f"{np.artist} • {np.album}")
            else:
                self.artist.set_full_text(np.artist or np.album or np.identity or "")
            if hasattr(self, "np_source"):
                self.np_source.setText(np.identity or "media")
            if hasattr(self, "btn_play_big"):
                self.btn_play_big.setText("⏸" if np.playing else "▶")
            if hasattr(self, "btn_play_small"):
                self.btn_play_small.setText("⏸" if np.playing else "▶")
            self.time_now.setText(fmt_time(np.position))
            self.time_len.setText(fmt_time(np.length))
            self._set_scrub(np.progress or 0.0)
            if hasattr(self, "title2"):
                self.title2.set_full_text(np.title or "(no title)")
                self.artist2.set_full_text(np.artist or np.album or np.identity or "")
                self.time2_now.setText(fmt_time(np.position))
                self.time2_len.setText(fmt_time(np.length))
            if np.playing and not self._badge_pulse_t.isActive():
                self._badge_pulse_t.start()
            elif not np.playing:
                self._badge_pulse_t.stop()
                self.badge.setStyleSheet("")
            self.badge.setText("PLAYING" if np.playing else "PAUSED")
            self.badge.setProperty("playing", "true" if np.playing else "false")
            self.badge.style().unpolish(self.badge)
            self.badge.style().polish(self.badge)
            parts = [p for p in (np.identity, np.album) if p]
            note = " · ".join(parts) if parts else "Media"
            ov = self._footer_override_text()
            self.now_label.set_full_text(ov if ov else note)
            self._update_art(np.art_url or "")
            self._set_chips(np)
            if hasattr(self, "music_status"):
                state_txt = "Sedang diputar" if np.playing else "Dijeda"
                self.music_status.setText(f"{state_txt} · {np.identity or ''} · {fmt_time(np.position)}")
        else:
            self._last_title = None
            self._base_title = "notchy"
            self._base_icon = "●"
            if hasattr(self, "compact_title"):
                self.compact_slot.setCurrentIndex(1)
                self.compact_title.set_full_text("notchy")
                self._refresh_idle_sub()
            self.title.set_full_text("Tidak ada musik")
            self.artist.set_full_text("Putar sesuatu di pemutar favoritmu")
            if hasattr(self, "np_source"):
                self.np_source.setText("—")
            if hasattr(self, "btn_play_big"):
                self.btn_play_big.setText("▶")
            if hasattr(self, "btn_play_small"):
                self.btn_play_small.setText("▶")
            self.time_now.setText("0:00")
            self.time_len.setText("0:00")
            self._set_scrub(0.0)
            self.badge.setText("IDLE")
            self.badge.setProperty("playing", "false")
            ov = self._footer_override_text()
            self.now_label.set_full_text(
                ov if ov else "Live activities siap — hover untuk membuka")
            self._art_url = ""
            self._art_fallback(C.ACCENT_DEEP)
            self._set_chips(np)
            self._set_chips(None)
            if hasattr(self, "music_status"):
                self.music_status.setText("Siap — putar musik untuk memulai")
        self._refresh_compact()
        self._sync_wave()

    def update_system(self, st) -> None:
        if st.battery_present:
            icon = "⚡" if st.charging else ""
            self.tile_bat["val"].setText(f"{st.battery_percent}%")
            self.compact_bat.setText(f"BAT {st.battery_percent}%")
            self._sys_hint = f"{st.battery_percent}%"
        else:
            self.tile_bat["val"].setText("AC")
            self.compact_bat.setText("AC")
            self._sys_hint = "AC"
        self.tile_vol["val"].setText(f"{st.volume}%")
        if hasattr(self, "vol_slider2"):
            if int(self.vol_slider2.value()) != st.volume:
                self.vol_slider2.blockSignals(True)
                self.vol_slider2.setValue(st.volume)
                self.vol_slider2.blockSignals(False)
            self.vol_pct2.setText(f"{st.volume}%")
        self.tile_cpu["val"].setText(f"{int(st.cpu_percent)}%")
        self.tile_ram["val"].setText(f"{int(st.ram_percent)}%")
        if int(self.vol_slider.value()) != st.volume:
            self.vol_slider.blockSignals(True)
            self.vol_slider.setValue(st.volume)
            self.vol_slider.blockSignals(False)

    def update_clock(self, st) -> None:
        self.clock_label.setText(st.time_str)
        self.date_label.setText(st.date_str)
        self.compact_clock.setText(st.time_str)
        self._date_text = st.date_str
        if not self._has_media:
            self._refresh_idle_sub()
        self._refresh_compact()

    def _refresh_idle_sub(self) -> None:
        if not hasattr(self, "compact_sub") or self._has_media:
            return
        date = getattr(self, "_date_text", "")
        temp = getattr(self, "_temp_text", "")
        parts = [p for p in (date, temp) if p]
        self.compact_sub.set_full_text(" · ".join(parts))

    def wake_eyes(self) -> None:
        if hasattr(self, "compact_eyes"):
            self.compact_eyes.wake()

    def _apply_fill_frac(self, frac: float) -> None:
        frac = max(0.0, min(1.0, frac))
        w1 = max(0, int(self.scrub.width() * frac))
        self.scrub_fill.setGeometry(0, 0, w1, self.scrub.height())
        if hasattr(self, "scrub2") and self.scrub2.width() > 0:
            w2 = max(0, int(self.scrub2.width() * frac))
            self.scrub2_fill.setGeometry(0, 0, w2, self.scrub2.height())

    def _set_scrub(self, frac: float, animate: bool = True) -> None:
        """Set posisi progress — kedua bar (normal & lirik) selalu sinkron."""
        self._frac = max(0.0, min(1.0, frac or 0.0))
        self._apply_fill_frac(self._frac)

    def _progress_tick(self) -> None:
        """Gerakkan progress tiap 250ms dari posisi terinterpolasi (anti-stuck)."""
        length = float(getattr(self, "_length", 0.0) or 0.0)
        if length <= 0:
            return
        pos = max(0.0, min(length, self._current_pos()))
        frac = pos / length
        self._apply_fill_frac(frac)
        now_txt = fmt_time(pos)
        len_txt = fmt_time(length)
        self.time_now.setText(now_txt)
        self.time_len.setText(len_txt)
        if hasattr(self, "time2_now"):
            self.time2_now.setText(now_txt)
            self.time2_len.setText(len_txt)

    def resizeEvent(self, ev) -> None:
        super().resizeEvent(ev)
        self._place_children()
        self._set_scrub(self._frac, animate=False)
        if hasattr(self, "scrub2"):
            w = max(0, int(self.scrub2.width() * self._frac))
            self.scrub2_fill.setGeometry(0, 0, w, self.scrub2.height())

    # ------------------------------------------------------------ waveform
    def _sync_wave(self) -> None:
        popping = time.monotonic() < getattr(self, "_wave_pop_until", 0.0)
        want = self._playing or popping
        if want and not self._wave_timer.isActive():
            self._wave_timer.start()
            self._set_wave_dim(False)
        elif not want and self._wave_timer.isActive():
            self._wave_timer.stop()
            self._set_wave_dim(True)
            for bars, base in getattr(self, "_waves", []):
                for b in bars:
                    b.setFixedHeight(max(3, base // 4))

    def _wave_pop(self, ms: int = 1400) -> None:
        """Satu denyut waveform saat perangkat audio tersambung."""
        self._wave_pop_until = time.monotonic() + ms / 1000.0
        if not self._wave_timer.isActive():
            self._wave_timer.start()
            self._set_wave_dim(False)

    def _halo_pulse(self) -> None:
        """Dua denyut halo di sekitar logo pill."""
        from PySide6.QtCore import QVariantAnimation

        anim = QVariantAnimation(self)
        anim.setDuration(1000)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)

        def step(u: float) -> None:
            a = abs(math.sin(float(u) * math.pi * 2.0)) * 0.55
            self.compact_slot.setStyleSheet(
                f"border: 2px solid rgba(155,135,255,{a:.2f}); border-radius: 15px;")

        anim.valueChanged.connect(step)
        anim.finished.connect(lambda: self.compact_slot.setStyleSheet(""))
        self._halo_anim = anim
        anim.start()

    def headset_event(self, kind: str, label: str) -> None:
        """Event colok/cabut headset — animasi di pill compact."""
        if kind == "plug":
            text = f"Headset tersambung · {label}"
        else:
            text = f"Headset dicabut · {label}"
        self.sneak_peek("toast", text, "", 2800, 24)
        self._halo_pulse()
        self._wave_pop()
        if hasattr(self, "_fx"):
            self._fx.play(kind, 2400)

    def flash_footer(self, text: str, ms: int = 2800) -> None:
        """Pesan singkat di footer saat panel sedang terbuka."""
        self._footer_override = (text, time.monotonic() + ms / 1000.0)
        self.now_label.set_full_text(text)

    def _footer_override_text(self) -> str | None:
        ov = getattr(self, "_footer_override", None)
        if ov and time.monotonic() < ov[1]:
            return ov[0]
        self._footer_override = None
        return None

    def _set_wave_dim(self, dim: bool) -> None:
        for bars, _base in getattr(self, "_waves", []):
            for b in bars:
                b.setProperty("dims", "true" if dim else "false")
                b.style().unpolish(b)
                b.style().polish(b)

    def _wave_tick(self) -> None:
        self._wave_level = max(0.15, min(1.0, self._wave_level + random.uniform(-0.28, 0.32)))
        phase = (self._wave_timer.interval() * self._wave_timer.isActive() +
                 __import__("time").monotonic()) * 1.0
        for bars, base in getattr(self, "_waves", []):
            n = len(bars)
            for i, bar in enumerate(bars):
                wobble = 0.5 + 0.5 * math.sin(phase * 5.0 + i * 0.9)
                level = self._wave_level * wobble
                bar.setFixedHeight(max(3, int(3 + level * (base - 3))))
