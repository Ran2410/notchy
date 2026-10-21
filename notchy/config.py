"""Konfigurasi visual & timing island — bahasa desain Alcove-style glass.

Padanan temuan REA boring.notch:
  closedNotchSize ↔ notchSize   → CLOSED_*/OPEN_*
  spring morph                   → ANIM_MS + EASE_POWER
  openNotchOnHover / closeTask   → CLOSE_DELAY_MS
"""

# Geometri (closed = pill mungil ala Dynamic Island, open = panel bento)
CLOSED_W, CLOSED_H = 264, 40
OPEN_W, OPEN_H = 528, 328
TOP_MARGIN = 8
SIDE_MIN_MARGIN = 24

# Desain token — dark glass ala Alcove
GLASS_BG = "rgba(14, 14, 20, 0.92)"
GLASS_SHEEN = "rgba(255, 255, 255, 0.08)"      # highlight atas panel
GLASS_EDGE = "rgba(255, 255, 255, 0.10)"
GLASS_EDGE_SOFT = "rgba(255, 255, 255, 0.06)"
TILE_BG = "rgba(255, 255, 255, 0.055)"
TILE_BG_HOVER = "rgba(255, 255, 255, 0.10)"
TRACK_BG = "rgba(255, 255, 255, 0.12)"
SHADOW = "0 18px 48px rgba(0, 0, 0, 0.55)"

TEXT = "#F4F4F8"
TEXT_DIM = "#9B9BAA"
TEXT_FAINT = "#6E6E7E"
ACCENT = "#6E8BFF"        # biru-lavender
ACCENT_DEEP = "#4C6EF5"
ACCENT2 = "#A78BFA"       # ungu
ACCENT_WARM = "#FFB86C"
ACCENT_GREEN = "#51CF66"
ACCENT_PINK = "#FF6B9D"

RADIUS_ISLAND = 24
RADIUS_TILE = 16
RADIUS_PILL = 999

# Animasi
ANIM_MS = 280
EASE_POWER = 3
CLOSE_DELAY_MS = 420
POLL_MPRIS_MS = 900
POLL_SYS_MS = 2500
WAVE_TICK_MS = 70         # bar visualizer (AudioSpectrum analog)
