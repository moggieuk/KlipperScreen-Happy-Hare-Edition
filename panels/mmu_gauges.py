# -*- coding: utf-8 -*-
# Happy Hare MMU Software
#
# Copyright (C) 2022-2026  moggieuk#6538 (discord)
#                          moggieuk@hotmail.com
#
# Implements Encoder and FlowGuard custom gauges
#
#
# (\_/)
# ( *,*)
# (")_(") Happy Hare Ready
#
# This file may be distributed under the terms of the GNU GPLv3 license.
# Happy Hare MMU Software
#
import logging, gi, math

gi.require_version("Gtk", "3.0")

from gi.repository import Gtk
import cairo


# -------------------------------------------------------------------------------------------
# ENCODER DIAL GUAGE
# -------------------------------------------------------------------------------------------

class EncoderDialGauge(Gtk.DrawingArea):
    def __init__(self):
        super().__init__()

        self.value = 30.0
        self.max_value = 30.0
        self.desired_headroom = 10.0
        self.min_headroom = 30.0
        self.flowrate = None
        self.enabled = False

        # Colors
        self.green = (0.25, 0.60, 0.32)
        self.amber = (0.78, 0.55, 0.16)
        self.red   = (0.70, 0.20, 0.20)
        self.white = (0.95, 0.95, 0.95)
        self.grey  = (0.45, 0.45, 0.45)

        # Geometry / styling
        self.arc_width = 10
        self.needle_width = 4
        self.marker_width = 4
        self.hub_radius = 6
        self.marker_inner_offset = 7
        self.marker_outer_offset = 12
        self.needle_inset = 12

        self.arc_start_deg = -20.0
        self.arc_sweep_deg = -140.0

        self.set_size_request(50, 30)
        self.set_hexpand(True)
        self.set_vexpand(True)

        self.connect("draw", self._draw)

    def update(self, data):
        new_max = max(1.0, float(data.get("detection_length", 10.0)))
        new_min = float(data.get("min_headroom", 0.0))
        new_desired = float(data.get("desired_headroom", 5.0))
        new_value = float(data.get("headroom", 0.0))
        new_enabled = bool(data.get("enabled", False))
        new_flowrate = float(data.get("flow_rate", 0.0))

        changed = (
            abs(self.max_value - new_max) > 0.01 or
            abs(self.min_headroom - new_min) > 0.01 or
            abs(self.desired_headroom - new_desired) > 0.01 or
            abs(self.value - new_value) > 0.05 or
            self.enabled != new_enabled or
            self.flowrate != new_flowrate
        )

        if not changed:
            return

        self.max_value = new_max
        self.min_headroom = new_min
        self.desired_headroom = new_desired
        self.value = new_value
        self.enabled = new_enabled
        self.flowrate = new_flowrate

        self.queue_draw()

    def _clamp(self, value, low, high):
        return max(low, min(high, value))

    def _angle(self, value):
        # left = max_value, right = 0, across the top
        value = self._clamp(value, 0.0, self.max_value)
        fraction = value / self.max_value
        degrees = self.arc_start_deg + self.arc_sweep_deg * fraction
        return math.radians(degrees)

    def _color_for_headroom(self, value):
        warning = self.desired_headroom
        danger = self.desired_headroom / 2.0

        if value <= danger:
            return self.red
        if value <= warning:
            return self.amber
        return self.green

    def _point_on_arc(self, cx, cy, radius, value):
        a = self._angle(value)
        return (
            cx + radius * math.cos(a),
            cy + radius * math.sin(a),
        )

    def _draw_arc(self, cr, cx, cy, r, start, end, color):
        cr.set_source_rgb(*color)
        cr.arc(cx, cy, r, self._angle(start), self._angle(end))
        cr.stroke()

    def _draw_marker(self, cr, cx, cy, r, value):
        x1, y1 = self._point_on_arc(cx, cy, r + self.marker_inner_offset, value)
        x2, y2 = self._point_on_arc(cx, cy, r + self.marker_outer_offset, value)

        cr.set_source_rgb(*self._color_for_headroom(value))
        cr.set_line_width(self.marker_width)
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        cr.move_to(x1, y1)
        cr.line_to(x2, y2)
        cr.stroke()

    def _draw_text_centered(self, cr, text, x, y):
        ext = cr.text_extents(text)
        cr.move_to(x - ext.width / 2, y)
        cr.show_text(text)

    def _draw(self, widget, cr):
        w = self.get_allocated_width()
        h = self.get_allocated_height()

        # Shape of arc (circle center and radius)
        cx = w * 0.5
        cy = h * 0.62 # 62% down
        r = min(w * 0.40, h * 0.50)

        warning = self.desired_headroom
        danger = self.desired_headroom / 2.0

        cr.set_line_width(self.arc_width)
        cr.set_line_cap(cairo.LINE_CAP_ROUND)

        # Zones:
        # max_value -> desired_headroom       = green
        # desired_headroom -> desired / 2     = amber
        # desired / 2 -> 0                    = red
        self._draw_arc(cr, cx, cy, r, self.max_value, warning, self.green)
        self._draw_arc(cr, cx, cy, r, warning, danger, self.amber)
        self._draw_arc(cr, cx, cy, r, danger, 0.0, self.red)

        # Endpoint labels
        cr.set_source_rgb(*self.white)
        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        cr.set_font_size(14)

        x, y = self._point_on_arc(cx, cy, r, self.max_value)
        self._draw_text_centered(cr, f"{int(self.max_value)}", x, y + 24)

        x, y = self._point_on_arc(cx, cy, r, 0.0)
        self._draw_text_centered(cr, "0", x, y + 24)

        # Min headroom marker
        self._draw_marker(cr, cx, cy, r, self.min_headroom)

        # Needle
        a = self._angle(self.value)
        nx = cx + (r - self.needle_inset) * math.cos(a)
        ny = cy + (r - self.needle_inset) * math.sin(a)

        cr.set_source_rgb(*self._color_for_headroom(self.value))
        cr.set_line_width(self.needle_width)
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        cr.move_to(cx, cy)
        cr.line_to(nx, ny)
        cr.stroke()

        cr.arc(cx, cy, self.hub_radius, 0, 2 * math.pi)
        cr.fill()

        # Main value
        cr.set_source_rgb(*self.white)
        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(16)

        value_y = h * 0.40
        self._draw_text_centered(cr, f"{self.value:.1f}", cx, value_y)

        # Unit
        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        cr.set_font_size(12)
        self._draw_text_centered(cr, "mm", cx, value_y + 12)

        # Gauge label
        cr.set_font_size(14)
        if not self.enabled:
            cr.set_source_rgb(*self.grey)
            text = "Disabled"
        else:
            cr.set_source_rgb(*self.white)
            text = "Encoder"
        self._draw_text_centered(cr, text, cx, cy - cr.text_extents(text).y_bearing + 14)

        # Flowrate / Trigger
        if self.value <= 0:
            cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
            cr.set_source_rgb(*self.red)
            bottom_text = "CLOG / TANGLE"
        elif self.flowrate is not None:
            cr.set_source_rgb(*self.white)
            bottom_text = f"Flowrate: {int(self.flowrate)}%"
        else:
            cr.set_source_rgb(*self.grey)
            bottom_text = "Flowrate: --%"
        self._draw_text_centered(cr, bottom_text, cx, cy - cr.text_extents(bottom_text).y_bearing + 34)

        return False


# -------------------------------------------------------------------------------------------
# FLOWGUARD TANGLE / CLOG METER
# -------------------------------------------------------------------------------------------

class FlowGuardDialGauge(Gtk.DrawingArea):
    def __init__(self):
        super().__init__()

        self.level = 0.0
        self.max_clog = 0.0
        self.max_tangle = 0.0
        self.active = False
        self.enabled = False
        self.trigger = ""
        self.flowrate = None

        # Colors
        self.green = (0.25, 0.60, 0.32)
        self.amber = (0.78, 0.55, 0.16)
        self.red   = (0.70, 0.20, 0.20)
        self.white = (0.95, 0.95, 0.95)
        self.grey  = (0.45, 0.45, 0.45)

        # Geometry / styling
        self.arc_width = 10
        self.needle_width = 4
        self.marker_width = 4
        self.hub_radius = 6
        self.arc_start_deg = -160.0
        self.arc_sweep_deg = 140.0

        # Thresholds
        self.amber_threshold = 0.5
        self.red_threshold = 0.9

        self.set_size_request(50, 30)
        self.set_hexpand(True)
        self.set_vexpand(True)

        self.connect("draw", self._draw)

    def update(self, flowguard_status, flowrate=None):
        new_level = float(flowguard_status.get("level", 0.0))
        new_max_clog = float(flowguard_status.get("max_clog", 0.0))
        new_max_tangle = float(flowguard_status.get("max_tangle", 0.0))
        new_active = bool(flowguard_status.get("active", False))
        new_enabled = bool(flowguard_status.get("enabled", False))
        new_trigger = flowguard_status.get("trigger", "")
        new_flowrate = None if flowrate is None else float(flowrate)

        changed = (
            abs(self.level - new_level) > 0.01 or
            abs(self.max_clog - new_max_clog) > 0.01 or
            abs(self.max_tangle - new_max_tangle) > 0.01 or
            self.active != new_active or
            self.enabled != new_enabled or
            self.trigger != new_trigger or
            self.flowrate != new_flowrate
        )

        if not changed:
            return

        self.level = new_level
        self.max_clog = new_max_clog
        self.max_tangle = new_max_tangle
        self.active = new_active
        self.enabled = new_enabled
        self.trigger = new_trigger
        self.flowrate = new_flowrate

        self.queue_draw()

    def _clamp(self, value):
        return max(-1.0, min(1.0, value))

    def _angle(self, value):
        fraction = (self._clamp(value) + 1.0) / 2.0
        degrees = self.arc_start_deg + self.arc_sweep_deg * fraction
        return math.radians(degrees)

    def _color_for_value(self, value):
        abs_value = abs(value)

        if abs_value > self.red_threshold:
            return self.red
        if abs_value > self.amber_threshold:
            return self.amber
        return self.green

    def _point_on_arc(self, cx, cy, radius, value):
        a = self._angle(value)
        return (
            cx + radius * math.cos(a),
            cy + radius * math.sin(a),
        )

    def _draw_arc(self, cr, cx, cy, r, start, end, color):
        cr.set_source_rgb(*color)
        cr.arc(cx, cy, r, self._angle(start), self._angle(end))
        cr.stroke()

    def _draw_marker(self, cr, cx, cy, r, value):
        x1, y1 = self._point_on_arc(cx, cy, r + 7, value)
        x2, y2 = self._point_on_arc(cx, cy, r + 12, value)

        cr.set_source_rgb(*self._color_for_value(value))
        cr.set_line_width(self.marker_width)
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        cr.move_to(x1, y1)
        cr.line_to(x2, y2)
        cr.stroke()

    def _draw_text_centered(self, cr, text, x, y):
        ext = cr.text_extents(text)
        cr.move_to(x - ext.width / 2, y)
        cr.show_text(text)

    def _draw(self, widget, cr):
        w = self.get_allocated_width()
        h = self.get_allocated_height()

        cx = w * 0.5
        cy = h * 0.62
        r = min(w * 0.40, h * 0.50)

        cr.set_line_width(self.arc_width)
        cr.set_line_cap(cairo.LINE_CAP_ROUND)

        self._draw_arc(cr, cx, cy, r, -0.5,  0.5, self.green)
        self._draw_arc(cr, cx, cy, r, -0.9, -0.5, self.amber)
        self._draw_arc(cr, cx, cy, r, -1.0, -0.9, self.red)
        self._draw_arc(cr, cx, cy, r,  0.5,  0.9, self.amber)
        self._draw_arc(cr, cx, cy, r,  0.9,  1.0, self.red)

        cr.set_source_rgb(*self.white)
        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        cr.set_font_size(14)

        x, y = self._point_on_arc(cx, cy, r, -1.0)
        self._draw_text_centered(cr, "Tangle", x + 8, y + 24)

        x, y = self._point_on_arc(cx, cy, r, 1.0)
        self._draw_text_centered(cr, "Clog", x - 8, y + 24)

        self._draw_marker(cr, cx, cy, r, self.max_tangle)
        self._draw_marker(cr, cx, cy, r, self.max_clog)

        # Needle
        a = self._angle(self.level)
        nx = cx + (r - 12) * math.cos(a)
        ny = cy + (r - 12) * math.sin(a)

        cr.set_source_rgb(*self._color_for_value(self.level))
        cr.set_line_width(self.needle_width)
        cr.move_to(cx, cy)
        cr.line_to(nx, ny)
        cr.stroke()

        cr.arc(cx, cy, self.hub_radius, 0, 2 * math.pi)
        cr.fill()

        # Main value
        cr.set_source_rgb(*self.white)
        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(16)

        value_y = h * 0.40
        self._draw_text_centered(cr, f"{self.level:+.2f}", cx, value_y)

        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)

        if self.active:
            cr.set_font_size(12)
            self._draw_text_centered(cr, "Active", cx, value_y + 14)

        cr.set_font_size(14)
        if not self.enabled:
            cr.set_source_rgb(*self.grey)
            text = "Disabled"
        elif self.active:
            cr.set_source_rgb(*self.white)
            text = "Active"
        else:
            cr.set_source_rgb(*self.grey)
            text = "Inactive"
        self._draw_text_centered(cr, text, cx, cy - cr.text_extents(text).y_bearing + 14)

        # Flowrate / Trigger
        if self.trigger:
            cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
            cr.set_source_rgb(*self.red)
            bottom_text = f"{self.trigger.upper()}"
        elif self.flowrate is not None:
            cr.set_source_rgb(*self.white)
            bottom_text = f"Flowrate: {int(self.flowrate)}%"
        else:
            cr.set_source_rgb(*self.grey)
            bottom_text = "Flowrate: --%"
        self._draw_text_centered(cr, bottom_text, cx, cy - cr.text_extents(bottom_text).y_bearing + 34)

        return False
