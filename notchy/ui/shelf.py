"""UI Rak Berkas: baris item, halaman daftar, dan overlay drag-drop."""
from __future__ import annotations

import math
import os
import time

from PySide6.QtCore import QFileInfo, QMimeData, QPoint, QRectF, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import (
    QColor,
    QDrag,
    QFont,
    QIcon,
    QPainter,
    QPainterPath,
    QPen,
)
from PySide6.QtWidgets import (
    QApplication,
    QFileIconProvider,
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .. import config as C
from ..shelf import ShelfItem, ShelfModel, KIND_DIR
from ..services import human_size


# ================================================================= baris
class ShelfRow(QWidget):
    open_requested = Signal(str)      # path
    remove_requested = Signal(str)    # id

    def __init__(self, item: ShelfItem, parent=None) -> None:
        super().__init__(parent)
        self.item = item
        self._press_pos: QPoint | None = None
        self._dragging = False
        self.setObjectName("shelf-row")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setFixedHeight(46)
        self.setCursor(Qt.PointingHandCursor)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 6, 8, 6)
        lay.setSpacing(10)

        self.icon_label = QLabel()
        self.icon_label.setFixedSize(24, 24)
        self.icon_label.setAlignment(Qt.AlignCenter)
        self.icon_label.setObjectName("shelf-icon")
        lay.addWidget(self.icon_label)

        col = QVBoxLayout()
        col.setSpacing(0)
        col.setContentsMargins(0, 0, 0, 0)
        self.name_label = QLabel()
        self.name_label.setObjectName("shelf-name")
        self.name_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.name_label.setAttribute(Qt.WA_StyledBackground, False)
        col.addWidget(self.name_label)
        self.meta_label = QLabel()
        self.meta_label.setObjectName("shelf-meta")
        col.addWidget(self.meta_label)
        lay.addLayout(col, 1)

        self.remove_btn = QToolButton()
        self.remove_btn.setObjectName("shelf-remove")
        self.remove_btn.setText("×")
        self.remove_btn.setToolTip("Hapus dari Shelf")
        self.remove_btn.setAccessibleName("Hapus dari Shelf")
        self.remove_btn.setFixedSize(22, 22)
        self.remove_btn.setCursor(Qt.PointingHandCursor)
        self.remove_btn.setFocusPolicy(Qt.TabFocus)
        self.remove_btn.hide()
        self.remove_btn.clicked.connect(
            lambda: self.remove_requested.emit(self.item.id))
        lay.addWidget(self.remove_btn)

        self._apply_icon()
        self.update_state()

    # ------------------------------------------------------------ tampilan
    def _apply_icon(self) -> None:
        provider = QFileIconProvider()
        icon: QIcon = provider.icon(QFileInfo(self.item.path))
        if icon.isNull():
            icon = self.style().standardIcon(
                self.style().StandardPixmap.SP_DirIcon if self.item.kind == KIND_DIR
                else self.style().StandardPixmap.SP_FileIcon)
        self.icon_label.setPixmap(icon.pixmap(22, 22))

    def update_state(self) -> None:
        item = self.item
        exists = item.exists()
        self.name_label.setText(self._elide(item.name))
        self.name_label.setToolTip(item.path)
        self.setToolTip(item.path)
        if not exists:
            self.meta_label.setText("Missing")
            self.name_label.setStyleSheet("color: rgba(228,225,233,0.35);")
            self.icon_label.setEnabled(False)
            self.setStyleSheet("background: transparent;")
        elif item.kind == KIND_DIR:
            self.meta_label.setText("Folder")
            self.name_label.setStyleSheet("")
            self.icon_label.setEnabled(True)
        else:
            self.meta_label.setText(human_size(item.size) if item.size else "File")
            self.name_label.setStyleSheet("")
            self.icon_label.setEnabled(True)

    @staticmethod
    def _elide(text: str) -> str:
        # elipsis sederhana berbasis panjang; QLabel di layout akan memotong +
        # tooltip menyediakan nama penuh
        if len(text) <= 42:
            return text
        return text[:40] + "…"

    def _dim(self, dim: bool) -> None:
        self.name_label.setStyleSheet(
            "color: rgba(228,225,233,0.35);" if dim else "")
        self.meta_label.setStyleSheet(
            "color: rgba(110,107,122,0.5);" if dim else "")

    # ------------------------------------------------------------ hover
    def enterEvent(self, ev) -> None:
        self.remove_btn.show()
        super().enterEvent(ev)

    def leaveEvent(self, ev) -> None:
        if not self.remove_btn.hasFocus():
            self.remove_btn.hide()
        super().leaveEvent(ev)

    # ------------------------------------------------------------ interaksi
    def mousePressEvent(self, ev) -> None:
        if ev.button() == Qt.LeftButton:
            self._press_pos = ev.position().toPoint()
        super().mousePressEvent(ev)

    def mouseReleaseEvent(self, ev) -> None:
        if (ev.button() == Qt.LeftButton and self._press_pos is not None
                and not self._dragging):
            self.open_requested.emit(self.item.path)
        self._press_pos = None
        self._dragging = False
        super().mouseReleaseEvent(ev)

    def mouseMoveEvent(self, ev) -> None:
        if (self._press_pos is None or not (ev.buttons() & Qt.LeftButton)
                or self._dragging):
            return super().mouseMoveEvent(ev)
        delta = ev.position().toPoint() - self._press_pos
        if delta.manhattanLength() < QApplication.startDragDistance():
            return super().mouseMoveEvent(ev)

        # mulai drag keluar — item TIDAK dihapus
        self._dragging = True
        drag = QDrag(self)
        drag.setMimeData(self.drag_mime())
        pm = self.icon_label.pixmap()
        if pm is not None and not pm.isNull():
            drag.setPixmap(pm)
        self._dim(True)
        try:
            drag.exec(Qt.CopyAction)
        finally:
            self._dim(False)
            self._dragging = False
            self._press_pos = None

    def drag_mime(self) -> QMimeData:
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(self.item.path)])
        mime.setText(self.item.path)
        return mime

    def keyPressEvent(self, ev) -> None:
        if ev.key() in (Qt.Key_Return, Qt.Key_Enter):
            self.open_requested.emit(self.item.path)
            ev.accept()
            return
        super().keyPressEvent(ev)


# ================================================================= halaman
class ShelfPage(QWidget):
    """Daftar ringkas satu kolom + empty state. Animasi masuk/keluar item."""

    def __init__(self, model: ShelfModel, parent=None) -> None:
        super().__init__(parent)
        self.model = model
        self._rows: dict[str, ShelfRow] = {}
        self._animations: list = []

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        head = QHBoxLayout()
        head.setSpacing(8)
        tag = QLabel("SHELF")
        tag.setObjectName("info-tag")
        head.addWidget(tag)
        head.addStretch(1)
        self.count_label = QLabel("")
        self.count_label.setObjectName("t-tiny")
        head.addWidget(self.count_label)
        lay.addLayout(head)

        self.stack = QStackedWidget()
        lay.addWidget(self.stack, 1)

        # --- empty state ---
        self.empty = QWidget()
        el = QVBoxLayout(self.empty)
        el.setContentsMargins(0, 10, 0, 10)
        el.setSpacing(6)
        el.addStretch(1)
        icon = QLabel("⇩")
        icon.setObjectName("shelf-empty-icon")
        icon.setAlignment(Qt.AlignCenter)
        el.addWidget(icon)
        title = QLabel("Your Shelf is empty")
        title.setObjectName("shelf-empty-title")
        title.setAlignment(Qt.AlignCenter)
        el.addWidget(title)
        sub = QLabel("Drop files here to collect them")
        sub.setObjectName("shelf-empty-sub")
        sub.setAlignment(Qt.AlignCenter)
        el.addWidget(sub)
        hint = QLabel("Drag out anytime · Click to open")
        hint.setObjectName("shelf-empty-hint")
        hint.setAlignment(Qt.AlignCenter)
        el.addWidget(hint)
        el.addStretch(1)
        self.stack.addWidget(self.empty)

        # --- list ---
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setObjectName("shelf-scroll")
        self.scroll.viewport().setAutoFillBackground(False)
        self.scroll.setStyleSheet("background: transparent;")
        self.content = QWidget()
        self.content.setAttribute(Qt.WA_StyledBackground, True)
        self.content.setStyleSheet("background: transparent;")
        self.list_layout = QVBoxLayout(self.content)
        self.list_layout.setContentsMargins(0, 0, 6, 0)
        self.list_layout.setSpacing(2)
        self.list_layout.addStretch(1)
        self.scroll.setWidget(self.content)
        self.stack.addWidget(self.scroll)

        self.rebuild()

    # ------------------------------------------------------------ helpers
    def _count_text(self) -> str:
        n = len(self.model.items)
        return f"{n} item" if n == 1 else f"{n} items"

    def _sync_views(self) -> None:
        has = not self.model.is_empty
        self.stack.setCurrentWidget(self.scroll if has else self.empty)
        self.count_label.setText(self._count_text() if has else "")

    # ------------------------------------------------------------ rebuild
    def rebuild(self) -> None:
        for row in self._rows.values():
            row.setParent(None)
            row.deleteLater()
        self._rows.clear()
        while self.list_layout.count() > 1:
            item = self.list_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        for item in self.model.items:
            self._insert_row(item, animate=False)
        self._sync_views()

    # ------------------------------------------------------------ increment
    def add_items(self, items: list[ShelfItem], animate: bool = True) -> None:
        for i, item in enumerate(items):
            if item.id in self._rows:
                continue
            row = self._make_row(item)
            idx = max(0, self.list_layout.count() - 1)
            self.list_layout.insertWidget(idx, row)
            self._rows[item.id] = row
            if animate:
                self._animate_in(row, delay_ms=i * 35)
        self._sync_views()

    def _make_row(self, item: ShelfItem) -> ShelfRow:
        row = ShelfRow(item)
        row.open_requested.connect(self._open_path)
        row.remove_requested.connect(self._remove_id)
        return row

    def _insert_row(self, item: ShelfItem, animate: bool) -> None:
        row = self._make_row(item)
        idx = max(0, self.list_layout.count() - 1)
        self.list_layout.insertWidget(idx, row)
        self._rows[item.id] = row
        if animate:
            self._animate_in(row)

    def remove_row(self, item_id: str, animate: bool = True) -> None:
        row = self._rows.pop(item_id, None)
        if row is None:
            return
        if not animate:
            row.setParent(None)
            row.deleteLater()
            self._sync_views()
            return

        from PySide6.QtCore import QEasingCurve, QPropertyAnimation

        anim = QPropertyAnimation(row, b"maximumHeight", self)
        anim.setDuration(170)
        anim.setEasingCurve(QEasingCurve.InOutCubic)
        anim.setStartValue(row.height())
        anim.setEndValue(0)
        anim.finished.connect(lambda: (row.setParent(None), row.deleteLater(),
                                       self._sync_views()))
        self._animations.append(anim)
        anim.start()

    def _animate_in(self, row: ShelfRow, delay_ms: int = 0) -> None:
        from PySide6.QtCore import QEasingCurve, QPropertyAnimation

        row.setMaximumHeight(0)
        row.hide()
        anim = QPropertyAnimation(row, b"maximumHeight", self)
        anim.setDuration(240)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        anim.setStartValue(0)
        anim.setEndValue(46)

        def start() -> None:
            row.show()
            anim.start()

        self._animations.append(anim)
        QTimer.singleShot(delay_ms, start)

    # ------------------------------------------------------------ state
    def refresh_states(self) -> None:
        """Periksa ulang keberadaan file (murah, tanpa rekursi)."""
        for item in self.model.items:
            item.refresh_meta()
            row = self._rows.get(item.id)
            if row is not None:
                row.update_state()

    # ------------------------------------------------------------ aksi
    def _open_path(self, path: str) -> None:
        from PySide6.QtGui import QDesktopServices

        if not os.path.exists(path):
            # refresh tampilan missing
            self.refresh_states()
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def _remove_id(self, item_id: str) -> None:
        if self.model.remove(item_id):
            self.remove_row(item_id, animate=True)


# ================================================================= overlay
DROP_IDLE = "IDLE"
DROP_VALID = "DRAG_OVER_VALID"
DROP_INVALID = "DRAG_OVER_INVALID"
DROP_PROCESSING = "DROP_PROCESSING"
DROP_SUCCESS = "DROP_SUCCESS"


class DropOverlay(QWidget):
    """Overlay drag-drop: border dashed violet berdenyut + instruksi."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self._state = DROP_IDLE
        self._count = 0
        self._phase = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(50)
        self._timer.timeout.connect(self._tick)
        self.hide()

    @property
    def state(self) -> str:
        return self._state

    def set_state(self, state: str, count: int = 0) -> None:
        self._state = state
        self._count = count
        if state == DROP_IDLE:
            self._timer.stop()
            self.hide()
            return
        self.show()
        self.raise_()
        if state == DROP_VALID:
            self._timer.start()
        else:
            self._timer.stop()
            self._phase = 0.0
        self.update()

    def _tick(self) -> None:
        self._phase += 0.12
        self.update()

    def paintEvent(self, ev) -> None:
        if self._state == DROP_IDLE:
            return
        from PySide6.QtGui import QColor, QFont, QPainter, QPen

        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        w, h = self.width(), self.height()
        rect = QRectF(3, 3, w - 6, h - 6)

        valid = self._state in (DROP_VALID, DROP_PROCESSING)
        success = self._state == DROP_SUCCESS
        if success:
            color = QColor(74, 222, 128, 210)
        elif valid:
            alpha = 150 + int(60 * (0.5 + 0.5 * math.sin(self._phase)))
            color = QColor(155, 135, 255, alpha)
        else:
            color = QColor(255, 90, 110, 200)

        pen = QPen(color, 1.6, Qt.DashLine)
        pen.setDashPattern([5, 4])
        p.setPen(pen)
        p.setBrush(QColor(20, 20, 30, 90))
        p.drawRoundedRect(rect, 20, 20)

        # ikon + teks tengah
        if self._state == DROP_VALID:
            text = ("Lepaskan untuk menambahkan "
                    + (f"{self._count} item" if self._count != 1 else "1 item"))
        elif self._state == DROP_PROCESSING:
            text = "Menambahkan…"
        elif self._state == DROP_SUCCESS:
            text = ("Ditambahkan "
                    + (f"{self._count} item" if self._count != 1 else "1 item"))
        else:
            text = "Tipe file tidak didukung"

        p.setPen(QColor(236, 233, 255, 230))
        f = QFont("Inter")
        f.setPixelSize(13)
        f.setWeight(QFont.Weight.DemiBold)
        p.setFont(f)
        if h < 110:
            # capsule kecil: cukup satu baris, tanpa ikon
            p.drawText(QRectF(0, 0, w, h), Qt.AlignHCenter | Qt.AlignVCenter, text)
        else:
            icon_y = h / 2 - 18
            p.drawText(QRectF(0, icon_y, w, 20), Qt.AlignHCenter | Qt.AlignVCenter, "⇩")
            p.drawText(QRectF(0, h / 2 + 2, w, 20), Qt.AlignHCenter | Qt.AlignVCenter, text)
        p.end()