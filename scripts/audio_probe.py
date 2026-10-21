#!/usr/bin/env python3
"""Diagnostik deteksi headset: tampilkan semua sumber yang dibaca.

Jalankan:  ./.venv/bin/python scripts/audio_probe.py
Colok/cabut headset lalu jalankan lagi untuk melihat perubahan.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from notchy.providers.linux import AudioOutputMonitor


def main() -> None:
    m = AudioOutputMonitor()
    print("== Sumber deteksi ==")
    pw = m._pw_dump()
    print("pw-dump tersedia :", pw is not None)
    print("jack PipeWire    :", m._read_pipewire_jack(pw) if pw is not None else "n/a",
          " (True = headphone tercolok)")
    print("jack ALSA        :", m._read_jack(), " (None = tidak ada kontrol jack)")
    sinks = m._read_sink_set(pw) if pw is not None else None
    print("sink aktif       :", sorted(sinks) if sinks else "tidak terdeteksi")
    print()

    if pw is not None:
        print("== Route audio perangkat ==")
        for obj in pw:
            info = obj.get("info") or {}
            props = info.get("props") or {}
            if props.get("media.class") != "Audio/Device":
                continue
            print("device:", props.get("node.name") or props.get("device.name"))
            params = info.get("params") or {}
            for key in ("EnumRoute", "Route"):
                for r in params.get(key) or []:
                    name = str(r.get("name", ""))
                    avail = str(r.get("available", ""))
                    if "headphone" in name or "headset" in name or "speaker" in name:
                        print(f"  [{key}] {name:38} available={avail}")


if __name__ == "__main__":
    main()