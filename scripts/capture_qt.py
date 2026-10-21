#!/usr/bin/env python3
"""Uji visual Qt: capture closed & expanded ke folder shots/."""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "xcb")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from notchy.ui.island import IslandWindow

OUT = os.path.join(ROOT, "shots")
os.makedirs(OUT, exist_ok=True)
win = None


def snap(name: str) -> None:
    pix = win.grab()
    path = os.path.join(OUT, name)
    pix.save(path)
    print("saved", path, "window", win.width(), "x", win.height(), "pos", win.pos())


def phase2() -> bool:
    print("expanding…")
    win.expand()
    QTimer.singleShot(900, phase3)
    return False


def phase3() -> bool:
    snap("02-expanded.png")
    QTimer.singleShot(300, QApplication.quit)
    return False


def phase1() -> bool:
    snap("01-closed.png")
    QTimer.singleShot(400, phase2)
    return False


def main() -> None:
    global win
    app = QApplication(sys.argv)
    win = IslandWindow()
    win.show()
    QTimer.singleShot(800, phase1)
    app.exec()


if __name__ == "__main__":
    main()
