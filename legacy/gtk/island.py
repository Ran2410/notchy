"""Island window: pill hitam top-center yang me-morph jadi panel live activity.

Padanan temuan REA boring.notch:
  BoringNotchSkyLightWindow  → IslandWindow (borderless, keep-above, top-center)
  NotchShape / NotchState    → cairo rounded-rect + state machine t∈[0,1]
  openNotchOnHover           → enter/leave-notify → expand/collapse
  closeNotchTask             → GLib timeout penutupan otomatis
  SwiftUI spring             → ease-out cubic interpolation per frame
"""
from __future__ import annotations

import time

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")

from gi.repository import Gdk, GLib, Gtk  # noqa: E402

from . import config as C  # noqa: E402
from .activities import Activities  # noqa: E402
from .providers import (  # noqa: E402
    BatteryProvider,
    ClockProvider,
    MprisProvider,
    SystemProvider,
    VolumeProvider,
)


def ease_out_cubic(t: float) -> float:
    return 1.0 - (1.0 - t) ** C.EASE_POWER


class IslandWindow(Gtk.Window):
    def __init__(self) -> None:
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        self.set_title("notchy")
        self.set_decorated(False)
        self.set_resizable(False)
        self.set_accept_focus(True)
        self.set_keep_above(True)
        self.set_type_hint(Gdk.WindowTypeHint.DOCK)
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)
        self.set_app_paintable(True)

        # transparansi penuh untuk sudut membulat
        screen = self.get_screen()
        visual = screen.get_rgba_visual()
        if visual is not None:
            self.set_visual(visual)
        else:
            self.set_visual(screen.get_system_visual())

        # providers (live activity)
        self.mpris = MprisProvider()
        self.volume = VolumeProvider()
        self.battery = BatteryProvider()
        self.clock = ClockProvider()
        self.sysmon = SystemProvider()

        # state morph: 0 = closed (pill), 1 = open (panel)
        self._t = 0.0
        self._target = 0.0
        self._anim_start = 0.0
        self._anim_from = 0.0
        self._anim_id = 0
        self._close_id = 0
        self._pointer_inside = False
        self._pinned = False  # klik untuk kunci terbuka

        self.activities = Activities(self)

        # permukaan island: rounded-rect via CSS (tanpa cairo)
        self.surface = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.surface.set_name("island-bg")
        self.surface.pack_start(self.activities, True, True, 0)
        self.add(self.surface)
        self._load_window_css()
        self.activities.show_all()
        self.activities.set_opacity_for(self._t)

        self.connect("enter-notify-event", self._on_enter)
        self.connect("leave-notify-event", self._on_leave)
        self.connect("button-press-event", self._on_button)
        self.connect("destroy", Gtk.main_quit)

        self._apply_size(C.CLOSED_W, C.CLOSED_H)
        self._position_top_center()
        self.show_all()

        # poll data
        GLib.timeout_add(C.POLL_MPRIS_MS, self._poll_media)
        GLib.timeout_add(C.POLL_SYS_MS, self._poll_sys)
        GLib.timeout_add(1000, self._poll_clock)
        self._poll_media()
        self._poll_sys()
        self._poll_clock()

    # ------------------------------------------------------------ layout
    def _current_size(self) -> tuple[int, int]:
        w = C.CLOSED_W + (C.OPEN_W - C.CLOSED_W) * self._t
        h = C.CLOSED_H + (C.OPEN_H - C.CLOSED_H) * self._t
        return int(round(w)), int(round(h))

    def _apply_size(self, w: int, h: int) -> None:
        self.set_size_request(w, h)
        self.resize(w, h)

    def _position_top_center(self) -> None:
        monitor = self.get_display().get_primary_monitor()
        if monitor is None:
            geo = self.get_screen().get_root_window().get_geometry()
            mon_w, mon_x, mon_y = geo.width, geo.x, geo.y
        else:
            geo = monitor.get_geometry()
            mon_w, mon_x, mon_y = geo.width, geo.x, geo.y
        w, _ = self._current_size()
        x = mon_x + max(C.SIDE_MIN_MARGIN, (mon_w - w) // 2)
        y = mon_y + C.TOP_MARGIN
        self.move(x, y)

    # ------------------------------------------------------------ animasi
    def _animate_to(self, target: float) -> None:
        target = 0.0 if target <= 0 else 1.0
        if target == self._target and self._t == target:
            return
        self._target = target
        self._anim_from = self._t
        self._anim_start = time.monotonic()
        if not self._anim_id:
            self._anim_id = GLib.timeout_add(16, self._anim_tick)

    def _anim_tick(self) -> bool:
        elapsed = (time.monotonic() - self._anim_start) * 1000.0
        u = min(1.0, elapsed / C.ANIM_MS)
        e = ease_out_cubic(u)
        self._t = self._anim_from + (self._target - self._anim_from) * e

        w, h = self._current_size()
        self._apply_size(w, h)
        self._position_top_center()
        self.activities.set_opacity_for(self._t)
        self.queue_draw()

        if u >= 1.0:
            self._t = self._target
            self._anim_id = 0
            return False
        return True

    def expand(self) -> None:
        self._cancel_close()
        self._animate_to(1.0)

    def collapse(self) -> None:
        if self._pinned:
            return
        self._animate_to(0.0)

    def toggle(self) -> None:
        self._pinned = not self._pinned
        self._animate_to(1.0 if self._pinned or self._pointer_inside else 0.0)

    # ------------------------------------------------------------ interaksi
    def _on_enter(self, _w, _ev) -> bool:
        self._pointer_inside = True
        self._cancel_close()
        self._animate_to(1.0)
        return False

    def _on_leave(self, _w, ev) -> bool:
        # abaikan leave fiktif ketika anak widget menerima event
        if ev.detail == Gdk.NotifyType.INFERIOR:
            return False
        self._pointer_inside = False
        self._schedule_close()
        return False

    def _schedule_close(self) -> None:
        self._cancel_close()
        self._close_id = GLib.timeout_add(C.CLOSE_DELAY_MS, self._close_now)

    def _cancel_close(self) -> None:
        if self._close_id:
            GLib.source_remove(self._close_id)
            self._close_id = 0

    def _close_now(self) -> bool:
        self._close_id = 0
        if not self._pointer_inside:
            self._pinned = False
            self.collapse()
        return False

    def _on_button(self, _w, ev) -> bool:
        if ev.button == 3:  # klik kanan → menu
            menu = Gtk.Menu()
            quit_item = Gtk.MenuItem(label="Quit notchy")
            quit_item.connect("activate", lambda *_: Gtk.main_quit())
            menu.append(quit_item)
            menu.show_all()
            menu.popup_at_pointer(ev)
            return True
        if ev.button == 1 and self._t < 0.15:
            self.toggle()
        return False

    # ------------------------------------------------------------ polling
    def _poll_media(self) -> bool:
        self.mpris.refresh()
        self.activities.update_media(self.mpris.state)
        return True

    def _poll_sys(self) -> bool:
        self.volume.refresh()
        self.battery.refresh()
        self.sysmon.refresh()
        self.activities.update_system(self.battery, self.volume, self.sysmon)
        return True

    def _poll_clock(self) -> bool:
        self.clock.refresh()
        self.activities.update_clock(self.clock)
        return True

    # ------------------------------------------------------------ CSS
    def _load_window_css(self) -> None:
        # dark glass ala Alcove: sheen gradient + soft edge + deep shadow.
        # border-radius konstan 24px → pill otomatis saat tinggi kecil
        css = f"""
        window {{ background-color: transparent; }}
        #island-bg {{
            background-image: linear-gradient(
                to bottom,
                rgba(28, 28, 38, 0.96),
                rgba(14, 14, 20, 0.94) 42%,
                rgba(10, 10, 15, 0.96));
            border-radius: {C.RADIUS_ISLAND}px;
            border: 1px solid {C.GLASS_EDGE};
            box-shadow:
                0 18px 48px rgba(0, 0, 0, 0.55),
                0 2px 8px rgba(0, 0, 0, 0.35),
                inset 0 1px 0 rgba(255, 255, 255, 0.10);
        }}
        """
        provider = Gtk.CssProvider()
        provider.load_from_data(css.encode())
        screen = Gdk.Screen.get_default()
        Gtk.StyleContext.add_provider_for_screen(
            screen, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
        self.surface.set_size_request(C.CLOSED_W, C.CLOSED_H)
