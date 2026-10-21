"""QSS design token — dark glass bento ala Alcove (sama dengan legacy GTK)."""
from __future__ import annotations

from .. import config as C

ISLAND_QSS = f"""
#Island {{
    background-color: transparent;
}}
/* solid dark glass ala versi GTK — border-radius di-set dinamis
   (min(24, tinggi/2)) dari IslandWindow agar closed selalu pill */
#island-bg {{
    background-color: #0c0c12;
    border: 1px solid rgba(255,255,255,0.10);
    border-radius: {C.RADIUS_ISLAND}px;
}}
#c-dot {{
    color: {C.ACCENT};
    background: transparent;
    font-weight: 700; font-size: 11px; font-family: Sans;
    min-width: 18px; max-width: 18px; min-height: 20px; max-height: 20px;
}}
#c-title {{ color: {C.TEXT}; font-weight: 600; font-size: 11px; font-family: Sans; }}
#c-chip {{
    color: {C.TEXT_DIM};
    background: {C.TILE_BG};
    border-radius: 12px;
    font-weight: 600; font-size: 11px; font-family: Sans;
}}
#c-clock {{ color: {C.TEXT_DIM}; font-weight: 700; font-size: 11px; font-family: Sans; }}
#c-sep {{ background: rgba(255,255,255,0.10); max-width: 1px; min-width: 1px; }}

#hero {{
    background: {C.TILE_BG};
    border: 1px solid {C.GLASS_EDGE_SOFT};
    border-radius: {C.RADIUS_TILE}px;
}}
#h-title {{ color: {C.TEXT}; font-weight: 700; font-size: 15px; font-family: Sans; }}
#h-sub {{ color: {C.TEXT_DIM}; font-weight: 500; font-size: 12px; font-family: Sans; }}
#badge {{
    color: {C.ACCENT};
    background: rgba(110,139,255,0.16);
    border-radius: {C.RADIUS_PILL}px;
    font-weight: 700; font-size: 9px; font-family: Sans;
}}
#badge[playing="true"] {{
    color: {C.ACCENT_GREEN};
    background: rgba(81,207,102,0.16);
}}
#t-tiny {{ color: {C.TEXT_FAINT}; font-weight: 500; font-size: 10px; font-family: Sans; }}

#seg {{
    background: rgba(255,255,255,0.06);
    border: 1px solid {C.GLASS_EDGE_SOFT};
    border-radius: {C.RADIUS_PILL}px;
}}
#seg-btn {{
    color: {C.TEXT};
    background: transparent;
    border: none;
    border-radius: {C.RADIUS_PILL}px;
    font-weight: 600; font-size: 13px; font-family: Sans;
    min-width: 34px; max-width: 34px; min-height: 30px; max-height: 30px;
}}
#seg-btn:hover {{ background: rgba(255,255,255,0.12); }}
#seg-btn:pressed {{ background: rgba(110,139,255,0.35); }}

#tile {{
    background: {C.TILE_BG};
    border: 1px solid {C.GLASS_EDGE_SOFT};
    border-radius: {C.RADIUS_TILE}px;
}}
#tile:hover {{ background: {C.TILE_BG_HOVER}; }}
#tile-tag {{ color: {C.TEXT_FAINT}; font-weight: 700; font-size: 9px; font-family: Sans; }}
#tile-val {{ color: {C.TEXT}; font-weight: 700; font-size: 22px; font-family: Sans; }}
#tile-sub {{ color: {C.TEXT_FAINT}; font-weight: 500; font-size: 10px; font-family: Sans; }}

#scrub {{ background: rgba(255,255,255,0.12); border-radius: 2px; max-height: 4px; min-height: 4px; }}
#scrub-fill {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 {C.ACCENT_DEEP}, stop:1 {C.ACCENT2});
    border-radius: 2px;
}}
#wave {{
    background: qlineargradient(x1:0,y1:1,x2:0,y2:0,
        stop:0 {C.ACCENT_DEEP}, stop:1 {C.ACCENT2});
    border-radius: 2px;
    min-width: 3px; max-width: 3px;
}}
#wave[dims="true"] {{ background: rgba(255,255,255,0.18); }}

#footer {{
    background: rgba(255,255,255,0.04);
    border: 1px solid {C.GLASS_EDGE_SOFT};
    border-radius: {C.RADIUS_TILE}px;
}}
#foot-note {{ color: {C.TEXT_DIM}; font-weight: 500; font-size: 11px; font-family: Sans; }}
#big-clock {{ color: {C.TEXT}; font-weight: 700; font-size: 20px; font-family: Sans; }}

QSlider::groove:horizontal {{
    background: rgba(255,255,255,0.12);
    height: 4px; border-radius: 2px;
}}
QSlider::handle:horizontal {{
    background: {C.TEXT};
    width: 12px; height: 12px; margin: -4px 0;
    border-radius: 6px;
}}
QSlider::sub-page:horizontal {{
    background: {C.ACCENT};
    border-radius: 2px;
}}
"""
