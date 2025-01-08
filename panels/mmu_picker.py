# Happy Hare MMU Software
# Display and selection of tools based on color and material
#
# Copyright (C) 2023-2025  moggieuk#6538 (discord)
#                          moggieuk@hotmail.com
#
import logging, gi

gi.require_version("Gtk", "3.0")

from gi.repository import Gtk, GLib, Pango, Gdk
from ks_includes.screen_panel import ScreenPanel

class Panel(ScreenPanel):
    TOOL_UNKNOWN = -1
    TOOL_BYPASS = -2

    GATE_UNKNOWN = -1
    GATE_EMPTY = 0
    GATE_AVAILABLE = 1
    GATE_AVAILABLE_FROM_BUFFER = 2

    DUMMY = -99

    COLOR_SWATCH = '⬤'
    EMPTY_SWATCH = '◯'

    def __init__(self, screen, title):
        super().__init__(screen, title)

        self.COLOR_RED = Gdk.RGBA(1,0,0,1)
        self.COLOR_GREEN = Gdk.RGBA(0,1,0,1)
        self.COLOR_DARK_GREY = Gdk.RGBA(0.2,0.2,0.2,1)
        self.COLOR_LIGHT_GREY = Gdk.RGBA(0.5,0.5,0.5,1)
        self.COLOR_ORANGE = Gdk.RGBA(1,0.8,0,1)

        grid = Gtk.Grid()
        grid.set_column_homogeneous(True)
        grid.set_row_spacing(10)

        mmu = self._printer.get_stat("mmu")
        num_tools = len(mmu['gate_status'])
        for i in range(num_tools):
            status_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
            status = self.labels[f'status_{i}'] = self._gtk.Image()
            available = self.labels[f'available_{i}'] = Gtk.Label("Unknown")
            available.get_style_context().add_class("mmu_available_text")
            status_box.pack_start(status, True, True, 0)
            status_box.pack_start(available, True, True, 0)

            tool = self.labels[f'tool_{i}'] = self._gtk.Button('extruder', f'T{i}', 'color2')
            tool.connect("clicked", self.select_tool, i)

            color = self.labels[f'color_{i}'] = Gtk.Label(self.EMPTY_SWATCH)
            color.get_style_context().add_class("mmu_color_swatch")
            color.set_xalign(0.7)

            material = self.labels[f'material_{i}'] = Gtk.Label("n/a")
            material.get_style_context().add_class("mmu_material_text")
            material.set_xalign(0.1)

            gate_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
            gate = self.labels[f'gate_{i}'] = Gtk.Label("n/a")
            gate.get_style_context().add_class("mmu_gate_text")
            gate.set_halign(Gtk.Align.START)
            gate.set_valign(Gtk.Align.END)
            alt_gates = self.labels[f'alt_gates_{i}'] = Gtk.Label("n/a")
            alt_gates.set_halign(Gtk.Align.START)
            alt_gates.set_valign(Gtk.Align.START)
            gate_box.pack_start(gate, True, True, 0)
            gate_box.pack_start(alt_gates, True, True, 0)

            grid.attach(status_box, 0, i, 3, 1)
            grid.attach(tool,       3, i, 3, 1)
            grid.attach(color,      6, i, 2, 1)
            grid.attach(material,   8, i, 3, 1)
            grid.attach(gate_box,  11, i, 5, 1)

        self.labels['unknown_icon'] = self._gtk.Image('mmu_unknown').get_pixbuf()
        self.labels['available_icon'] = self._gtk.Image('mmu_tick').get_pixbuf()
        self.labels['empty_icon'] = self._gtk.Image('mmu_cross').get_pixbuf()

        scroll = self._gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.add(grid)
        self.content.add(scroll)

    def activate(self):
        mmu = self._printer.get_stat("mmu")
        endless_spool = mmu['endless_spool']
        tool_map = self.build_tool_map()
        gate_status = mmu['gate_status']
        gate_material = mmu['gate_material']
        gate_color = mmu['gate_color']
        num_tools = len(gate_status)

        for i in range(num_tools):
            t_map = tool_map[i]
            gate = t_map['gate']
            color = Gdk.RGBA()
            if not Gdk.RGBA.parse(color, gate_color[gate]):
                Gdk.RGBA.parse(color, '#' + gate_color[gate])

            gate_str = (f"Gate #{t_map['gate']}")
            alt_gate_str = ''
            if endless_spool == 1 and len(t_map['alt_gates']) > 0:
                alt_gate_str = '+(' + ', '.join(map(str, t_map['alt_gates'][:6]))
                alt_gate_str += ', ...)' if len(t_map['alt_gates']) > 6 else ')'

            status_icon, status_str, status_color = self.get_status_details(gate_status[gate])
            self.labels[f'status_{i}'].clear()
            self.labels[f'status_{i}'].set_from_pixbuf(self.labels[f'{status_icon}'])
            self.labels[f'available_{i}'].set_label(status_str)
            self.labels[f'available_{i}'].override_color(Gtk.StateType.NORMAL, status_color)
            self.labels[f'tool_{i}'].set_sensitive(gate_status[i] in (self.GATE_AVAILABLE, self.GATE_AVAILABLE_FROM_BUFFER))
            if gate_color[i] != '':
                self.labels[f'color_{i}'].set_text(self.COLOR_SWATCH)
            else:
                self.labels[f'color_{i}'].set_text(self.EMPTY_SWATCH)
            self.labels[f'color_{i}'].override_color(Gtk.StateType.NORMAL, color)
            self.labels[f'material_{i}'].set_label(gate_material[gate][:6])
            self.labels[f'gate_{i}'].set_label(gate_str)
            self.labels[f'alt_gates_{i}'].set_label(alt_gate_str)

    def get_status_details(self, gate_status):
        if gate_status == self.GATE_AVAILABLE:
            status_icon = 'available_icon'
            status_str = "Available"
            status_color = self.COLOR_GREEN
        elif gate_status == self.GATE_AVAILABLE_FROM_BUFFER:
            status_icon = 'available_icon'
            status_str = "Buffered"
            status_color = self.COLOR_GREEN
        elif gate_status == self.GATE_EMPTY:
            status_icon = 'empty_icon'
            status_str = "Empty"
            status_color = self.COLOR_RED
        else: 
            status_icon = 'unknown_icon'
            status_str = "Unknown"
            status_color = self.COLOR_LIGHT_GREY
        return status_icon, status_str, status_color

    # Structure is:
    # tool_map = [ { 'gate': <gate>, 'alt_gates': <alternative_gates> }, ... ]
    def build_tool_map(self):
        tool_map = []
        mmu = self._printer.get_stat("mmu")
        endless_spool_groups = mmu['endless_spool_groups']
        ttg_map = mmu['ttg_map']
        num_tools = len(ttg_map)
        for tool in range(num_tools):
            es_group = endless_spool_groups[tool]
            alt_gates = []
            for i in range(len(endless_spool_groups) - 1):
                alt = (tool + i + 1) % num_tools
                if endless_spool_groups[alt] == es_group:
                    alt_gates.append(alt)
            tool_map.append({ 'gate': ttg_map[tool], 'alt_gates': alt_gates })
        return tool_map

    def process_update(self, action, data):
        if action == "notify_status_update":
            if 'configfile' in data:
                return
            elif 'mmu' in data:
                e_data = data['mmu']
                if 'tool' in e_data or 'gate' in e_data or 'gate_status' in e_data or 'gate_material' in e_data or 'gate_color' in e_data:
                    self.activate()

    def select_tool(self, widget, selected_tool):
        mmu = self._printer.get_stat("mmu")
        tool = mmu['tool']
        filament = mmu['filament']
        if tool == self.TOOL_BYPASS and filament == "Loaded":
            # Should not of got here but do nothing for safety
            pass
        else:
            self._screen._ws.klippy.gcode_script(f"MMU_CHANGE_TOOL TOOL={selected_tool}")
            self._screen._menu_go_back()

