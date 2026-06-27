import math
import cairo
import logging
from gi.repository import Gtk, Gdk, GLib

from panels.mmu_mixin import *


class MmuSpoolTray(Gtk.DrawingArea):
    MAX_DISPLAY = 13

    def __init__(self, printer):
        super().__init__()
        self._printer = printer
        self._items = None
        self._spool_cache = {}

        self._hitboxes = []  # list of (gate, x, y, w, h)
        self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        self.connect("button-press-event", self._on_button_press)

        self._popover = None
        self._popover_timeout_id = None
        self._click_shield = None
        self._click_overlay = None

        self.set_size_request(360, 72)
        self.set_app_paintable(True)
        self.connect("draw", self._draw)


    def set_click_shield(self, shield, overlay):
        self._click_shield = shield
        self._click_shield_overlay = overlay

        self._click_shield.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        self._click_shield.connect("button-press-event", self._on_shield_button_press)

        self._click_shield.hide()
        self._click_shield_overlay.set_overlay_pass_through(self._click_shield, True)


    def refresh(self):
        self._items = self._build_items()
        self.queue_draw()


    def _build_items(self):
        mmu = self._printer.get_stat("mmu")
        gate_status = mmu["gate_status"]
        gate_color = mmu["gate_color"]
        selected_gate = mmu["gate"]

        unit_selected = mmu.get("unit")
        groups = []

        if unit_selected is not None:
            machine = self._printer.get_stat("mmu_machine")

            for unit_index in range(machine["num_units"]):
                unit = machine[f"unit_{unit_index}"]
                first = unit["first_gate"]
                count = unit["num_gates"]

                group = []
                for g in range(first, first + count):
                    group.append(self._gate_item(g, gate_status, gate_color, selected_gate))

                if unit.get("has_bypass", False):
                    group.append(self._bypass_item(selected_gate))

                groups.append(group)

            if not any(
                any(item["gate"] == TOOL_GATE_BYPASS for item in group)
                for group in groups
            ):
                groups.append([self._bypass_item(selected_gate)])
        else:
            groups.append([
                self._gate_item(g, gate_status, gate_color, selected_gate)
                for g in range(len(gate_status))
            ])

        flat_count = sum(len(g) for g in groups)
        if flat_count <= self.MAX_DISPLAY:
            return groups

        # Simple debug trim: keep first MAX_DISPLAY visible spools.
        trimmed = []
        remaining = self.MAX_DISPLAY

        for group in groups:
            if remaining <= 0:
                break

            part = group[:remaining]
            if part:
                trimmed.append(part)

            remaining -= len(part)

        return trimmed


    def _gate_item(self, g, gate_status, gate_color, selected_gate):
        status = gate_status[g]

        return {
            "gate": g,
            "color": MmuUtils.get_rgb_color(gate_color[g]) or "#777777",
            "empty": status == GATE_EMPTY,
            "selected": g == selected_gate,
            "status": status,
        }


    def _bypass_item(self, selected_gate):
        return {
            "gate": TOOL_GATE_BYPASS,
            "color": "#202020",
            "empty": False,
            "selected": selected_gate == TOOL_GATE_BYPASS,
            "status": GATE_EMPTY,
        }


    def _draw(self, widget, cr):
        alloc = self.get_allocation()
        width = alloc.width
        height = alloc.height
        self._hitboxes.clear()

        if self._items is None:
            self._items = self._build_items()

        groups = self._items
        total_spools = sum(len(g) for g in groups)
        if total_spools == 0:
            return False

        tray_pad_ratio = 0.25
        group_gap = 12

        margin = 6
        reserved_tray_pad = 18

        x = margin + reserved_tray_pad
        available_w = width - (margin + reserved_tray_pad) * 2 - group_gap * (len(groups) - 1)
        slot_w = available_w / max(total_spools, 1)

        # Deliberately wider than the slot so adjacent spools overlap.
        spool_h = height * 0.86
        spool_w = min(slot_w * 1.75, spool_h * 0.80)

        spool_cy = height * 0.42

        # Tray anchored to spool position.
        # Larger value = tray starts lower = covers less of the spool.
        tray_top = spool_cy + spool_h * 0.24
        tray_h = height - tray_top - 2

        tray_rects = []
        gate_badges = []

        for group in groups:
            group_start = x
            group_w = slot_w * len(group)

            for item in group:
                cx = x + slot_w / 2

                self._draw_spool(
                    cr,
                    cx,
                    spool_cy,
                    spool_w,
                    spool_h,
                    item["color"],
                    empty=item["empty"],
                    selected=item["selected"],
                )

                spool_x = cx - spool_w / 2
                spool_y = spool_cy - spool_h / 2
                self._hitboxes.append((item["gate"], spool_x, spool_y, spool_w, spool_h))
                gate_badges.append((item, cx, tray_top, tray_h, slot_w))

                x += slot_w

            tray_pad = slot_w * tray_pad_ratio
            tray_rects.append((group_start - tray_pad, tray_top, group_w + tray_pad * 2, tray_h))
            x += group_gap

        # Draw trays in foreground so they cover the lower part of the spools.
        for rect in tray_rects:
            self._draw_tray(cr, *rect)

        # Draw gate badges on top of the tray.
        for item, cx, tray_top, tray_h, slot_w in gate_badges:
            self._draw_gate_status(cr, item, cx, tray_top, tray_h, slot_w)

        return False


    def _draw_spool(self, cr, cx, cy, w, h, color, empty=False, selected=False, filament_pct=100):
        # Round to nearest 10% for efficient caching
        filament_pct = max(0, min(100, filament_pct))
        filament_pct = int(round(filament_pct / 10.0) * 10)

        key = (round(w), round(h), color, empty, int(filament_pct))
        surface = self._spool_cache.get(key)

        if surface is None:
            surface = cairo.ImageSurface(
                cairo.FORMAT_ARGB32,
                int(w + 14),
                int(h + 14),
            )
            c = cairo.Context(surface)
            c.translate(7, 7)
            self._render_spool(c, w, h, color, empty, filament_pct)
            self._spool_cache[key] = surface

            if len(self._spool_cache) > 64:
                self._spool_cache.clear()

        cr.set_source_surface(surface, cx - w / 2 - 7, cy - h / 2 - 7)
        cr.paint()

    def _render_spool(self, cr, w, h, color, empty, filament_pct=100):
        fr, fg, fb = self._parse_color(color)
        filament_pct = max(0.0, min(1.0, filament_pct / 100.0))

        # Cardboard colors
        cardboard      = (0.70, 0.52, 0.30)
        cardboard_dark = (0.38, 0.25, 0.12) # Recess on cardboard joins
        cardboard_edge = (0.20, 0.13, 0.06)

        left_x = w * 0.30
        right_x = w * 0.72

        outer_w = w * 0.20 # Orientation of spools to viewer
        outer_h = h * 0.88

        # Use the outer oval aspect ratio for all smaller ovals
        oval_ratio = outer_w / outer_h

        # Tube / center hole dimensions
        tube_h = outer_h * 0.38
        tube_w = tube_h * oval_ratio

        body_x = left_x
        body_w = right_x - left_x

        # Core rectangle
        core_y = h / 2 - tube_h / 2
        core_h = tube_h

        # Filament diameter varies with remaining amount.
        # 0%  = same height as the core/tube
        # 100% = slightly smaller than cardboard flange
        max_filament_h = outer_h * 0.8
        inner_h = tube_h + (max_filament_h - tube_h) * filament_pct
        inner_w = inner_h * oval_ratio * 0.8 # * 0.8 is because of lack of resolution on small display

        # Filament bulk rectangle matches the oval height.
        filament_h = inner_h
        filament_y = h / 2 - filament_h / 2

        # 1. Right cardboard oval (with edge)
        self._draw_oval(cr, right_x, h / 2, outer_w, outer_h, cardboard, cardboard_edge)

        # 2. Right core rounded tube end
        self._draw_oval(cr, right_x, h / 2, tube_w, tube_h, cardboard, cardboard_dark)

        # 3. Core body (rectangle)
        cr.set_source_rgb(*cardboard)
        cr.rectangle(body_x, core_y, body_w, core_h)
        cr.fill()

        if not empty and filament_pct > 0.0:
            # 4. Filament oval on right face
            self._draw_oval(cr, right_x, h / 2, inner_w, inner_h, (fr, fg, fb), cardboard_dark)

            # 5. Filament body (rectangle)
            cr.set_source_rgb(fr, fg, fb)
            cr.rectangle(body_x, filament_y, body_w, filament_h)
            cr.fill()

        # 6. Left cardboard oval
        self._draw_oval(cr, left_x, h / 2, outer_w, outer_h, cardboard, cardboard_edge)

        # 7. Left black hole
        self._draw_oval(cr, left_x, h / 2, tube_w, tube_h, (0.03, 0.025, 0.02), cardboard_edge)


    def _draw_gate_status(self, cr, item, cx, tray_top, tray_h, slot_w):
        badge_w = min(slot_w * 0.72, 34)
        badge_h = max(14, min(tray_h * 0.58, 20))
        badge_x = cx - badge_w / 2
        badge_y = tray_top + tray_h * 0.32
        radius = badge_h * 0.3

        selected_fill = (0.30, 1.00, 0.10)
        transparent_fill = (0, 0, 0, 0)

        if item["gate"] == TOOL_GATE_BYPASS:
            label = "Byp"
            fill_rgba = (*selected_fill, 1.0) if item["selected"] else transparent_fill
            stroke_rgb = None
        else:
            label = str(item["gate"])
            fill_rgba = (*selected_fill, 1.0) if item["selected"] else transparent_fill

            if item["status"] in (GATE_AVAILABLE, GATE_AVAILABLE_FROM_BUFFER):
                stroke_rgb = (0.20, 0.85, 0.20)
            elif item["status"] == GATE_EMPTY:
                stroke_rgb = (0.55, 0.55, 0.55)
            else:
                stroke_rgb = (1.00, 0.55, 0.05)

        self._draw_rounded_rect(cr, badge_x, badge_y, badge_w, badge_h, radius, fill_rgb=fill_rgba, stroke_rgb=stroke_rgb, stroke_width=1.2)

        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(max(10, badge_h * 0.82))

        xb, yb, tw, th, xa, ya = cr.text_extents(label)

        if item["selected"]:
            # Black text on bright green background.
            cr.set_source_rgb(0.0, 0.0, 0.0)
        else:
            style = self.get_style_context()
            fg = style.get_color(Gtk.StateFlags.NORMAL)
            cr.set_source_rgba(fg.red, fg.green, fg.blue, fg.alpha)

        cr.move_to(
            cx - tw / 2 - xb,
            badge_y + badge_h / 2 - th / 2 - yb,
        )
        cr.show_text(label)


    # ---------------------------------------------------------------------------
    # Pop-up action handling
    # ---------------------------------------------------------------------------

    def _hit_test_spool(self, px, py):
        # Reverse order because later spools visually overlap earlier ones.
        for gate, x, y, w, h in reversed(self._hitboxes):
            if x <= px <= x + w and y <= py <= y + h:
                return gate
        return None


    def _on_button_press(self, widget, event):
        if event.button != 1:
            return False

        gate = self._hit_test_spool(event.x, event.y)
        if gate is None:
            return False

        self._show_gate_popover(gate, event.x, event.y)
        return True


    def _on_shield_button_press(self, shield, event):
        # Convert shield coordinates to spool tray coordinates.
        coords = shield.translate_coordinates(self, event.x, event.y)

        self._close_gate_popover()

        if coords is not None:
            x, y = coords

            gate = self._hit_test_spool(x, y)
            if gate is not None:
                GLib.idle_add(
                    lambda: (
                        self._show_gate_popover(gate, x, y),
                        False,
                    )[1]
                )

        return True


    def _show_gate_popover(self, gate, x, y):
        self._close_gate_popover()

        popover = Gtk.Popover.new(self)
        self._popover = popover

        # Keep non-modal so another gate click can be handled by the shield.
        popover.set_modal(False)
        popover.set_position(Gtk.PositionType.BOTTOM)

        rect = Gdk.Rectangle()
        rect.x = int(x)
        rect.y = int(y)
        rect.width = 1
        rect.height = 1
        popover.set_pointing_to(rect)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.set_margin_top(6)
        box.set_margin_bottom(6)
        box.set_margin_start(6)
        box.set_margin_end(6)

        title = Gtk.Label(label=f"Gate {gate}" if gate != TOOL_GATE_BYPASS else "Bypass")
        title.get_style_context().add_class("heading")
        box.pack_start(title, False, False, 0)

        load_btn = Gtk.Button(label="Load")
        unload_btn = Gtk.Button(label="Unload")
        select_btn = Gtk.Button(label="Select")

        load_btn.connect("clicked", self._on_gate_action, gate, "load")
        unload_btn.connect("clicked", self._on_gate_action, gate, "unload")
        select_btn.connect("clicked", self._on_gate_action, gate, "select")

        box.pack_start(load_btn, False, False, 0)
        box.pack_start(unload_btn, False, False, 0)
        box.pack_start(select_btn, False, False, 0)

        popover.add(box)
        popover.show_all()
        popover.popup()

        if self._click_shield is not None:
            self._click_shield.show()
            if self._click_shield_overlay is not None:
                self._click_shield_overlay.set_overlay_pass_through(self._click_shield, False)

        self._popover_timeout_id = GLib.timeout_add_seconds(3, self._on_popover_timeout)


    def _close_gate_popover(self):
        if self._popover_timeout_id is not None:
            GLib.source_remove(self._popover_timeout_id)
            self._popover_timeout_id = None

        popover = self._popover
        self._popover = None

        if popover is not None:
            popover.popdown()
            popover.destroy()

        if self._click_shield is not None:
            if self._click_shield_overlay is not None:
                self._click_shield_overlay.set_overlay_pass_through(self._click_shield, True)
            self._click_shield.hide()


    def _on_gate_action(self, button, gate, action):
        self._close_gate_popover()
        logging.info("PAUL: %s gate %s", action, gate)


    def _on_popover_timeout(self):
        self._close_gate_popover()
        return False


    # ---------------------------------------------------------------------------
    # Drawing helpers
    # ---------------------------------------------------------------------------

    def _draw_oval(self, cr, cx, cy, w, h, fill_rgb, stroke_rgb=None, stroke_width=1.0):
        cr.save()
        cr.translate(cx, cy)
        cr.scale(w / 2, h / 2)
        cr.arc(0, 0, 1, 0, math.tau)
        cr.restore()

        cr.set_source_rgb(*fill_rgb)
        cr.fill_preserve()

        if stroke_rgb is not None:
            cr.set_line_width(stroke_width)
            cr.set_source_rgb(*stroke_rgb)
            cr.stroke()
        else:
            cr.new_path()


    def _draw_rounded_rect(self, cr, x, y, w, h, r, fill_rgb=None, stroke_rgb=None, stroke_width=1.0):
        cr.new_sub_path()
        cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
        cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
        cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
        cr.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
        cr.close_path()

        if fill_rgb is not None:
            if isinstance(fill_rgb, cairo.Pattern):
                cr.set_source(fill_rgb)
            elif len(fill_rgb) == 4:
                cr.set_source_rgba(*fill_rgb)
            else:
                cr.set_source_rgb(*fill_rgb)

            if stroke_rgb is not None:
                cr.fill_preserve()
            else:
                cr.fill()

        if stroke_rgb is not None:
            cr.set_line_width(stroke_width)

            if isinstance(stroke_rgb, cairo.Pattern):
                cr.set_source(stroke_rgb)
            elif len(stroke_rgb) == 4:
                cr.set_source_rgba(*stroke_rgb)
            else:
                cr.set_source_rgb(*stroke_rgb)

            cr.stroke()


    def _draw_tray(self, cr, x, y, w, h):
        tray_grad = cairo.LinearGradient(0, y, 0, y + h)
        tray_grad.add_color_stop_rgb(0.0, 0.34, 0.35, 0.36)  # mid grey top
        tray_grad.add_color_stop_rgb(1.0, 0.06, 0.07, 0.08)  # very dark bottom

        self._draw_rounded_rect(
            cr, x, y, w, h, 7,
            fill_rgb=tray_grad,
            stroke_rgb=(0.18, 0.19, 0.20),
            stroke_width=1.0,
        )

        # Bright top highlight / lip
        cr.save()
        cr.set_source_rgba(1, 1, 1, 0.32)
        cr.set_line_width(1.0)
        cr.move_to(x + 7, y + 1.5)
        cr.line_to(x + w - 7, y + 1.5)
        cr.stroke()
        cr.restore()

        # Soft darker line just under the lip
        cr.save()
        cr.set_source_rgba(0, 0, 0, 0.30)
        cr.set_line_width(1.0)
        cr.move_to(x + 7, y + 3.0)
        cr.line_to(x + w - 7, y + 3.0)
        cr.stroke()
        cr.restore()


    def _parse_color(self, color):
        rgba = Gdk.RGBA()
        if color and rgba.parse(color):
            return rgba.red, rgba.green, rgba.blue
        return 0.45, 0.45, 0.45
