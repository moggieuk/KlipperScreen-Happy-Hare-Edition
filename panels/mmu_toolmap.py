# -*- coding: utf-8 -*-
# Happy Hare MMU Software
# Display and editing of TTG map and endless spool groups
#
# Copyright (C) 2023-2026  moggieuk#6538 (discord)
#                          moggieuk@hotmail.com
#
import gi

gi.require_version("Gtk", "3.0")
gi.require_version("PangoCairo", "1.0")

from gi.repository import Gtk, Pango, PangoCairo

from ks_includes.screen_panel import ScreenPanel
from panels.mmu_mixin         import *


class Panel(ScreenPanel, MmuMixin):

    def __init__(self, screen, title):
        super().__init__(screen, title)

        mmu = self._printer.get_stat("mmu")
        self.num_gates = len(mmu['ttg_map'])
        self.ui_sel_tool = 0

        self.labels = {
            't_decrease': self._gtk.Button('decrease', None, 'color1', scale=self.bts * 1.2),
            'tool': Gtk.Label("T0"),
            't_increase': self._gtk.Button('increase', None, 'color2', scale=self.bts * 1.2),
            'g_decrease': self._gtk.Button('decrease', None, 'color1', scale=self.bts * 1.2),
            'gate': Gtk.Label("#0"),
            'g_increase': self._gtk.Button('increase', None, 'color2', scale=self.bts * 1.2),
            'save': self._gtk.Button('mmu_save', 'Save', 'color3'),
            'es_group': Gtk.Label("ES Group: A"),
            'reset': self._gtk.Button('refresh', 'Reset', scale=self.bts, position=Gtk.PositionType.LEFT, lines=1),
            'endless_spool': Gtk.CheckButton("EndlessSpool Enabled"),
        }

        l = self.labels
        l['t_decrease'].connect("clicked", self.select_tool_gate, 'tool', -1)
        l['t_increase'].connect("clicked", self.select_tool_gate, 'tool', 1)
        l['g_decrease'].connect("clicked", self.select_tool_gate, 'gate', -1)
        l['g_increase'].connect("clicked", self.select_tool_gate, 'gate', 1)
        l['save'].connect("clicked", self.select_reset_save, "save")
        l['reset'].connect("clicked", self.select_reset_save, "reset")
        l['endless_spool'].connect("notify::active", self.select_es_toggle)
        l['tool'].get_style_context().add_class("mmu_tool_text")
        l['gate'].get_style_context().add_class("mmu_gate_text")
        l['t_decrease'].set_vexpand(False)
        l['t_increase'].set_vexpand(False)
        l['g_decrease'].set_vexpand(False)
        l['g_increase'].set_vexpand(False)
        l['save'].set_vexpand(False)
        l['save'].set_hexpand(False)
        l['reset'].set_halign(Gtk.Align.CENTER)
        l['reset'].set_vexpand(False)
        l['reset'].get_style_context().add_class("mmu_es_gate")
        l['reset'].get_style_context().add_class("mmu_es_gate_reset")
        l['es_group'].set_xalign(0)
        l['es_group'].get_style_context().add_class("mmu_endless_spool_toggle")
        l['endless_spool'].get_style_context().add_class("mmu_endless_spool_toggle")

        self.ttg_map_widget = TtgMapWidget()
        self.ttg_map_widget.set_hexpand(True)
        self.ttg_map_widget.set_halign(Gtk.Align.FILL)
        self.ttg_map_widget.set_vexpand(True)
        self.ttg_map_widget.set_valign(Gtk.Align.FILL)

        es_flowbox = Gtk.FlowBox(orientation=Gtk.Orientation.HORIZONTAL)
        es_flowbox.set_selection_mode(Gtk.SelectionMode.NONE)
        es_flowbox.set_vexpand(False)
        es_flowbox.set_margin_bottom(8)
        for i in range(self.num_gates):
            g = l[f'es_gate{i}'] = self._gtk.Button(label=str(i))
            g.set_hexpand(False)
            g.connect("clicked", self.select_es_gate, int(i))
            g.get_style_context().add_class("mmu_es_gate")
            es_flowbox.add(g)

        inner = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        inner.set_margin_top(8)
        inner.pack_start(l['endless_spool'], False, False, 0)
        inner.pack_start(l['es_group'], False, False, 0)
        es_grp_box = Gtk.Box()
        es_grp_box.set_halign(Gtk.Align.CENTER)
        es_grp_box.pack_start(inner, False, False, 0)

        mapgrid = Gtk.Grid()
        mapgrid.set_column_homogeneous(True)
        mapgrid.set_vexpand(True)
        mapgrid.attach(l['t_decrease'],      0,  1,  3, 2)
        mapgrid.attach(l['tool'],            0,  3,  3, 1)
        mapgrid.attach(l['t_increase'],      0,  4,  3, 2)
        mapgrid.attach(self.ttg_map_widget,  3,  0, 10, 7)
        mapgrid.attach(l['g_decrease'],     13,  1,  3, 2)
        mapgrid.attach(l['gate'],           13,  3,  3, 1)
        mapgrid.attach(l['g_increase'],     13,  4,  3, 2)

        grid = Gtk.Grid()
        grid.set_column_homogeneous(False)

        # My screen fails touch requests if buttons a tight to the bottom (?)
        # so added a spacer as a temporary workaround
        bottom_pad = Gtk.Box()
        bottom_pad.set_size_request(-1, 15)

        grid.attach(mapgrid,                 0,  0, 16, 1)
        grid.attach(es_grp_box,              2,  1, 12, 1)
        grid.attach(l['reset'],             14,  1,  2, 1)
        grid.attach(es_flowbox,              0,  2, 14, 2)
        grid.attach(l['save'],              14,  2,  2, 2)
        grid.attach(bottom_pad,              0,  4, 16, 1)

        self.content.add(grid)


    def activate(self):
        # We need to keep track of just a little bit of UI state
        mmu = self._printer.get_stat("mmu")
        self.ui_ttg_map = list(mmu['ttg_map'])
        self.ui_endless_spool_groups = list(mmu['endless_spool_groups'])
        self.ui_es_enabled = mmu.get('endless_spool_enabled') or mmu.get('endless_spool')
        self.ui_sel_es_group = self.selected_group()

        self.update_all()


    def process_update(self, action, data):
        if action == "notify_status_update" and data is not None:
            if 'mmu' in data:
                e_data = data['mmu']
                if any(
                    key in e_data
                    for key in ('ttg_map', 'endless_spool_groups', 'endless_spool_enabled', 'endless_spool') # 'endless_spool' is legacy HHv3 variable
                ):
                    # Server side change requires us to completely re-sync
                    self.activate()


    def update_all(self):
        mmu = self._printer.get_stat("mmu")
        self.ui_ttg_map = list(mmu['ttg_map'])
        self.ui_endless_spool_groups = list(mmu['endless_spool_groups'])

        self.ui_sel_es_group = self.selected_group()

        self.ui_es_enabled = mmu.get('endless_spool_enabled') or mmu.get('endless_spool')

        self.labels['endless_spool'].set_active(bool(self.ui_es_enabled))
        self.update_map()
        self.update_es_group()


    def update_map(self):
        tool = self.ui_sel_tool
        gate = self.ui_ttg_map[tool]

        self.labels['tool'].set_label(f"T{tool}")
        self.labels['gate'].set_label(f"Gate #{gate}")

        self.ttg_map_widget.set_state(
            self.ui_ttg_map,
            self.ui_endless_spool_groups,
            selected_tool=tool,
            endless_spool_enabled=bool(self.ui_es_enabled)
        )


    def update_es_group(self):
        selected_gate = self.selected_gate()
        selected_group = self.selected_group()
        gates_in_group = set(self.get_gates_in_es_group(selected_group))

        self.ui_sel_es_group = selected_group

        for gate in range(self.num_gates):
            button = self.labels[f"es_gate{gate}"]
            ctx = button.get_style_context()

            if gate in gates_in_group:
                ctx.add_class("mmu_es_gate_selected")
            else:
                ctx.remove_class("mmu_es_gate_selected")

            # EndlessSpool disabled: no editing.
            # Selected gate: visible/highlighted, but cannot be removed from its group.
            button.set_sensitive(bool(self.ui_es_enabled) and gate != selected_gate)

        grp = self.convert_number_to_letter(selected_group)
        self.labels['es_group'].set_markup(f"<b>ES Group: {grp}</b>")
        self.labels['es_group'].set_sensitive(bool(self.ui_es_enabled))


    def select_tool_gate(self, widget, toolgate, param=0):
        if toolgate == "tool":
            self.ui_sel_tool = max(0, min(self.ui_sel_tool + param, self.num_gates - 1))
        else:
            gate = self.selected_gate()
            self.ui_ttg_map[self.ui_sel_tool] = max(0, min(gate + param, self.num_gates - 1))

        self.ui_sel_es_group = self.selected_group()

        self.update_map()
        self.update_es_group()


    def select_es_gate(self, widget, gate):
        if self.ui_ttg_map is None or self.ui_endless_spool_groups is None:
            self.update_all()

        if gate < 0 or gate >= self.num_gates:
            return

        selected_gate = self.selected_gate()
        selected_group = self.selected_group()

        if selected_group < 0:
            return

        # The selected gate defines the editable group and must always remain in it.
        if gate == selected_gate:
            return

        if self.ui_endless_spool_groups[gate] == selected_group:
            # Remove from this group by assigning a new singleton group.
            self.ui_endless_spool_groups[gate] = self.get_first_empty_group_number(
                self.ui_endless_spool_groups
            )
        else:
            # Add to selected gate's group.
            self.ui_endless_spool_groups[gate] = selected_group

        self.ui_sel_es_group = self.selected_group()
        self.update_map()
        self.update_es_group()


    def select_es_toggle(self, widget, param=0):
        if self.labels['endless_spool'].get_active():
            self.ui_es_enabled = 1
        else:
            self.ui_es_enabled = 0

        self.update_es_group()


    def selected_gate(self):
        if self.ui_ttg_map is None:
            return -1
        if 0 <= self.ui_sel_tool < self.num_gates:
            return self.ui_ttg_map[self.ui_sel_tool]
        return -1


    def selected_group(self):
        if self.ui_endless_spool_groups is None:
            return -1

        gate = self.selected_gate()
        if 0 <= gate < self.num_gates:
            return self.ui_endless_spool_groups[gate]

        return -1


    def get_first_empty_group_number(self, groups):
        used = set(groups)
        group = 0
        while group in used:
            group += 1
        return group


    def convert_number_to_letter(self, group):
        if group is None or group < 0:
            return "?"
        if group < 26:
            return chr(ord("A") + group)
        return str(group)


    def get_gates_in_es_group(self, es_group):
        return [
            gate for gate, group in enumerate(self.ui_endless_spool_groups)
            if group == es_group
        ]


    def select_reset_save(self, widget, action):
        label = Gtk.Label()
        label.set_hexpand(True)
        label.set_halign(Gtk.Align.CENTER)
        label.set_vexpand(True)
        label.set_valign(Gtk.Align.CENTER)
        label.set_line_wrap(True)
        label.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)

        if action == "reset":
            label.set_text("This will reset the TTG map and EndlessSpool groups\n\nto the default defined in your MMU configuration\n\nAre you sure you want to continue?")
        else:
            label.set_text("This will set the MMU TTG map and ALL EndlessSpool groups\n\nto the configuration defined on this panel\n\nAre you sure you want to continue?")

        grid = Gtk.Grid(row_homogeneous=True, column_homogeneous=True)
        grid.attach(label, 0, 0, 1, 1)
        buttons = [
            {"name": _("Apply"), "response": Gtk.ResponseType.APPLY},
            {"name": _("Cancel"), "response": Gtk.ResponseType.CANCEL}
        ]
        dialog = self._gtk.Dialog(self._screen, buttons, grid, self.reset_save_confirm, action)
        dialog.set_title(_("Confirm TTG/EndlessSpool Reset"))


    def reset_save_confirm(self, dialog, response_id, action):
        self._gtk.remove_dialog(dialog)
        if response_id == Gtk.ResponseType.APPLY:
            if action == "reset":
                self._screen._ws.api.gcode_script("MMU_TTG_MAP RESET=1 QUIET=1")
                self._screen._ws.api.gcode_script("MMU_ENDLESS_SPOOL RESET=1 QUIET=1")
            else:
                ttg_map=",".join(map(str,self.ui_ttg_map))
                groups=",".join(map(str,self.ui_endless_spool_groups))
                self._screen._ws.api.gcode_script(f"MMU_TTG_MAP MAP={ttg_map} QUIET=1")
                self._screen._ws.api.gcode_script(f"MMU_ENDLESS_SPOOL GROUPS={groups} QUIET=1 ENABLE={self.ui_es_enabled}")



# -------------------------------------------------------------------------------------------
# MMU TTG MAP WIDGET
# -------------------------------------------------------------------------------------------

class TtgMapWidget(Gtk.DrawingArea):
    """
    Compact horizontally-scaling TTG map widget.
    """

    MIN_ROW_HEIGHT = 18
    MAX_ROW_HEIGHT = 30
    TARGET_HEIGHT = 180

    TOP_PAD = 8
    BOTTOM_PAD = 14
    LEFT_PAD = 24
    RIGHT_PAD = 24

    TOOL_LABEL_GAP = 10
    TOOL_STUB = 20
    GATE_STUB = 20
    GATE_LABEL_GAP = 10

    GROUP_LABEL_GAP = 4
    GROUP_AFTER_GATE_LABEL_GAP = 18
    GROUP_BRACKET_WIDTH = 12
    GROUP_COLUMN_SPACING = 22
    GROUP_TAG_LENGTH = 8

    NORMAL_LINE_WIDTH = 2.0
    SELECTED_LINE_WIDTH = 4.5

    SELECTED_RGBA = (0.0, 0.85, 1.0, 1.0)

    def __init__(self):
        super().__init__()

        self.ttg_map = []
        self.es_groups = []
        self.selected_tool = -1
        self.selected_gate = -1
        self.endless_spool_enabled = True

        self.set_hexpand(True)
        self.set_halign(Gtk.Align.FILL)
        self.set_vexpand(False)

        self.connect("draw", self.on_draw)


    def set_state(self, ttg_map, es_groups, selected_tool=-1, endless_spool_enabled=True):
        self.ttg_map = list(ttg_map or [])
        self.es_groups = list(es_groups or [])
        self.selected_tool = selected_tool
        self.endless_spool_enabled = endless_spool_enabled

        if 0 <= selected_tool < len(self.ttg_map):
            self.selected_gate = self.ttg_map[selected_tool]
        else:
            self.selected_gate = -1

        self.queue_draw()


    def content_height(self):
        alloc = self.get_allocation()
        return max(1, alloc.height - self.TOP_PAD - self.BOTTOM_PAD)


    def calc_row_height(self):
        count = max(1, len(self.ttg_map))
        return self.content_height() / count


    def y_for(self, index):
        return self.TOP_PAD + index * self.calc_row_height() + self.calc_row_height() / 2.0


    def calc_height(self):
        count = max(1, len(self.ttg_map))
        return int(self.TOP_PAD + count * self.calc_row_height() + self.BOTTOM_PAD)


    def current_group(self):
        if 0 <= self.selected_gate < len(self.es_groups):
            return self.es_groups[self.selected_gate]
        return -1


    def grouped_gates(self):
        groups = {}
        for gate, group in enumerate(self.es_groups):
            groups.setdefault(group, []).append(gate)
        return groups


    def visible_groups(self):
        groups = []
        for group, gates in sorted(self.grouped_gates().items()):
            if len(gates) > 1:
                groups.append((group, gates))
        return groups


    def create_text_layout(self, text, selected=False):
        layout = self.create_pango_layout(text)
        weight = "Bold " if selected else ""
        layout.set_font_description(
            Pango.FontDescription(f"Sans {weight}{self.font_size()}")
        )
        return layout


    def text_size(self, text, selected=False):
        layout = self.create_text_layout(text, selected)
        return layout.get_pixel_size()


    def font_size(self):
        count = max(1, len(self.ttg_map))

        if count <= 4:
            return 16
        if count <= 8:
            return 14
        if count <= 12:
            return 13
        return 12


    def max_tool_label_width(self):
        count = len(self.ttg_map)
        if count <= 0:
            return 0

        max_tool = count - 1
        width, _ = self.text_size(f"T{max_tool}", selected=True)
        return width


    def max_gate_label_width(self):
        count = max(len(self.ttg_map), len(self.es_groups))
        if count <= 0:
            return 0

        max_gate = count - 1
        width, _ = self.text_size(f"#{max_gate}", selected=True)
        return width


    def layout_values(self):
        alloc = self.get_allocation()
        width = max(1, alloc.width)

        group_count = len(self.visible_groups())
        group_width = 0
        if group_count:
            group_width = (
                self.GROUP_AFTER_GATE_LABEL_GAP
                + self.GROUP_BRACKET_WIDTH
                + (group_count - 1) * self.GROUP_COLUMN_SPACING
                + 18
            )

        tool_label_width = self.max_tool_label_width()
        gate_label_width = self.max_gate_label_width()

        tool_label_right_x = self.LEFT_PAD + tool_label_width
        tool_line_start_x = tool_label_right_x + self.TOOL_LABEL_GAP

        gate_label_x = width - self.RIGHT_PAD - group_width - gate_label_width
        gate_line_end_x = gate_label_x - self.GATE_LABEL_GAP

        min_span = self.TOOL_STUB + self.GATE_STUB + 20
        if gate_line_end_x < tool_line_start_x + min_span:
            gate_line_end_x = tool_line_start_x + min_span
            gate_label_x = gate_line_end_x + self.GATE_LABEL_GAP

        group_start_x = gate_label_x + gate_label_width + self.GROUP_AFTER_GATE_LABEL_GAP

        return {
            "tool_label_right_x": tool_label_right_x,
            "tool_line_start_x": tool_line_start_x,
            "gate_line_end_x": gate_line_end_x,
            "gate_label_x": gate_label_x,
            "group_start_x": group_start_x,
        }


    def set_source_normal(self, cr):
        context = self.get_style_context()
        color = context.get_color(Gtk.StateFlags.NORMAL)
        cr.set_source_rgba(color.red, color.green, color.blue, color.alpha)


    def set_source_selected(self, cr):
        cr.set_source_rgba(*self.SELECTED_RGBA)


    def set_source_for_selected(self, cr, selected):
        if selected:
            self.set_source_selected(cr)
        else:
            self.set_source_normal(cr)


    def on_draw(self, widget, cr):
        if not self.ttg_map:
            return False

        cr.set_line_cap(1)
        cr.set_line_join(1)

        values = self.layout_values()

        self.draw_paths(cr, values)
        self.draw_tool_labels(cr, values)
        self.draw_gate_labels(cr, values)
        self.draw_groups(cr, values)

        return False


    def draw_paths(self, cr, values):
        # Draw non-selected paths first
        for tool, gate in enumerate(self.ttg_map):
            if tool != self.selected_tool:
                self.draw_path(cr, values, tool, gate)

        # Draw selected path last, so it appears on top
        if 0 <= self.selected_tool < len(self.ttg_map):
            self.draw_path(
                cr,
                values,
                self.selected_tool,
                self.ttg_map[self.selected_tool],
            )


    def draw_path(self, cr, values, tool, gate):
        if gate < 0 or gate >= max(1, len(self.ttg_map)):
            return

        selected = tool == self.selected_tool

        self.set_source_for_selected(cr, selected)
        cr.set_line_width(
            self.SELECTED_LINE_WIDTH if selected else self.NORMAL_LINE_WIDTH
        )

        y_tool = self.y_for(tool)
        y_gate = self.y_for(gate)

        start_x = values["tool_line_start_x"]
        tool_stub_end_x = start_x + self.TOOL_STUB
        gate_end_x = values["gate_line_end_x"]
        gate_stub_start_x = gate_end_x - self.GATE_STUB

        if gate_stub_start_x < tool_stub_end_x + 8:
            center_x = (tool_stub_end_x + gate_stub_start_x) / 2.0
            tool_stub_end_x = center_x - 4
            gate_stub_start_x = center_x + 4

        cr.move_to(start_x, y_tool)
        cr.line_to(tool_stub_end_x, y_tool)
        cr.line_to(gate_stub_start_x, y_gate)
        cr.line_to(gate_end_x, y_gate)
        cr.stroke()

        self.draw_square(cr, start_x, y_tool, selected)
        self.draw_arrow(cr, gate_end_x, y_gate, selected)


    def draw_tool_labels(self, cr, values):
        for tool in range(len(self.ttg_map)):
            selected = tool == self.selected_tool
            text = "T%d" % tool
            y = self.y_for(tool)
            x = values["tool_label_right_x"]
            self.draw_text(cr, text, x, y, selected=selected, right=True, centered=True)


    def draw_gate_labels(self, cr, values):
        gate_count = max(len(self.ttg_map), len(self.es_groups))
        for gate in range(gate_count):
            selected = gate == self.selected_gate
            text = "#%d" % gate
            y = self.y_for(gate)
            x = values["gate_label_x"]
            self.draw_text(cr, text, x, y, selected=selected, centered=True)


    def draw_groups(self, cr, values):
        if not self.endless_spool_enabled:
            return

        current_group = self.current_group()
        x = values["group_start_x"]

        for group, gates in self.visible_groups():
            selected = group == current_group
            self.set_source_for_selected(cr, selected)
            cr.set_line_width(self.SELECTED_LINE_WIDTH if selected else self.NORMAL_LINE_WIDTH)

            y_values = [self.y_for(gate) for gate in gates]
            y_first = min(y_values)
            y_last = max(y_values)
            bracket_x = x + self.GROUP_BRACKET_WIDTH

            cr.move_to(bracket_x, y_first)
            cr.line_to(bracket_x, y_last)
            cr.stroke()

            for y in y_values:
                cr.move_to(x, y)
                cr.line_to(bracket_x, y)
                cr.stroke()

            letter = self.group_letter(group)
            label_y = y_last + self.calc_row_height() / 2.0 + self.GROUP_LABEL_GAP
            self.draw_text(
                cr,
                letter,
                bracket_x,
                label_y,
                selected=selected,
                centered=True,
                horizontal_center=True,
            )

            x += self.GROUP_COLUMN_SPACING


    def group_letter(self, group):
        if group is None or group < 0:
            return "?"
        if group < 26:
            return chr(ord("A") + group)
        return str(group)


    def draw_text(self, cr, text, x, y, selected=False, right=False, centered=False, horizontal_center=False):
        self.set_source_for_selected(cr, selected)

        layout = self.create_text_layout(text, selected)
        width, height = layout.get_pixel_size()

        draw_x = x
        draw_y = y

        if right:
            draw_x -= width
        elif horizontal_center:
            draw_x -= width / 2.0

        if centered:
            draw_y -= height / 2.0

        cr.move_to(draw_x, draw_y)
        PangoCairo.show_layout(cr, layout)


    def draw_square(self, cr, x, y, selected=False):
        self.set_source_for_selected(cr, selected)
        size = 7 if not selected else 8
        cr.rectangle(x - size / 2.0, y - size / 2.0, size, size)
        cr.fill()


    def draw_arrow(self, cr, x, y, selected=False):
        self.set_source_for_selected(cr, selected)
        size = 7 if not selected else 8

        cr.move_to(x, y)
        cr.line_to(x - size, y - size / 2.0)
        cr.line_to(x - size, y + size / 2.0)
        cr.close_path()
        cr.fill()
