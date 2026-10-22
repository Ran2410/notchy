"""Konfigurasi visual & timing island — bahasa desain Alcove-style glass.

Padanan temuan REA boring.notch:
  closedNotchSize ↔ notchSize   → CLOSED_*/OPEN_*
  spring morph                   → ANIM_MS + EASE_POWER
  openNotchOnHover / closeTask   → CLOSE_DELAY_MS
"""

# Geometri (closed = capsule, open = panel) — mengikuti design Stitch/Nusa
CLOSED_W, CLOSED_H = 328, 42
OPEN_W, OPEN_H = 528, 420
TOP_MARGIN = 8
SIDE_MIN_MARGIN = 24

# Desain token — dark glass ala Alcove
GLASS_BG = "rgba(14, 14, 20, 0.92)"
GLASS_SHEEN = "rgba(255, 255, 255, 0.08)"      # highlight atas panel
GLASS_EDGE = "rgba(255, 255, 255, 0.10)"
GLASS_EDGE_SOFT = "rgba(255, 255, 255, 0.06)"
TILE_BG = "rgba(255, 255, 255, 0.06)"
TILE_BG_HOVER = "rgba(255, 255, 255, 0.10)"
TRACK_BG = "rgba(255, 255, 255, 0.12)"
SHADOW = "0 18px 48px rgba(0, 0, 0, 0.55)"

TEXT = "#E4E1E9"
TEXT_DIM = "#A6A3B2"
TEXT_FAINT = "#6E6B7A"
ACCENT = "#9B87FF"        # violet utama (design token)
ACCENT_DEEP = "#7B4BFF"   # iris dalam
ACCENT2 = "#C4B5FD"       # lavender terang
ACCENT_CYAN = "#19B8FF"   # aksen listrik (waveform)
ACCENT_WARM = "#FBBF24"
ACCENT_GREEN = "#4ADE80"
ACCENT_PINK = "#FF5A6E"

RADIUS_ISLAND = 26
RADIUS_TILE = 16
RADIUS_PILL = 999

# Animasi
ANIM_MS = 280
EASE_POWER = 3
CLOSE_DELAY_MS = 420
POLL_MPRIS_MS = 900
POLL_SYS_MS = 2500
WAVE_TICK_MS = 70         # bar visualizer (AudioSpectrum analog)

# Sneak-peek / HUD (padanan sneakPeekEvent + HUD volume/brightness)
TOAST_MS = 3200           # notifikasi / sneak peek lagu
HUD_MS = 1400             # HUD volume / brightness
HUD_SUPPRESS_MS = 600     # abaikan perubahan volume sesaat setelah slider dikirim

# Prioritas 2 — cuaca / unduhan / alert baterai
WEATHER_POLL_MS = 60_000      # cek tiap menit; fetch nyata dibatasi max_age 30 menit
DOWNLOADS_POLL_MS = 2_000
AUDIO_POLL_MS = 2_500
BATTERY_LOW = 20              # toast peringatan di bawah ini
BATTERY_REARM = 25            # izinkan peringatan lagi setelah naik di atas ini
BATTERY_FULL = 99             # toast saat hampir penuh (sambil mengisi)

