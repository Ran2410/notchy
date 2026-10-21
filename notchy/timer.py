"""Controller timer/pomodoro — live activity kedua setelah musik.

Padanan pola Live Activities: saat berjalan, pill compact menampilkan sisa
waktu; panel expanded menyediakan preset & kontrol.
"""
from __future__ import annotations

from PySide6.QtCore import QObject, QTimer, Signal


def fmt_mmss(total_seconds: int) -> str:
    total_seconds = max(0, int(total_seconds))
    m, s = divmod(total_seconds, 60)
    if m >= 60:
        h, m = divmod(m, 60)
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


class TimerController(QObject):
    changed = Signal()
    finished = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.duration = 0
        self.remaining = 0
        self.running = False
        self.label = "Timer"
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._tick)

    # ------------------------------------------------------------ state
    @property
    def active(self) -> bool:
        """Timer sedang punya sisa waktu (running atau paused)."""
        return self.duration > 0 and self.remaining > 0

    def text(self) -> str:
        return fmt_mmss(self.remaining)

    def progress(self) -> float:
        if self.duration <= 0:
            return 0.0
        return max(0.0, min(1.0, 1.0 - self.remaining / self.duration))

    # ------------------------------------------------------------ aksi
    def start(self, seconds: int, label: str = "Timer") -> None:
        seconds = max(1, int(seconds))
        self.duration = seconds
        self.remaining = seconds
        self.label = label
        self.running = True
        self._timer.start()
        self.changed.emit()

    def pause(self) -> None:
        if self.running:
            self.running = False
            self._timer.stop()
            self.changed.emit()

    def resume(self) -> None:
        if self.active and not self.running:
            self.running = True
            self._timer.start()
            self.changed.emit()

    def toggle(self) -> None:
        if self.running:
            self.pause()
        else:
            self.resume() if self.active else self.start(self.duration or 25 * 60)

    def reset(self) -> None:
        self._timer.stop()
        self.running = False
        self.remaining = 0
        self.duration = 0
        self.changed.emit()

    def _tick(self) -> None:
        self.remaining = max(0, self.remaining - 1)
        if self.remaining == 0:
            self.running = False
            self._timer.stop()
            self.changed.emit()
            self.finished.emit()
        else:
            self.changed.emit()
