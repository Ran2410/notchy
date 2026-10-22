# notchy — Dynamic Island untuk Linux & Windows

Aplikasi overlay top-center ala Dynamic Island, diport dari mekanisme
**boring.notch v2.7.3** (aplikasi notch untuk MacBook) lewat analisis reverse-
engineering pada binary shipped-nya. Visual mengikuti design system
**dark glass violet** (Stitch "Dynamic Island Companion") — capsule 328×42
dengan album art + judul + waveform + chip waktu, state idle menampilkan
**mata maskot** yang berkedip, panel musik dengan art besar + tombol play
besar, serta lirik dengan **baris aktif pill violet + bar aksen + timestamp**.

## Dukungan OS

| | Linux | Windows 10/11 |
|---|---|---|
| UI / overlay | Qt (X11/Xwayland) | Qt (native, stay-on-top) |
| Now Playing | **MPRIS** (D-Bus) | **SMTC** (`winsdk` — Windows.Media.Control) |
| Thumbnail album | `mpris:artUrl` | stream thumbnail SMTC |
| Volume | `amixer` (ALSA) | **Core Audio** (`pycaw`) |
| Baterai / CPU / RAM | `/sys`, `/proc` | `psutil` |
| Status | teruji penuh | provider compile-checked; uji runtime di Windows |

## Menjalankan

### Linux
```bash
cd notchy
python3 -m venv --system-site-packages .venv   # system-site-packages → dbus-python
./.venv/bin/pip install -r requirements-linux.txt
./.venv/bin/python run.py
```

### Windows (PowerShell)
```powershell
cd notchy
py -m venv .venv
.\.venv\Scripts\pip install -r requirements-windows.txt
.\.venv\Scripts\python run.py
```

**Interaksi:** hover island → buka panel · klik pill → pin terbuka ·
klik kanan → Quit · slider volume langsung bekerja.

## Fitur

- **Pill compact** (`264×40`, rounded penuh) — **logo notchy**, teks fokus
  (lagu / timer / toast), waveform mini, jam
- **Branding** — logo tampil di pill compact, header tab, placeholder art saat
  idle, dan icon jendela/taskbar
- **Panel expanded bertab** (`528×364`) — hanya fitur yang isinya banyak
  dijadikan tab, diganti lewat **panah ‹ ›** (klik / keyboard kiri-kanan / scroll)
  dengan animasi slide-out/slide-in (OutCubic):
  - **♪ Musik** — kartu hero (thumbnail album 88px, judul, chips sumber/album/status),
    **progress seekable** (klik untuk lompat posisi), kontrol transport +
    **shuffle ⇄** + **repeat ↻**, waveform besar, dan tombol **LIRIK**.
    **Lirik tersinkron** (LRCLIB): panel terbelah — pemutar ringkas di kiri,
    lirik di kanan; baris aktif menyala & auto-scroll, klik baris untuk seek.
    Auto-scroll hanya jalan bila baris aktif keluar layar dan **menghormati
    scroll manual** (ditahan 6 detik), jadi tidak menarik paksa ke atas.
    Tombol shuffle/repeat otomatis **nonaktif** bila pemutar tidak mendukung
    (mis. YouTube di Chrome tidak mengekspos `Shuffle`/`LoopStatus` di MPRIS —
    gunakan Spotify/VLC/mpv untuk fitur itu; seek & transport tetap jalan)
  - **▦ Sistem** — tile VOL/BAT/CPU/RAM + strip timer/pomodoro
  - **ⓘ Info** — **cuaca + prakiraan per jam** (Open-Meteo, lokasi via IP
    atau config) dan **unduhan aktif** (folder Downloads)
- **Sneak-peek / toast** — notifikasi desktop (Linux, D-Bus
  `org.freedesktop.Notifications`) dan judul saat lagu berganti tampil sekilas
  di pill, dengan prioritas: toast > HUD > timer > musik
- **HUD volume & brightness** — perubahan dari tombol keyboard/OS terdeteksi
  dan tampil sebagai HUD ringkas di pill (bukan OSD bawaan)
- **Timer / pomodoro** — preset 5/15/25/50 menit, play/pause/reset; sisa waktu
  mengambil alih pill compact saat aktif, notifikasi saat selesai
- **Cuaca** — suhu + kondisi (kode WMO) di tab Info, **prakiraan per jam**
  (5 jam ke depan), dan chip `32°` di pill; lokasi otomatis lewat IP atau
  manual via config
- **Watcher unduhan** — mendeteksi file yang sedang diunduh di `~/Downloads`
  (`.part`/`.crdownload`/ukuran membesar), toast saat mulai & selesai
- **Alert baterai** — toast saat mulai mengisi, daya dicabut, baterai lemah
  (≤20%, sekali per sesi), dan hampir penuh (≥99%)
- **Deteksi headset/earphone** — Bluetooth via sinyal BlueZ
  (`org.bluez.Device1.Connected`, difilter UUID audio) + jack 3.5mm via
  **status route PipeWire** (`analog-output-headphones: available=yes/no`,
  dibaca dari `pw-dump`) dengan fallback kontrol jack ALSA dan nama sink
  `pactl`; USB headset terdeteksi dari sink yang muncul/hilang.
  Windows memantau perangkat output default (pycaw).
  Diagnostik: `./.venv/bin/python scripts/audio_probe.py` Saat colok/cabut, pill menampilkan animasi:
  pill **pop** (OutBack), **kilau menyapu**, **headphone menggambar diri**
  mengelilingi logo, **sonar rings**, glow, halo, dan **waveform "pop"** sekali.
  Bila panel sedang terbuka, pesan cukup muncul di footer tanpa pindah tab.
- **Animasi** —
  - morph pill ↔ panel (geometry OutCubic 280 ms) + radius otomatis
  - tab: slide-out/in + flash halus judul tab
  - progress seek **glide** antar polling (420 ms OutCubic)
  - badge **PLAYING** berdenyut saat musik berjalan
  - bar unduhan **marquee** saat ada unduhan aktif
  - ikon cuaca **breathing** di tab Info
  - timer **berkedip** saat sisa ≤60 detik
  - jendela **fade-in** saat aplikasi mulai
- **Hover-to-expand**, auto-close setelah kursor keluar, klik untuk pin
- Thumbnail album di-fetch dari `mpris:artUrl` (file/http/data URI) dan di-cache

## Cara kerja (ringkas)

| Mekanisme boring.notch (hasil RE) | Implementasi notchy |
|---|---|
| `BoringNotchSkyLightWindow` — overlay top-center | `Qt.FramelessWindowHint \| WindowStaysOnTopHint \| Tool`, posisi `(mon_w-w)/2, y=8` |
| `NotchState`, `closedNotchSize` ↔ `notchSize` | `QPropertyAnimation` geometry 264×40 ↔ 528×328, easing OutCubic 280 ms |
| `NotchShape` | rounded-rect QSS, radius dinamis `min(24, h/2)` |
| `openNotchOnHover` + `closeNotchTask` | `enterEvent`/`leaveEvent` + `QTimer` 420 ms (verifikasi kursor) |
| `NowPlayingController` (MediaRemote) | MPRIS (Linux) / SMTC (Windows) |
| `AudioSpectrum` | waveform bar saat playing |
| `VolumeManager` / `BatteryActivityManager` | ALSA+`/sys` (Linux) / pycaw+psutil (Windows) |

## Struktur

```
run.py                      entry point (Qt)
assets/
    notchy-icon.png         ikon (crop dari notchy-hero-dark.png)
    notchy-wordmark.png     wordmark
notchy/config.py            design token + geometri + timing
notchy/art.py               fetch & thumbnail album art (file/http/data URI)
notchy/providers/
    base.py                 dataclass NowPlaying/SystemState
    linux.py                MPRIS + amixer + /sys + /proc + AudioOutputMonitor
    windows.py              SMTC (winsdk) + pycaw + psutil + AudioOutputMonitor
notchy/ui/
    island.py               window, animasi morph, hover/close, HUD & toast wiring
    activities.py           compact pill ↔ expanded bertab (Musik/Sistem) + sneak-peek
    style.py                QSS dark-glass
notchy/timer.py             kontrol timer/pomodoro
notchy/services.py          cuaca (Open-Meteo), agenda ICS, watcher unduhan
legacy/gtk/                 implementasi GTK3 lama (Linux-only, referensi)
scripts/capture_qt.py       uji visual → shots/ (di-ignore)
```

## Konfigurasi opsional

Buat `~/.config/notchy/config.json` bila ingin mengatur manual:

```json
{
  "weather":   { "lat": -6.2, "lon": 106.8, "city": "Jakarta" },
  "downloads": { "dir": "~/Downloads" }
}
```

Tanpa config, lokasi cuaca dideteksi via IP.

## Catatan Windows

- `winsdk` membaca sesi media global (Spotify, Chrome/Edge, dll) lewat SMTC —
  setara MPRIS di Linux. Thumbnail disimpan ke `~/.cache/notchy/art/`.
- Posisi window native (tidak butuh Xwayland).
- Pemutar yang tidak mengekspos sesi SMTC → fallback idle (clock, baterai,
  CPU/RAM tetap hidup).

## Catatan Reverse Engineering

Mekanisme di tabel di atas diturunkan dari analisis statis binary
boring.notch v2.7.3 (Mach-O universal, decompile via Hopper). Artefak analisis
itu (DMG, hasil ekstraksi, evidence bundle) **tidak disertakan di repo** —
lihat `.gitignore`. Aplikasi ini hanya meniru perilaku UI-nya, tidak
menggunakan kode dari boring.notch (GPL-3.0); silakan patuhi lisensinya bila
ingin memakai kode aslinya.

## Uji cepat

```bash
./.venv/bin/python scripts/capture_qt.py   # screenshot → shots/
```
