"""Konten island Qt: compact cluster ↔ expanded bento (Alcove-style glass)."""
from __future__ import annotations

import math
import random

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QSlider,
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


class Activities(QWidget):
    volume_changed = Signal(int)
    play_pause_clicked = Signal()
    next_clicked = Signal()
    prev_clicked = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        # WA_StyledBackground: wajib agar QSS #island-bg terpaint pada QWidget custom
        self.setAttribute(Qt.WA_StyledBackground, True)
        self._has_media = False
        self._playing = False
        self._art_url = ""
        self._art_loaded_url = ""
        self._art_size = 72
        self._sys_hint = "…"
        self._wave_level = 0.0
        self._frac = 0.0

        # Tanpa layout root: compact & expanded diposisikan manual di resizeEvent
        # supaya widget yang sedang di-fade tidak menghimpit yang lain (bug clip).
        self.compact = self._build_compact()
        self.expanded = self._build_expanded()
        self.compact.setParent(self)
        self.expanded.setParent(self)

        self._compact_fx = QGraphicsOpacityEffect(self.compact)
        self.compact.setGraphicsEffect(self._compact_fx)
        self._expanded_fx = QGraphicsOpacityEffect(self.expanded)
        self.expanded.setGraphicsEffect(self._expanded_fx)

        self._wave_timer = QTimer(self)
        self._wave_timer.setInterval(C.WAVE_TICK_MS)
        self._wave_timer.timeout.connect(self._wave_tick)

        self.set_opacity_for(0.0)

    # ============================================================ COMPACT
    def _build_compact(self) -> QWidget:
        row = QWidget()
        lay = QHBoxLayout(row)
        lay.setContentsMargins(14, 0, 14, 0)
        lay.setSpacing(8)

        self.compact_dot = QLabel("●")
        self.compact_dot.setObjectName("c-dot")
        self.compact_dot.setAlignment(Qt.AlignCenter)
        self.compact_dot.setFixedWidth(18)
        self.compact_dot.setFixedHeight(20)
        lay.addWidget(self.compact_dot)

        self.compact_title = ElidedLabel("notchy")
        self.compact_title.setObjectName("c-title")
        self.compact_title.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        lay.addWidget(self.compact_title, 1)

        self.compact_wave = self._make_wave(3, base=10)
        lay.addWidget(self.compact_wave)

        self.compact_clock = QLabel("--:--")
        self.compact_clock.setObjectName("c-clock")
        self.compact_clock.setFixedHeight(20)
        self.compact_clock.setAlignment(Qt.AlignVCenter | Qt.AlignRight)
        lay.addWidget(self.compact_clock)

        # referensi agar tetap aman saat update (tidak lagi tampil di compact)
        self.compact_bat = QLabel("")
        self.compact_bat.hide()
        return row

    # ============================================================ EXPANDED
    def _build_expanded(self) -> QWidget:
        box = QWidget()
        lay = QVBoxLayout(box)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(12)

        # ---------- hero musik ----------
        hero = QFrame()
        hero.setObjectName("hero")
        hlay = QHBoxLayout(hero)
        hlay.setContentsMargins(12, 12, 12, 12)
        hlay.setSpacing(14)

        self.art_label = QLabel("♪")
        self.art_label.setFixedSize(self._art_size, self._art_size)
        self.art_label.setAlignment(Qt.AlignCenter)
        self.art_label.setStyleSheet(
            f"background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 {C.ACCENT_DEEP},"
            f" stop:1 #7C5CFF); border-radius: 14px; color: rgba(255,255,255,0.85);"
            f" font: 700 26px Sans;"
        )
        hlay.addWidget(self.art_label, 0, Qt.AlignVCenter)

        info = QVBoxLayout()
        info.setSpacing(4)

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

        self.scrub = QFrame()
        self.scrub.setObjectName("scrub")
        self.scrub.setFixedHeight(4)
        self.scrub_fill = QFrame(self.scrub)
        self.scrub_fill.setObjectName("scrub-fill")
        self.scrub_fill.setGeometry(0, 0, 0, 4)
        info.addWidget(self.scrub)

        times = QHBoxLayout()
        self.time_now = QLabel("0:00")
        self.time_now.setObjectName("t-tiny")
        self.time_len = QLabel("0:00")
        self.time_len.setObjectName("t-tiny")
        times.addWidget(self.time_now)
        times.addStretch(1)
        times.addWidget(self.time_len)
        info.addLayout(times)

        hlay.addLayout(info, 1)

        seg = QFrame()
        seg.setObjectName("seg")
        slay = QHBoxLayout(seg)
        slay.setContentsMargins(4, 2, 4, 2)
        slay.setSpacing(2)
        for label, sig, tip in (
            ("⏮", self.prev_clicked, "Previous"),
            ("⏯", self.play_pause_clicked, "Play / Pause"),
            ("⏭", self.next_clicked, "Next"),
        ):
            btn = QLabel(label)
            btn.setObjectName("seg-btn")
            btn.setAlignment(Qt.AlignCenter)
            btn.setFixedSize(34, 30)
            btn.setToolTip(tip)
            btn.installEventFilter(self)
            btn.setProperty("sig", sig)
            slay.addWidget(btn)
        hlay.addWidget(seg, 0, Qt.AlignVCenter)

        lay.addWidget(hero)

        # ---------- bento tiles ----------
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

        # ---------- footer ----------
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
        self.date_label = QLabel("")
        self.date_label.setObjectName("t-tiny")
        self.date_label.setAlignment(Qt.AlignRight)
        clock_box.addWidget(self.clock_label)
        clock_box.addWidget(self.date_label)
        flay.addLayout(clock_box)

        lay.addWidget(footer)
        return box

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

    def _make_wave(self, count: int, base: int) -> QWidget:
        box = QWidget()
        lay = QHBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(3)
        lay.setAlignment(Qt.AlignVCenter)
        bars = []
        for _ in range(count):
            bar = QFrame()
            bar.setObjectName("wave")
            bar.setFixedWidth(3)
            bar.setFixedHeight(max(3, base // 3))
            lay.addWidget(bar, 0, Qt.AlignVCenter)
            bars.append(bar)
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
        return super().eventFilter(obj, ev)

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

    # ------------------------------------------------------------ update
    def _set_thumb(self, path: str, url: str) -> None:
        if url != self._art_url:
            return  # basi
        if not path:
            return
        img = art_loader.load_thumbnail(path, self._art_size, radius=14)
        if img is None:
            return
        self.art_label.setPixmap(QPixmap.fromImage(img))
        self.art_label.setText("")
        self.art_label.setStyleSheet("background: transparent;")
        self._art_loaded_url = url

    def _art_fallback(self, color: str) -> None:
        self.art_label.clear()
        self.art_label.setText("♪")
        self.art_label.setStyleSheet(
            f"background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 {color},"
            f" stop:1 #7C5CFF); border-radius: 14px; color: rgba(255,255,255,0.85);"
            f" font: 700 26px Sans;"
        )
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
        if self._has_media:
            label = np.title if not np.artist else f"{np.title} — {np.artist}"
            self.compact_title.set_full_text(label)
            self.compact_dot.setText("▶")
            self.title.set_full_text(np.title or "(no title)")
            self.artist.set_full_text(np.artist or np.album or np.identity or "")
            self.time_now.setText(fmt_time(np.position))
            self.time_len.setText(fmt_time(np.length))
            self._set_scrub(np.progress or 0.0)
            self.badge.setText("PLAYING" if np.playing else "PAUSED")
            self.badge.setProperty("playing", "true" if np.playing else "false")
            self.badge.style().unpolish(self.badge)
            self.badge.style().polish(self.badge)
            parts = [p for p in (np.identity, np.album) if p]
            self.now_label.set_full_text(" · ".join(parts) if parts else "Media")
            self._update_art(np.art_url or "")
        else:
            self.compact_title.set_full_text("notchy")
            self.compact_dot.setText("●")
            self.title.set_full_text("Tidak ada musik")
            self.artist.set_full_text("Putar sesuatu di pemutar favoritmu")
            self.time_now.setText("0:00")
            self.time_len.setText("0:00")
            self._set_scrub(0.0)
            self.badge.setText("IDLE")
            self.badge.setProperty("playing", "false")
            self.now_label.set_full_text("Live activities siap — hover untuk membuka")
            self._art_url = ""
            self._art_fallback(C.ACCENT_DEEP)
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

    def _set_scrub(self, frac: float) -> None:
        self._frac = max(0.0, min(1.0, frac or 0.0))
        w = max(0, int(self.scrub.width() * self._frac))
        self.scrub_fill.setGeometry(0, 0, w, 4)

    def resizeEvent(self, ev) -> None:
        super().resizeEvent(ev)
        self._place_children()
        self._set_scrub(self._frac)

    # ------------------------------------------------------------ waveform
    def _sync_wave(self) -> None:
        if self._playing and not self._wave_timer.isActive():
            self._wave_timer.start()
            self._set_wave_dim(False)
        elif not self._playing and self._wave_timer.isActive():
            self._wave_timer.stop()
            self._set_wave_dim(True)
            for bars, base in getattr(self, "_waves", []):
                for b in bars:
                    b.setFixedHeight(max(3, base // 4))

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
