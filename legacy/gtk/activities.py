"""Konten island: compact cluster ↔ expanded bento panel (Alcove-style glass).

Padanan temuan REA boring.notch:
  NowPlayingController  → kartu musik hero (MPRIS)
  AudioSpectrum         → waveform bar animasi saat playing
  Volume/BatteryManager → tile mini + HUD strip
  sneakPeek             → teks sekilas di baris status
"""
from __future__ import annotations

import math
import random

import gi

gi.require_version("Gtk", "3.0")

from gi.repository import Gdk, GdkPixbuf, GLib, Gtk, Pango  # noqa: E402

from . import config as C  # noqa: E402
from . import art as art_loader  # noqa: E402


class Activities(Gtk.Overlay):
    def __init__(self, window: Gtk.Window) -> None:
        super().__init__()
        self.window = window

        self._has_media = False
        self._playing = False
        self._sys_hint = ""
        self._art_color = "#4C6EF5"
        self._wave_level = 0.0
        self._wave_id = 0
        self._art_url = ""
        self._art_loaded_url = ""
        self._art_size = 72

        self.compact = self._build_compact()
        self.expanded = self._build_expanded()

        self.compact.set_halign(Gtk.Align.FILL)
        self.compact.set_valign(Gtk.Align.CENTER)
        self.expanded.set_halign(Gtk.Align.FILL)
        self.expanded.set_valign(Gtk.Align.FILL)
        self.add_overlay(self.compact)
        self.add_overlay(self.expanded)

        self._load_css()

    # ============================================================ COMPACT
    def _build_compact(self) -> Gtk.Widget:
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        row.set_margin_start(14)
        row.set_margin_end(14)

        # ikon musik: chip bulat beraksen
        self.compact_dot = Gtk.Label(label="♪")
        self.compact_dot.set_name("c-dot")
        row.pack_start(self.compact_dot, False, False, 0)

        self.compact_title = Gtk.Label(label="notchy")
        self.compact_title.set_ellipsize(Pango.EllipsizeMode.END)
        self.compact_title.set_halign(Gtk.Align.START)
        self.compact_title.set_name("c-title")
        row.pack_start(self.compact_title, True, True, 0)

        # waveform mini (AudioSpectrum analog)
        self.compact_wave = self._make_wave(4, h=12)
        row.pack_start(self.compact_wave, False, False, 0)

        # pemisah tipis
        sep = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        sep.set_name("c-sep")
        row.pack_start(sep, False, False, 0)

        self.compact_bat = Gtk.Label(label="—")
        self.compact_bat.set_name("c-chip")
        row.pack_start(self.compact_bat, False, False, 0)

        self.compact_clock = Gtk.Label(label="--:--")
        self.compact_clock.set_name("c-clock")
        row.pack_end(self.compact_clock, False, False, 0)
        return row

    # ============================================================ EXPANDED
    def _build_expanded(self) -> Gtk.Widget:
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        outer.set_margin_start(16)
        outer.set_margin_end(16)
        outer.set_margin_top(14)
        outer.set_margin_bottom(14)

        # ---------- kartu musik hero ----------
        hero = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)
        hero.set_name("hero")

        self.art = Gtk.Overlay()
        self.art.set_size_request(self._art_size, self._art_size)
        self.art.set_valign(Gtk.Align.CENTER)
        self.art.set_halign(Gtk.Align.CENTER)
        self.art.set_name("art-wrap")

        # fallback: gradasi warna + glif (saat art belum ada)
        art_bg = Gtk.Box()
        art_bg.set_name("art")
        self._art_css = Gtk.CssProvider()
        art_bg.get_style_context().add_provider(
            self._art_css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
        self.art.add(art_bg)

        self.art_glyph = Gtk.Label(label="♪")
        self.art_glyph.set_name("art-glyph")
        self.art_glyph.set_halign(Gtk.Align.CENTER)
        self.art_glyph.set_valign(Gtk.Align.CENTER)
        self.art.add_overlay(self.art_glyph)

        # thumbnail asli dari mpris:artUrl
        self.art_image = Gtk.Image()
        self.art_image.set_halign(Gtk.Align.FILL)
        self.art_image.set_valign(Gtk.Align.FILL)
        self.art_image.set_no_show_all(True)
        self.art.add_overlay(self.art_image)

        hero.pack_start(self.art, False, False, 0)

        info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        info.set_valign(Gtk.Align.CENTER)

        title_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.title = Gtk.Label(label="Tidak ada musik")
        self.title.set_halign(Gtk.Align.START)
        self.title.set_ellipsize(Pango.EllipsizeMode.END)
        self.title.set_name("h-title")
        title_row.pack_start(self.title, True, True, 0)

        self.badge = Gtk.Label(label="IDLE")
        self.badge.set_name("badge")
        title_row.pack_end(self.badge, False, False, 0)
        info.pack_start(title_row, False, False, 0)

        self.artist = Gtk.Label(label="Putar sesuatu di pemutar favoritmu")
        self.artist.set_halign(Gtk.Align.START)
        self.artist.set_ellipsize(Pango.EllipsizeMode.END)
        self.artist.set_name("h-sub")
        info.pack_start(self.artist, False, False, 0)

        # scrubber + waktu
        scrub = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.progress = Gtk.ProgressBar()
        self.progress.set_name("scrub")
        self.progress.set_show_text(False)
        scrub.pack_start(self.progress, False, False, 0)

        times = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.time_now = Gtk.Label(label="0:00")
        self.time_now.set_halign(Gtk.Align.START)
        self.time_now.set_name("t-tiny")
        times.pack_start(self.time_now, False, False, 0)
        self.time_len = Gtk.Label(label="0:00")
        self.time_len.set_halign(Gtk.Align.END)
        self.time_len.set_name("t-tiny")
        times.pack_end(self.time_len, False, False, 0)
        scrub.pack_start(times, False, False, 0)
        info.pack_start(scrub, False, False, 0)

        hero.pack_start(info, True, True, 0)

        # kontrol — segmented pill ala Alcove
        controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        controls.set_valign(Gtk.Align.CENTER)
        controls.set_name("seg")
        for label, handler, tip in (
            ("⏮", lambda *_: self.window.mpris.previous(), "Previous"),
            ("⏯", lambda *_: self.window.mpris.play_pause(), "Play / Pause"),
            ("⏭", lambda *_: self.window.mpris.next(), "Next"),
        ):
            btn = Gtk.Button(label=label)
            btn.set_name("seg-btn")
            btn.set_tooltip_text(tip)
            btn.set_relief(Gtk.ReliefStyle.NONE)
            btn.connect("clicked", handler)
            controls.pack_start(btn, False, False, 0)
        hero.pack_end(controls, False, False, 0)

        outer.pack_start(hero, False, False, 0)

        # ---------- bento tiles ----------
        tiles = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)

        self.tile_vol = self._tile("VOL", "—", "Volume", accent=C.ACCENT)
        self.tile_bat = self._tile("BAT", "—", "Battery", accent=C.ACCENT_GREEN)
        self.tile_cpu = self._tile("CPU", "—", "Processor", accent=C.ACCENT2)
        self.tile_ram = self._tile("RAM", "—", "Memory", accent=C.ACCENT_WARM)

        self.vol_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
        self.vol_scale.set_draw_value(False)
        self.vol_scale.set_name("tile-scale")
        self.vol_scale.connect("change-value", self._on_volume)
        self.tile_vol["body"].pack_start(self.vol_scale, False, False, 0)

        for t in (self.tile_vol, self.tile_bat, self.tile_cpu, self.tile_ram):
            tiles.pack_start(t["frame"], True, True, 0)

        outer.pack_start(tiles, False, False, 0)

        # ---------- footer: waveform + jam ----------
        footer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        footer.set_name("footer")

        self.footer_wave = self._make_wave(18, h=18)
        footer.pack_start(self.footer_wave, False, False, 0)

        self.now_label = Gtk.Label(label="")
        self.now_label.set_halign(Gtk.Align.START)
        self.now_label.set_ellipsize(Pango.EllipsizeMode.END)
        self.now_label.set_name("foot-note")
        footer.pack_start(self.now_label, True, True, 0)

        clock_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.clock_label = Gtk.Label(label="--:--")
        self.clock_label.set_halign(Gtk.Align.END)
        self.clock_label.set_name("big-clock")
        clock_box.pack_start(self.clock_label, False, False, 0)
        self.date_label = Gtk.Label(label="")
        self.date_label.set_halign(Gtk.Align.END)
        self.date_label.set_name("t-tiny")
        clock_box.pack_start(self.date_label, False, False, 0)
        footer.pack_end(clock_box, False, False, 0)

        outer.pack_end(footer, False, False, 0)
        return outer

    # ------------------------------------------------------------ widgets
    def _tile(self, tag: str, value: str, label: str, accent: str) -> dict:
        frame = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        frame.set_name("tile")
        frame.set_size_request(112, -1)

        head = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        tag_lbl = Gtk.Label(label=tag)
        tag_lbl.set_name("tile-tag")
        # titik aksen
        dot = Gtk.Label(label="●")
        dot.set_name("tile-dot")
        self._tint(dot, accent)
        head.pack_start(dot, False, False, 0)
        head.pack_start(tag_lbl, False, False, 0)
        frame.pack_start(head, False, False, 0)

        val = Gtk.Label(label=value)
        val.set_halign(Gtk.Align.START)
        val.set_name("tile-val")
        frame.pack_start(val, False, False, 0)

        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        sub = Gtk.Label(label=label)
        sub.set_halign(Gtk.Align.START)
        sub.set_name("t-tiny")
        body.pack_start(sub, False, False, 0)
        frame.pack_start(body, True, True, 0)

        return {"frame": frame, "val": val, "body": body}

    def _make_wave(self, count: int, h: int = 14) -> Gtk.Box:
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=3)
        box.set_valign(Gtk.Align.CENTER)
        bars = []
        for _ in range(count):
            bar = Gtk.Box()
            bar.set_name("wave")
            bar.set_size_request(3, max(3, h // 3))
            box.pack_start(bar, False, False, 0)
            bars.append(bar)
        # simpan di instance lewat atribut dinamis rapi
        if not hasattr(self, "_waves"):
            self._waves = []
        self._waves.append((bars, h))
        return box

    @staticmethod
    def _tint(label: Gtk.Label, color: str) -> None:
        css = f"#{Gtk.Buildable.get_name(label) or ''} {{ }}"  # placeholder aman
        provider = Gtk.CssProvider()
        # pakai inline name unik
        name = f"tint{id(label) & 0xffff}"
        label.set_name(name)
        provider.load_from_data(f"#{name} {{ color: {color}; }}".encode())
        label.get_style_context().add_provider(
            provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
        del css

    # ------------------------------------------------------------ CSS
    def _load_css(self) -> None:
        css = f"""
        #c-dot {{
            color: {C.ACCENT};
            font: 700 15px Sans;
            background: rgba(110, 139, 255, 0.18);
            border-radius: {C.RADIUS_PILL}px;
            min-width: 26px; min-height: 26px;
        }}
        #c-title {{ color: {C.TEXT}; font: 600 12px Sans; }}
        #c-chip {{
            color: {C.TEXT_DIM}; font: 600 11px Sans;
            background: {C.TILE_BG}; padding: 3px 9px;
            border-radius: {C.RADIUS_PILL}px;
        }}
        #c-clock {{ color: {C.TEXT}; font: 700 13px Sans; margin-left: 6px; }}
        #c-sep {{ background: rgba(255,255,255,0.10); min-width: 1px; margin: 4px 2px; }}

        #hero {{
            background: {C.TILE_BG};
            border-radius: {C.RADIUS_TILE}px;
            border: 1px solid {C.GLASS_EDGE_SOFT};
            padding: 12px;
        }}
        #art-wrap {{ border-radius: 14px; }}
        #art {{
            background-color: {C.ACCENT_DEEP};
            border-radius: 14px;
            border: 1px solid rgba(255,255,255,0.12);
        }}
        #art-glyph {{ color: rgba(255,255,255,0.85); font: 700 26px Sans; }}

        #h-title {{ color: {C.TEXT}; font: 700 15px Sans; }}
        #h-sub {{ color: {C.TEXT_DIM}; font: 500 12px Sans; }}
        #badge {{
            color: {C.ACCENT}; font: 700 9px Sans;
            background: rgba(110,139,255,0.16);
            padding: 3px 8px; border-radius: {C.RADIUS_PILL}px;
        }}
        #badge.playing {{ color: {C.ACCENT_GREEN}; background: rgba(81,207,102,0.16); }}

        #scrub trough {{ background: rgba(255,255,255,0.12); border-radius: 3px; min-height: 4px; }}
        #scrub progress {{ background: linear-gradient(to right, {C.ACCENT_DEEP}, {C.ACCENT2});
                           border-radius: 3px; min-height: 4px; }}
        #t-tiny {{ color: {C.TEXT_FAINT}; font: 500 10px Sans; }}

        #seg {{
            background: rgba(255,255,255,0.06);
            border-radius: {C.RADIUS_PILL}px;
            border: 1px solid {C.GLASS_EDGE_SOFT};
            padding: 2px;
        }}
        #seg-btn {{
            color: {C.TEXT}; font: 600 13px Sans;
            min-width: 34px; min-height: 30px;
            border-radius: {C.RADIUS_PILL}px;
            background: transparent;
            border: none;
            transition: 150ms ease;
        }}
        #seg-btn:hover {{ background: rgba(255,255,255,0.12); }}
        #seg-btn:active {{ background: rgba(110,139,255,0.35); }}

        #tile {{
            background: {C.TILE_BG};
            border-radius: {C.RADIUS_TILE}px;
            border: 1px solid {C.GLASS_EDGE_SOFT};
            padding: 10px 12px;
            transition: 150ms ease;
        }}
        #tile:hover {{ background: {C.TILE_BG_HOVER}; }}
        #tile-tag {{ color: {C.TEXT_FAINT}; font: 700 9px Sans; letter-spacing: 1px; }}
        #tile-dot {{ font: 700 8px Sans; margin-right: 2px; }}
        #tile-val {{ color: {C.TEXT}; font: 700 22px Sans; }}
        #tile-scale {{ min-width: 80px; margin-top: 2px; }}
        #tile-scale trough {{ background: rgba(255,255,255,0.12); border-radius: 3px; min-height: 4px; }}
        #tile-scale highlight {{ background: {C.ACCENT}; border-radius: 3px; }}
        #tile-scale slider {{ background: {C.TEXT}; min-width: 12px; min-height: 12px;
                              border-radius: 6px; }}

        #wave {{
            background: linear-gradient(to top, {C.ACCENT_DEEP}, {C.ACCENT2});
            border-radius: 2px;
            min-width: 3px;
        }}
        #wave.dim {{ background: rgba(255,255,255,0.18); }}

        #footer {{
            background: rgba(255,255,255,0.04);
            border-radius: {C.RADIUS_TILE}px;
            border: 1px solid {C.GLASS_EDGE_SOFT};
            padding: 8px 12px;
        }}
        #foot-note {{ color: {C.TEXT_DIM}; font: 500 11px Sans; }}
        #big-clock {{ color: {C.TEXT}; font: 700 20px Sans; }}

        scale trough {{ background: rgba(255,255,255,0.12); border-radius: 3px; min-height: 4px; }}
        scale highlight {{ background: {C.ACCENT}; border-radius: 3px; }}
        scale slider {{ background: {C.TEXT}; min-width: 12px; min-height: 12px; border-radius: 6px; }}
        """
        provider = Gtk.CssProvider()
        provider.load_from_data(css.encode())
        screen = Gdk.Screen.get_default()
        Gtk.StyleContext.add_provider_for_screen(
            screen, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
        self._set_art_color(self._art_color)

    def _set_art_color(self, color: str) -> None:
        # gradasi art dari warna dasar
        css = f"#art {{ background-image: linear-gradient(135deg, {color}, rgba(255,255,255,0.18)); }}"
        self._art_css.load_from_data(css.encode())

    # ------------------------------------------------------------ morph
    def set_opacity_for(self, t: float) -> None:
        self.compact.set_opacity(max(0.0, 1.0 - t * 1.7))
        self.expanded.set_opacity(max(0.0, min(1.0, (t - 0.18) * 1.55)))
        self.compact.set_sensitive(t < 0.55)
        self.expanded.set_sensitive(t > 0.35)
        # waveform hanya hidup saat playing
        self._sync_wave()

    # ------------------------------------------------------------ update
    def _show_art_fallback(self) -> None:
        self.art_image.hide()
        self.art_glyph.set_opacity(1.0)
        self._set_art_color(self._art_color)
        self._art_loaded_url = ""

    def _on_art_loaded(self, path, url: str) -> None:
        # abaikan hasil basi (lagu sudah berganti)
        if url != self._art_url:
            return
        if not path:
            self._show_art_fallback()
            return
        pb = art_loader.load_thumbnail(path, self._art_size, radius=14)
        if pb is None:
            self._show_art_fallback()
            return
        self.art_image.set_from_pixbuf(pb)
        self.art_image.show()
        self.art_glyph.set_opacity(0.0)
        self._art_loaded_url = url

    def _update_art(self, art_url: str) -> None:
        url = art_url or ""
        if url == self._art_loaded_url and url:
            return  # sudah tampil
        if url == self._art_url and url and self._art_loaded_url:
            return
        if url != self._art_url:
            self._art_url = url
            if not url:
                self._show_art_fallback()
                return
            # tampilkan fallback dulu, lalu ganti saat unduhan selesai
            if not self._art_loaded_url:
                self._show_art_fallback()
            art_loader.fetch_async(url, lambda p, u=url: self._on_art_loaded(p, u))

    def update_media(self, np) -> None:
        self._has_media = bool(np.available and np.title)
        self._playing = bool(np.playing)
        if self._has_media:
            label = np.title if not np.artist else f"{np.title} — {np.artist}"
            self.compact_title.set_text(label)
            self.compact_dot.set_text("♪")
            self.title.set_text(np.title or "(no title)")
            self.artist.set_text(np.artist or np.album or np.identity or "")
            self.progress.set_fraction(np.progress or 0.0)
            self.time_now.set_text(fmt_time(np.position))
            self.time_len.set_text(fmt_time(np.length))
            color = color_from_text(np.album or np.title or np.identity)
            self._art_color = color
            self._set_art_color(color)
            self.badge.set_text("PLAYING" if np.playing else "PAUSED")
            ctx = self.badge.get_style_context()
            if np.playing:
                ctx.add_class("playing")
            else:
                ctx.remove_class("playing")
            parts = [p for p in (np.identity, np.album) if p]
            self.now_label.set_text(" · ".join(parts) if parts else "MPRIS")
            self._update_art(np.art_url or "")
        else:
            self.compact_title.set_text("notchy")
            self.compact_dot.set_text("✦")
            self.title.set_text("Tidak ada musik")
            self.artist.set_text("Putar sesuatu di pemutar favoritmu")
            self.progress.set_fraction(0.0)
            self.time_now.set_text("0:00")
            self.time_len.set_text("0:00")
            self._art_color = C.ACCENT_DEEP
            self._set_art_color(self._art_color)
            self.badge.set_text("IDLE")
            self.badge.get_style_context().remove_class("playing")
            self.now_label.set_text("Live activities siap — hover untuk membuka")
            self._art_url = ""
            self._show_art_fallback()
        self._sync_wave()

    def update_system(self, bat, vol, sysmon) -> None:
        if bat.present:
            icon = "⚡" if bat.charging else ""
            self.tile_bat["val"].set_text(f"{bat.percent}%")
            self.compact_bat.set_text(f"{icon}🔋{bat.percent}%")
            self._sys_hint = f"{bat.percent}%"
        else:
            self.tile_bat["val"].set_text("AC")
            self.compact_bat.set_text("AC")
            self._sys_hint = "AC"

        self.tile_vol["val"].set_text(f"{vol.level}%")
        self.tile_cpu["val"].set_text(f"{int(sysmon.cpu_percent)}%")
        self.tile_ram["val"].set_text(f"{int(sysmon.ram_percent)}%")

        if self.vol_scale.get_value() != vol.level:
            self.vol_scale.set_value(vol.level)

    def update_clock(self, clock) -> None:
        self.clock_label.set_text(clock.time_str)
        self.date_label.set_text(clock.date_str)
        self.compact_clock.set_text(clock.time_str)

    # ------------------------------------------------------------ waveform
    def _sync_wave(self) -> None:
        want = self._playing
        running = self._wave_id != 0
        if want and not running:
            self._wave_id = GLib.timeout_add(C.WAVE_TICK_MS, self._wave_tick)
        elif not want and running:
            GLib.source_remove(self._wave_id)
            self._wave_id = 0
            for bars, h in getattr(self, "_waves", []):
                for b in bars:
                    b.set_size_request(3, max(3, h // 4))
                    if "dim" not in b.get_style_context().list_classes():
                        b.get_style_context().add_class("dim")
        if want:
            for bars, _h in getattr(self, "_waves", []):
                for b in bars:
                    b.get_style_context().remove_class("dim")

    def _wave_tick(self) -> bool:
        # level pseudo-audio: random-walk halus (padanan AudioSpectrum)
        self._wave_level = max(0.15, min(1.0, self._wave_level + random.uniform(-0.28, 0.32)))
        phase = GLib.get_monotonic_time() / 1e6
        for bars, h in getattr(self, "_waves", []):
            n = len(bars)
            for i, bar in enumerate(bars):
                wobble = 0.5 + 0.5 * math.sin(phase * 5.0 + i * 0.9)
                level = self._wave_level * wobble
                height = max(3, int(3 + level * (h - 3)))
                bar.set_size_request(3, height)
        return True

    # ------------------------------------------------------------ aksi
    def _on_volume(self, _scale, _scroll, value: float) -> bool:
        self.window.volume.set_level(int(value))
        self.tile_vol["val"].set_text(f"{int(value)}%")
        return False


def fmt_time(seconds: float) -> str:
    if not seconds or seconds < 0:
        return "0:00"
    m, s = divmod(int(seconds), 60)
    if m >= 60:
        h, m = divmod(m, 60)
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def color_from_text(text: str) -> str:
    """Warna art pseudo-stabil dari teks — pengganti artwork fetch."""
    h = 0
    for ch in text:
        h = (h * 131 + ord(ch)) & 0xFFFFFFFF
    palette = ["#4C6EF5", "#7C5CFF", "#E64980", "#F76707", "#0CA678", "#1098AD", "#AE3EC9"]
    return palette[h % len(palette)]
