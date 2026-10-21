"""Loader thumbnail album art (cross-platform, berbasis QImage).

Menerima: file path lokal, file://, http(s)://, data:image/…;base64.
Hasil di-cache di ~/.cache/notchy/art/ — file gambar tak tepercaya,
hanya dibaca QImage, tidak pernah dieksekusi.
"""
from __future__ import annotations

import base64
import hashlib
import os
import threading
import urllib.request
from typing import Callable, Optional

CACHE_DIR = os.path.join(os.path.expanduser("~"), ".cache", "notchy", "art")
MAX_BYTES = 6 * 1024 * 1024
TIMEOUT_S = 6.0
UA = "notchy/0.2 (Qt; MPRIS/SMTC album-art fetcher)"

_pending: set[str] = set()


def _cache_path(key: str) -> str:
    os.makedirs(CACHE_DIR, exist_ok=True)
    digest = hashlib.sha256(key.encode("utf-8", "replace")).hexdigest()
    return os.path.join(CACHE_DIR, digest + ".img")


def fetch_sync(url: str) -> Optional[str]:
    """Kembalikan path file gambar lokal, atau None bila gagal."""
    if not url:
        return None
    try:
        # path lokal polos (dipakai provider Windows SMTC)
        if not ("://" in url or url.startswith("data:")):
            if os.path.isfile(url) and os.path.getsize(url) > 0:
                return url
            return None

        if url.startswith("file://"):
            from urllib.parse import unquote, urlparse

            path = unquote(urlparse(url).path)
            with open(path, "rb") as f:
                data = f.read(MAX_BYTES + 1)
        elif url.startswith("data:"):
            header, _, payload = url.partition(",")
            if ";base64" in header:
                data = base64.b64decode(payload, validate=False)[: MAX_BYTES + 1]
            else:
                data = payload.encode("utf-8", "replace")[: MAX_BYTES + 1]
        elif url.startswith("http://") or url.startswith("https://"):
            cached = _cache_path(url)
            if os.path.isfile(cached) and os.path.getsize(cached) > 0:
                return cached
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
                data = resp.read(MAX_BYTES + 1)
            if 0 < len(data) <= MAX_BYTES:
                tmp = cached + ".part"
                with open(tmp, "wb") as f:
                    f.write(data)
                os.replace(tmp, cached)
                return cached
            return None
        else:
            return None

        if not (0 < len(data) <= MAX_BYTES):
            return None
        cached = _cache_path(url)
        if not os.path.isfile(cached) or os.path.getsize(cached) == 0:
            tmp = cached + ".part"
            with open(tmp, "wb") as f:
                f.write(data)
            os.replace(tmp, cached)
        return cached
    except Exception:
        return None


def fetch_async(url: str, callback: Callable[[Optional[str]], None]) -> None:
    """Ambil art di background; callback dijadwalkan balik ke thread UI oleh pemanggil."""
    if not url:
        callback(None)
        return
    if url in _pending:
        return
    _pending.add(url)

    def worker() -> None:
        try:
            path = fetch_sync(url)
        finally:
            _pending.discard(url)
        callback(path)

    threading.Thread(target=worker, daemon=True, name="notchy-art").start()


def load_thumbnail(path: str, size: int = 72, radius: int = 14):
    """Muat gambar → center-crop square → resize → sudut membulat (QImage)."""
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QBrush, QColor, QImage, QPainter, QPainterPath, QPen

    img = QImage(path)
    if img.isNull():
        return None

    w, h = img.width(), img.height()
    if w <= 0 or h <= 0:
        return None
    side = min(w, h)
    xoff = (w - side) // 2
    yoff = (h - side) // 2
    if (w, h) != (side, side):
        img = img.copy(xoff, yoff, side, side)

    img = img.convertToFormat(QImage.Format_ARGB32_Premultiplied)
    if side != size:
        img = img.scaled(size, size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        # pastikan pas square setelah scale
        if img.width() != size or img.height() != size:
            x = (img.width() - size) // 2
            y = (img.height() - size) // 2
            img = img.copy(max(0, x), max(0, y), size, size)

    # mask sudut membulat
    out = QImage(size, size, QImage.Format_ARGB32_Premultiplied)
    out.fill(Qt.transparent)
    painter = QPainter(out)
    painter.setRenderHint(QPainter.Antialiasing, True)
    path = QPainterPath()
    path.addRoundedRect(0.5, 0.5, size - 1.0, size - 1.0, radius, radius)
    painter.setClipPath(path)
    painter.drawImage(0, 0, img)
    # hairline glass edge
    pen = QPen(QColor(255, 255, 255, 40))
    pen.setWidthF(1.0)
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)
    painter.drawPath(path)
    painter.end()
    return out
