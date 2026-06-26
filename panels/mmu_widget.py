import math
import cairo
from gi.repository import Gtk, Gdk

GATE_EMPTY = 0
GATE_AVAILABLE = 1
GATE_AVAILABLE_FROM_BUFFER = 2
GATE_UNKNOWN = -1
TOOL_GATE_BYPASS = -99


class MmuSpoolTray(Gtk.DrawingArea):
    MAX_DISPLAY = 13

    def __init__(self, printer):
        super().__init__()
        self._printer = printer
        self._items = None
        self._spool_cache = {}

        self.set_size_request(360, 72)
        self.set_app_paintable(True)
        self.connect("draw", self._draw)

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
            "color": self.get_rgb_color(gate_color[g]) or "#777777",
            "empty": status == GATE_EMPTY,
            "selected": g == selected_gate,
        }

    def _bypass_item(self, selected_gate):
        return {
            "gate": TOOL_GATE_BYPASS,
            "color": "#202020",
            "empty": False,
            "selected": selected_gate == TOOL_GATE_BYPASS,
        }

    def _draw(self, widget, cr):
        alloc = self.get_allocation()
        width = alloc.width
        height = alloc.height

        # Transparent background.
#        cr.set_operator(cairo.OPERATOR_CLEAR)
#        cr.paint()
#        cr.set_operator(cairo.OPERATOR_OVER)

        if self._items is None:
            self._items = self._build_items()

        groups = self._items
        total_spools = sum(len(g) for g in groups)
        if total_spools == 0:
            return False

        margin = 6
        group_gap = 12
        available_w = width - margin * 2 - group_gap * (len(groups) - 1)

        slot_w = available_w / max(total_spools, 1)

        # Deliberately wider than the slot so adjacent spools overlap.
        spool_h = height * 0.86
        spool_w = min(slot_w * 1.75, spool_h * 0.80)

        spool_cy = height * 0.42

        # Tray anchored to spool position.
        # Larger value = tray starts lower = covers less of the spool.
        tray_top = spool_cy + spool_h * 0.24
        tray_h = height - tray_top - 2

        x = margin

        tray_rects = []

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

                x += slot_w

            tray_rects.append((group_start - 2, tray_top, group_w + 4, tray_h))
            x += group_gap

        # Draw trays in foreground so they cover the lower part of the spools.
        for rect in tray_rects:
            self._draw_tray(cr, *rect)

        return False

    def _draw_spool(self, cr, cx, cy, w, h, color, empty=False, selected=False):
        key = (round(w), round(h), color, empty)
        surface = self._spool_cache.get(key)

        if surface is None:
            surface = cairo.ImageSurface(
                cairo.FORMAT_ARGB32,
                int(w + 14),
                int(h + 14),
            )
            c = cairo.Context(surface)
            c.translate(7, 7)
            self._render_spool(c, w, h, color, empty)
            self._spool_cache[key] = surface

            if len(self._spool_cache) > 64:
                self._spool_cache.clear()

# PAUL for now don't show selected
#        if selected:
#            cr.save()
#            cr.set_source_rgba(0.45, 1.0, 0.15, 0.35)
#            cr.arc(cx, cy, h * 0.55, 0, math.tau)
#            cr.fill()
#            cr.restore()

        cr.set_source_surface(surface, cx - w / 2 - 7, cy - h / 2 - 7)
        cr.paint()

    def _render_spool(self, cr, w, h, color, empty):
        fr, fg, fb = self._parse_color(color)

        # Cardboard colors
        cardboard = (0.70, 0.52, 0.30)
        cardboard_core = (0.60, 0.45, 0.26)
        cardboard_dark = (0.38, 0.25, 0.12)
        cardboard_edge = (0.20, 0.13, 0.06)

        left_x = w * 0.30
        right_x = w * 0.72

        outer_w = w * 0.30
        outer_h = h * 0.88

        # Filament oval on the right face
        inner_w = outer_w * 0.46
        inner_h = outer_h * 0.48

        # Tube / center hole dimensions
        tube_w = outer_w * 0.34
        tube_h = outer_h * 0.38

        body_x = left_x
        body_w = right_x - left_x

        # Core rectangle should match the black hole height
        core_y = h / 2 - tube_h / 2
        core_h = tube_h

        # Filament bulk, only drawn when not empty
        filament_y = h * 0.31
        filament_h = h * 0.38

        # 1. Right cardboard oval
        self._draw_oval(cr, right_x, h / 2, outer_w, outer_h, cardboard, cardboard_edge)

        # 2. Right cardboard tube end
        self._draw_oval(cr, right_x, h / 2, tube_w, tube_h, cardboard_core, cardboard_edge)

        # 3. Core rectangle
        cr.set_source_rgb(*cardboard_core)
        cr.rectangle(body_x, core_y, body_w, core_h)
        cr.fill()

        if not empty:
            # 4. Filament oval on right face
            self._draw_oval(cr, right_x, h / 2, inner_w, inner_h, (fr, fg, fb), cardboard_dark)

            # 5. Filament bulk
            cr.set_source_rgb(fr, fg, fb)
            cr.rectangle(body_x, filament_y, body_w, filament_h)
            cr.fill()

        # 6. Left cardboard oval
        self._draw_oval(cr, left_x, h / 2, outer_w, outer_h, cardboard, cardboard_edge)

        # 7. Left black hole
        self._draw_oval(cr, left_x, h / 2, tube_w, tube_h, (0.03, 0.025, 0.02), cardboard_edge)

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

#        # Filament ribs.
#        cr.set_line_width(1.0)
#        cr.set_source_rgba(0, 0, 0, 0.42)
#        for i in range(7):
#            px = body_x + body_w * (i + 1) / 8
#            cr.move_to(px, body_y + 1)
#            cr.line_to(px, body_y + body_h - 1)
#            cr.stroke()


# PAUL not currently used...
    def _draw_flange(self, cr, cx, cy, w, h, back=False):
        # Cardboard/kraft spool flange.
        grad = cairo.LinearGradient(cx - w / 2, cy, cx + w / 2, cy)
        grad.add_color_stop_rgb(0.00, 0.44, 0.34, 0.21)  # darker left edge
        grad.add_color_stop_rgb(0.45, 0.78, 0.68, 0.48)  # cardboard highlight
        grad.add_color_stop_rgb(1.00, 0.55, 0.43, 0.27)  # shaded right edge

        cr.save()
        cr.translate(cx, cy)
        cr.scale(w / 2, h / 2)
        cr.arc(0, 0, 1, 0, math.tau)
        cr.restore()

        cr.set_source(grad)
        cr.fill_preserve()

        # Outer cardboard edge.
        cr.set_line_width(1.1)
        cr.set_source_rgb(0.32, 0.24, 0.14)
        cr.stroke()

        # Subtle inner ring.
        cr.save()
        cr.translate(cx, cy)
        cr.scale(w * 0.32, h * 0.36)
        cr.arc(0, 0, 1, 0, math.tau)
        cr.restore()

        cr.set_line_width(0.8)
        cr.set_source_rgba(0.30, 0.22, 0.12, 0.55)
        cr.stroke()

        # Center hole, only on the visible/front flange.
        if not back:
            cr.save()
            cr.translate(cx, cy)
            cr.scale(w * 0.19, h * 0.24)
            cr.arc(0, 0, 1, 0, math.tau)
            cr.restore()

            cr.set_source_rgb(0.12, 0.085, 0.045)
            cr.fill()

#    def _draw_flange(self, cr, cx, cy, w, h, back=False):
#        grad = cairo.LinearGradient(cx - w / 2, cy, cx + w / 2, cy)
#        grad.add_color_stop_rgb(0.0, 0.06, 0.06, 0.06)
#        grad.add_color_stop_rgb(0.5, 0.34, 0.34, 0.34)
#        grad.add_color_stop_rgb(1.0, 0.10, 0.10, 0.10)
#
#        cr.save()
#        cr.translate(cx, cy)
#        cr.scale(w / 2, h / 2)
#        cr.arc(0, 0, 1, 0, math.tau)
#        cr.restore()
#
#        cr.set_source(grad)
#        cr.fill_preserve()
#
#        cr.set_line_width(1.1)
#        cr.set_source_rgb(0.58, 0.58, 0.58)
#        cr.stroke()
#
#        if not back:
#            cr.save()
#            cr.translate(cx, cy)
#            cr.scale(w * 0.19, h * 0.24)
#            cr.arc(0, 0, 1, 0, math.tau)
#            cr.restore()
#
#            cr.set_source_rgb(0.015, 0.015, 0.015)
#            cr.fill()

    def _draw_tray(self, cr, x, y, w, h):
#        # Foreground container: translucent and intentionally drawn over spools.
#        self._rounded_rect(cr, x, y, w, h, 7)
#
#        grad = cairo.LinearGradient(0, y, 0, y + h)
#        grad.add_color_stop_rgba(0.0, 0.55, 0.60, 0.62, 0.30)
#        grad.add_color_stop_rgba(1.0, 0.05, 0.07, 0.08, 0.62)
#
#        cr.set_source(grad)
#        cr.fill_preserve()
#
#        cr.set_line_width(1.0)
#        cr.set_source_rgba(0.80, 0.85, 0.88, 0.45)
#        cr.stroke()
        self._rounded_rect(cr, x, y, w, h, 7)

        cr.set_source_rgb(0.16, 0.17, 0.18)  # solid dark grey
        cr.fill_preserve()

        cr.set_line_width(1.0)
        cr.set_source_rgb(0.34, 0.35, 0.36)
        cr.stroke()

        # Top lip line.
        cr.set_source_rgba(1, 1, 1, 0.28)
        cr.set_line_width(1.0)
        cr.move_to(x + 5, y + 1)
        cr.line_to(x + w - 5, y + 1)
        cr.stroke()

    def _rounded_rect(self, cr, x, y, w, h, r):
        cr.new_sub_path()
        cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
        cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
        cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
        cr.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
        cr.close_path()

    def _parse_color(self, color):
        rgba = Gdk.RGBA()
        if color and rgba.parse(color):
            return rgba.red, rgba.green, rgba.blue
        return 0.45, 0.45, 0.45

#class MmuSpoolView(Gtk.DrawingArea):
#    MAX_DISPLAY = 13
#
#    def __init__(self, printer):
#        super().__init__()
#        self._printer = printer
#        self._state = None
#        self._spool_cache = {}
#        self.set_size_request(360, 105)
#
#        self.connect("draw", self._draw)
#
#    def refresh(self, show_gate=None):
#        self._state = self._build_state(show_gate)
#        self.queue_draw()
#
#    def _build_state(self, show_gate=None):
#        mmu = self._printer.get_stat("mmu")
#        gate_status = mmu["gate_status"]
#        gate_color = mmu["gate_color"]
#        ttg_map = mmu["ttg_map"]
#        selected = mmu["gate"]
#
#        unit_selected = mmu.get("unit")
#        gate_indices = []
#
#        if unit_selected is not None:
#            mmu_machine = self._printer.get_stat("mmu_machine")
#            bypass_found = False
#
#            for unit_index in range(mmu_machine["num_units"]):
#                if gate_indices:
#                    gate_indices.append(None)
#
#                unit = mmu_machine[f"unit_{unit_index}"]
#                first = unit["first_gate"]
#                count = unit["num_gates"]
#                gate_indices.extend(range(first, first + count))
#
#                if unit.get("has_bypass", False):
#                    gate_indices.append(TOOL_GATE_BYPASS)
#                    bypass_found = True
#
#            if not bypass_found:
#                gate_indices.extend([None, TOOL_GATE_BYPASS])
#        else:
#            gate_indices = list(range(len(gate_status)))
#
#        if show_gate is None:
#            show_gate = selected
#
#        if len(gate_indices) > self.MAX_DISPLAY:
#            try:
#                selected_idx = gate_indices.index(show_gate)
#                offset = max(0, selected_idx - self.MAX_DISPLAY // 2)
#                offset = min(offset, len(gate_indices) - self.MAX_DISPLAY)
#            except ValueError:
#                offset = 0
#            gate_indices = gate_indices[offset:offset + self.MAX_DISPLAY]
#
#        items = []
#        for g in gate_indices:
#            if g is None:
#                items.append({"kind": "sep"})
#                continue
#
#            if g == TOOL_GATE_BYPASS:
#                items.append({
#                    "kind": "bypass",
#                    "gate": g,
#                    "label": "Byp",
#                    "tool": "-",
#                    "status": None,
#                    "color": "#222222",
#                    "selected": selected == g,
#                })
#                continue
#
#            tools = [f"T{t}" for t, gate in enumerate(ttg_map) if gate == g]
#            status = gate_status[g]
#            color = self.get_rgb_color(gate_color[g]) or "#777777"
#
#            items.append({
#                "kind": "gate",
#                "gate": g,
#                "label": f"#{g}",
#                "tool": "+".join(tools) if tools else "-",
#                "status": status,
#                "color": color,
#                "selected": selected == g,
#            })
#
#        return items
#
#    def _draw(self, widget, cr):
#        alloc = self.get_allocation()
#        w, h = alloc.width, alloc.height
#
#        if self._state is None:
#            self._state = self._build_state()
#
#        cr.set_source_rgb(0.06, 0.07, 0.08)
#        cr.paint()
#
#        items = self._state
#        visible_slots = sum(1 for x in items if x["kind"] != "sep")
#        sep_count = sum(1 for x in items if x["kind"] == "sep")
#
#        margin_x = 8
#        sep_w = 8
#        slot_w = max(28, (w - margin_x * 2 - sep_count * sep_w) / max(1, visible_slots))
#
#        spool_w = min(44, slot_w * 1.25)
#        spool_h = min(58, h * 0.55)
#
#        x = margin_x
#        cy = 42
#
#        for item in items:
#            if item["kind"] == "sep":
#                self._draw_separator(cr, x + sep_w / 2, 8, h - 10)
#                x += sep_w
#                continue
#
#            cx = x + slot_w / 2
#
#            self._draw_text(cr, item["label"], cx, 13, 11, bold=True)
#
#            is_empty = item["status"] == GATE_EMPTY
#            is_unknown = item["status"] not in (
#                None,
#                GATE_EMPTY,
#                GATE_AVAILABLE,
#                GATE_AVAILABLE_FROM_BUFFER,
#            )
#
#            self._draw_spool(
#                cr,
#                cx,
#                cy,
#                spool_w,
#                spool_h,
#                item["color"],
#                empty=is_empty,
#                selected=item["selected"],
#                unknown=is_unknown,
#            )
#
#            self._draw_avail_dot(cr, cx, 75, item)
#            self._draw_text(cr, item["tool"], cx, 96, 10)
#
#            x += slot_w
#
#        return False
#
#    def _draw_spool(self, cr, cx, cy, w, h, color, empty=False, selected=False, unknown=False):
#        key = (round(w), round(h), color, empty, unknown)
#        surf = self._spool_cache.get(key)
#
#        if surf is None:
#            surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, int(w + 14), int(h + 14))
#            c = cairo.Context(surf)
#            c.translate(7, 7)
#            self._render_spool_surface(c, w, h, color, empty, unknown)
#            self._spool_cache[key] = surf
#
#            if len(self._spool_cache) > 64:
#                self._spool_cache.clear()
#
#        if selected:
#            cr.save()
#            cr.set_source_rgba(0.45, 1.0, 0.15, 0.35)
#            cr.arc(cx, cy, max(w, h) * 0.58, 0, math.tau)
#            cr.fill()
#            cr.restore()
#
#        cr.set_source_surface(surf, cx - w / 2 - 7, cy - h / 2 - 7)
#        cr.paint()
#
#        if selected:
#            cr.save()
#            cr.set_line_width(2.0)
#            cr.set_source_rgb(0.55, 1.0, 0.25)
#            cr.arc(cx, cy, max(w, h) * 0.55, 0, math.tau)
#            cr.stroke()
#            cr.restore()
#
#    def _render_spool_surface(self, cr, w, h, color, empty, unknown):
#        r, g, b = self._parse_color(color)
#
#        left_x = w * 0.26
#        right_x = w * 0.68
#        body_x = w * 0.18
#        body_w = w * 0.54
#
#        # filament body
#        if empty:
#            fr, fg, fb = 0.10, 0.10, 0.10
#        elif unknown:
#            fr, fg, fb = 0.45, 0.45, 0.45
#        else:
#            fr, fg, fb = r, g, b
#
#        grad = cairo.LinearGradient(0, 0, 0, h)
#        grad.add_color_stop_rgb(0.0, min(fr + 0.25, 1), min(fg + 0.25, 1), min(fb + 0.25, 1))
#        grad.add_color_stop_rgb(0.5, fr, fg, fb)
#        grad.add_color_stop_rgb(1.0, max(fr - 0.25, 0), max(fg - 0.25, 0), max(fb - 0.25, 0))
#
#        cr.set_source(grad)
#        self._rounded_rect(cr, body_x, h * 0.24, body_w, h * 0.52, 4)
#        cr.fill()
#
#        # filament ribs
#        cr.set_line_width(1)
#        cr.set_source_rgba(0, 0, 0, 0.35)
#        ribs = 7
#        for i in range(ribs):
#            px = body_x + body_w * (i + 1) / (ribs + 1)
#            cr.move_to(px, h * 0.25)
#            cr.line_to(px, h * 0.75)
#            cr.stroke()
#
#        # flanges
#        self._draw_flange(cr, left_x, h / 2, w * 0.24, h * 0.82)
#        self._draw_flange(cr, right_x, h / 2, w * 0.24, h * 0.82)
#
#        if unknown:
#            cr.set_source_rgb(1, 0.15, 0.10)
#            cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
#            cr.set_font_size(h * 0.45)
#            cr.move_to(w * 0.44, h * 0.62)
#            cr.show_text("?")
#
#    def _draw_flange(self, cr, cx, cy, w, h):
#        grad = cairo.LinearGradient(cx - w / 2, cy, cx + w / 2, cy)
#        grad.add_color_stop_rgb(0, 0.12, 0.12, 0.12)
#        grad.add_color_stop_rgb(0.5, 0.35, 0.35, 0.35)
#        grad.add_color_stop_rgb(1, 0.08, 0.08, 0.08)
#
#        cr.save()
#        cr.translate(cx, cy)
#        cr.scale(w / 2, h / 2)
#        cr.arc(0, 0, 1, 0, math.tau)
#        cr.restore()
#        cr.set_source(grad)
#        cr.fill_preserve()
#        cr.set_source_rgb(0.55, 0.55, 0.55)
#        cr.set_line_width(1)
#        cr.stroke()
#
#        cr.save()
#        cr.translate(cx, cy)
#        cr.scale(w * 0.18, h * 0.23)
#        cr.arc(0, 0, 1, 0, math.tau)
#        cr.restore()
#        cr.set_source_rgb(0.03, 0.03, 0.03)
#        cr.fill()
#
#    def _draw_avail_dot(self, cr, cx, cy, item):
#        status = item["status"]
#
#        if status is None:
#            self._draw_text(cr, "-", cx, cy + 3, 10)
#            return
#
#        if status == GATE_EMPTY:
#            cr.set_source_rgba(0.75, 0.75, 0.75, 0.8)
#            cr.set_line_width(1.6)
#            cr.arc(cx, cy, 5, 0, math.tau)
#            cr.stroke()
#            return
#
#        if status in (GATE_AVAILABLE, GATE_AVAILABLE_FROM_BUFFER):
#            r, g, b = self._parse_color(item["color"])
#            cr.set_source_rgb(r, g, b)
#            cr.arc(cx, cy, 5, 0, math.tau)
#            cr.fill()
#            return
#
#        cr.set_source_rgb(1, 0.15, 0.1)
#        self._draw_text(cr, "?", cx, cy + 4, 13, bold=True)
#
#    def _draw_separator(self, cr, x, y1, y2):
#        cr.set_source_rgba(0.7, 0.7, 0.7, 0.35)
#        cr.set_line_width(1)
#        cr.move_to(x, y1)
#        cr.line_to(x, y2)
#        cr.stroke()
#
#    def _draw_text(self, cr, text, cx, y, size, bold=False):
#        cr.select_font_face(
#            "Sans",
#            cairo.FONT_SLANT_NORMAL,
#            cairo.FONT_WEIGHT_BOLD if bold else cairo.FONT_WEIGHT_NORMAL,
#        )
#        cr.set_font_size(size)
#        xb, yb, tw, th, xa, ya = cr.text_extents(text)
#        cr.set_source_rgb(0.78, 0.78, 0.78)
#        cr.move_to(cx - tw / 2 - xb, y)
#        cr.show_text(text)
#
#    def _rounded_rect(self, cr, x, y, w, h, r):
#        cr.new_sub_path()
#        cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
#        cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
#        cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
#        cr.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
#        cr.close_path()
#
#    def _parse_color(self, color):
#        try:
#            rgba = Gdk.RGBA()
#            if rgba.parse(color):
#                return rgba.red, rgba.green, rgba.blue
#        except Exception:
#            pass
#        return 0.45, 0.45, 0.45
#


    def get_rgb_color(self, gate_color):
        if gate_color and len(gate_color) == 8:
            try:
                int(gate_color, 16)
                gate_color = gate_color[:6]
            except ValueError:
                pass
        color = Gdk.RGBA()
        if not Gdk.RGBA.parse(color, gate_color.lower() if gate_color else ""):
            if not Gdk.RGBA.parse(color, '#' + gate_color if gate_color else ""):
                return ""
        rgb_color = "#{:02x}{:02x}{:02x}".format(int(color.red * 255), int(color.green * 255), int(color.blue * 255))
        return rgb_color
