#!/usr/bin/env python3
"""Uji visual: jalankan island, capture closed & expanded, simpan PNG."""
import os
import sys

os.environ.setdefault("GDK_BACKEND", "x11")
import os
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, GLib, Gtk

from notchy.island import IslandWindow

OUT = os.path.join(ROOT, "shots")
os.makedirs(OUT, exist_ok=True)
win = None


def snap(name: str) -> None:
    # capture window itu sendiri (root Xwayland tidak memantulkan desktop Wayland)
    gw = win.get_window()
    pb = Gdk.pixbuf_get_from_window(gw, 0, 0, gw.get_width(), gw.get_height())
    path = os.path.join(OUT, name)
    pb.savev(path, "png", [], [])
    print("saved", path, "window", gw.get_width(), "x", gw.get_height(),
          "at", win.get_position())


def phase2() -> bool:
    print("expanding…")
    win.expand()
    GLib.timeout_add(700, phase3)
    return False


def phase3() -> bool:
    snap("02-expanded.png")
    # ukur geometri jendela saat open
    print("win geom:", win.get_allocation().width, "x", win.get_allocation().height,
          "pos:", win.get_position())
    GLib.timeout_add(300, quit_now)
    return False


def quit_now() -> bool:
    Gtk.main_quit()
    return False


def phase1() -> bool:
    snap("01-closed.png")
    print("win geom closed:", win.get_allocation().width, "x", win.get_allocation().height,
          "pos:", win.get_position())
    GLib.timeout_add(400, phase2)
    return False


def main() -> None:
    global win
    win = IslandWindow()
    win.show_all()
    GLib.timeout_add(800, phase1)
    Gtk.main()


if __name__ == "__main__":
    main()
