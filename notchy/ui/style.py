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
#c-art {{
    background: transparent;
    border-radius: 9px;
}}
#c-sub {{
    color: {C.TEXT_FAINT};
    font-weight: 500; font-size: 10px; font-family: "Inter";
}}
#c-time-chip {{
    color: {C.TEXT};
    background: rgba(255,255,255,0.07);
    border-radius: 11px;
    padding: 0 7px;
    font-weight: 600; font-size: 10px; font-family: "Inter";
}}
#tab-logo {{ background: transparent; }}
#c-title {{ color: {C.TEXT}; font-weight: 600; font-size: 13px; font-family: "Inter"; }}
#c-chip {{
    color: {C.TEXT_DIM};
    background: {C.TILE_BG};
    border-radius: 12px;
    font-weight: 600; font-size: 11px; font-family: "Inter";
}}
#c-clock {{ color: {C.TEXT_DIM}; font-weight: 700; font-size: 11px; font-family: "Inter"; }}
#c-sep {{ background: rgba(255,255,255,0.10); max-width: 1px; min-width: 1px; }}

#hero {{
    background: transparent;
    border: none;
}}
#h-title {{ color: {C.TEXT}; font-weight: 600; font-size: 18px; font-family: "Inter"; }}
#h-sub {{ color: {C.TEXT_DIM}; font-weight: 400; font-size: 13px; font-family: "Inter"; }}
#badge {{
    color: {C.ACCENT};
    background: rgba(110,139,255,0.16);
    border-radius: {C.RADIUS_PILL}px;
    font-weight: 700; font-size: 9px; font-family: "Inter";
}}
#badge[playing="true"] {{
    color: {C.ACCENT_GREEN};
    background: rgba(81,207,102,0.16);
}}
#t-tiny {{ color: {C.TEXT_FAINT}; font-weight: 400; font-size: 11px; font-family: "Inter"; }}

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
    font-weight: 600; font-size: 13px; font-family: "Inter";
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
#tile-tag {{ color: {C.TEXT_FAINT}; font-weight: 600; font-size: 11px; font-family: "Inter"; }}
#tile-val {{ color: {C.TEXT}; font-weight: 600; font-size: 20px; font-family: "Inter"; }}
#tile-sub {{ color: {C.TEXT_FAINT}; font-weight: 400; font-size: 11px; font-family: "Inter"; }}

#scrub {{ background: rgba(255,255,255,0.12); border-radius: 2px; max-height: 4px; min-height: 4px; }}
#scrub-fill {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 {C.ACCENT_DEEP}, stop:1 {C.ACCENT2});
    border-radius: 2px;
}}
#wave {{
    background: qlineargradient(x1:0,y1:1,x2:0,y2:0,
        stop:0 {C.ACCENT_DEEP}, stop:0.55 {C.ACCENT}, stop:1 {C.ACCENT_CYAN});
    border-radius: 2px;
}}
#wave[dims="true"] {{ background: rgba(255,255,255,0.18); }}

#footer {{
    background: transparent;
    border: none;
}}
#divider {{
    background: rgba(255,255,255,0.06);
    border: none;
    min-height: 1px; max-height: 1px;
}}
#foot-note {{ color: {C.TEXT_DIM}; font-weight: 400; font-size: 12px; font-family: "Inter"; }}
#big-clock {{ color: {C.TEXT}; font-weight: 600; font-size: 22px; font-family: "Inter"; }}

#timer-strip {{
    background: {C.TILE_BG};
    border: 1px solid {C.GLASS_EDGE_SOFT};
    border-radius: {C.RADIUS_TILE}px;
}}
#t-icon {{ color: {C.ACCENT_WARM}; font-weight: 700; font-size: 14px; font-family: "Inter"; }}
#t-label {{ color: {C.TEXT_DIM}; font-weight: 600; font-size: 11px; font-family: "Inter"; }}
#t-value {{ color: {C.TEXT}; font-weight: 600; font-size: 20px; font-family: "Inter"; }}
#t-chip {{
    color: {C.TEXT_DIM};
    background: rgba(255,255,255,0.07);
    border-radius: 12px;
    font-weight: 600; font-size: 11px; font-family: "Inter";
}}
#t-chip:hover {{ background: rgba(255,255,255,0.14); color: {C.TEXT}; }}
#t-value-big {{ color: {C.TEXT}; font-weight: 600; font-size: 40px; font-family: "Inter"; }}

#tab-arrow {{
    color: {C.TEXT_DIM};
    background: rgba(255,255,255,0.06);
    border: 1px solid {C.GLASS_EDGE_SOFT};
    border-radius: 15px;
    font-weight: 700; font-size: 18px; font-family: "Inter";
}}
#tab-arrow:hover {{ background: rgba(255,255,255,0.14); color: {C.TEXT}; }}
#tab-title {{ color: {C.TEXT}; font-weight: 700; font-size: 13px; font-family: "Inter"; }}
#tab-dots {{ color: {C.ACCENT}; font-weight: 700; font-size: 10px; font-family: "Inter"; }}

#toggle-btn {{
    color: {C.TEXT_DIM};
    background: transparent;
    border: none;
    border-radius: 16px;
    font-weight: 600; font-size: 14px; font-family: "Inter";
}}
#toggle-btn:hover {{ background: rgba(255,255,255,0.08); color: {C.TEXT}; }}

/* --- tab Info: cuaca / unduhan --- */
#info-card {{
    background: {C.TILE_BG};
    border: 1px solid {C.GLASS_EDGE_SOFT};
    border-radius: {C.RADIUS_TILE}px;
}}
#info-card:hover {{ background: {C.TILE_BG_HOVER}; }}
#wx-icon {{ color: {C.ACCENT_WARM}; font-weight: 700; font-size: 22px; font-family: "Inter"; }}
#wx-temp {{ color: {C.TEXT}; font-weight: 600; font-size: 24px; font-family: "Inter"; }}
#wx-text {{ color: {C.TEXT_DIM}; font-weight: 400; font-size: 13px; font-family: "Inter"; }}
#info-tag {{ color: {C.TEXT_FAINT}; font-weight: 600; font-size: 11px; font-family: "Inter"; }}
#ag-title {{ color: {C.TEXT}; font-weight: 600; font-size: 14px; font-family: "Inter"; }}
#dl-name {{ color: {C.TEXT}; font-weight: 600; font-size: 12px; font-family: "Inter"; }}
#c-temp {{ color: {C.TEXT_DIM}; font-weight: 700; font-size: 11px; font-family: "Inter"; }}
#h-title2 {{ color: {C.TEXT}; font-weight: 700; font-size: 12px; font-family: "Inter"; }}
#np-tag {{ color: {C.TEXT_FAINT}; font-weight: 600; font-size: 11px; font-family: "Inter"; }}
#np-src {{ color: {C.TEXT_DIM}; font-weight: 400; font-size: 11px; font-family: "Inter"; }}
#chip-btn {{
    background: transparent;
    border: none;
    border-radius: 999px;
}}
#chip-btn:hover {{ background: rgba(255,255,255,0.08); }}
#sync-chip {{ background: transparent; border: none; }}
#chip-btn-txt {{ color: {C.TEXT_DIM}; font-weight: 500; font-size: 12px; font-family: "Inter"; }}
#play-big {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
        stop:0 {C.ACCENT_DEEP}, stop:1 {C.ACCENT2});
    border-radius: 26px;
    color: #12081f;
    font-weight: 700; font-size: 17px; font-family: "Inter";
}}
#play-big:hover {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
        stop:0 {C.ACCENT}, stop:1 #d9ccff); }}
#lyric-line {{
    color: rgba(228,225,233,0.42);
    background: transparent;
    font-weight: 400; font-size: 14px; font-family: "Inter";
}}
#lyr-accent {{
    background: {C.ACCENT};
    border-radius: 2px;
}}
#lyr-time {{
    color: {C.TEXT_DIM};
    font-weight: 600; font-size: 9px; font-family: "Inter";
}}
#lyr-title {{ color: {C.TEXT}; font-weight: 600; font-size: 14px; font-family: "Inter"; }}
#lyr-sub {{ color: {C.TEXT_FAINT}; font-weight: 400; font-size: 12px; font-family: "Inter"; }}
#lyr-dot {{ color: {C.ACCENT_GREEN}; font-size: 8px; font-family: "Inter"; }}
#sync-dot {{ color: {C.ACCENT_GREEN}; font-size: 8px; font-family: "Inter"; }}
#play-small {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
        stop:0 {C.ACCENT_DEEP}, stop:1 {C.ACCENT2});
    border-radius: 18px;
    color: #12081f;
    font-weight: 700; font-size: 13px; font-family: "Inter";
}}
#lyrics-scroll, #lyrics-scroll QWidget,
#lyrics-scroll QWidget#qt_scrollarea_viewport {{ background: transparent; }}
#lyrics-scroll {{ border: none; }}
#lyrics-scroll QScrollBar:vertical {{
    background: transparent; width: 6px; margin: 0;
}}
#lyrics-scroll QScrollBar::handle:vertical {{
    background: rgba(255,255,255,0.18); border-radius: 3px; min-height: 20px;
}}
#lyrics-scroll QScrollBar::add-line:vertical,
#lyrics-scroll QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollArea {{ background: transparent; }}
#h-icon {{ color: {C.ACCENT_WARM}; font-weight: 700; font-size: 14px; font-family: "Inter"; }}
#h-temp {{ color: {C.TEXT}; font-weight: 600; font-size: 11px; font-family: "Inter"; }}
#ag-row {{ color: {C.TEXT_DIM}; font-weight: 500; font-size: 11px; font-family: "Inter"; }}

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
