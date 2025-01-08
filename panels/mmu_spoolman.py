# Happy Hare MMU Software
# Display filaments loaded on each gate with Spoolman integration
#
# Copyright (C) 2023-2025  moggieuk#6538 (discord)
#                          moggieuk@hotmail.com
#
import logging, gi

gi.require_version("Gtk", "3.0")

from gi.repository import Gtk, GLib, Pango, Gdk, GdkPixbuf, GObject
from ks_includes.screen_panel import ScreenPanel
from ks_includes.KlippyRest import KlippyRest
from panels.spoolman import SpoolmanSpool
import threading, time

class Panel(ScreenPanel):
    apiClient: KlippyRest
    TOOL_UNKNOWN = -1
    TOOL_BYPASS = -2

    GATE_UNKNOWN = -1
    GATE_EMPTY = 0
    GATE_AVAILABLE = 1
    GATE_AVAILABLE_FROM_BUFFER = 2

    def __init__(self, screen, title):
        super().__init__(screen, title)
        self.ui_sel_tool = 0

        self.COLOR_RED = Gdk.RGBA(1,0,0,1)
        self.COLOR_GREEN = Gdk.RGBA(0,1,0,1)
        self.COLOR_DARK_GREY = Gdk.RGBA(0.2,0.2,0.2,1)
        self.COLOR_LIGHT_GREY = Gdk.RGBA(0.5,0.5,0.5,1)
        self.COLOR_ORANGE = Gdk.RGBA(1,0.8,0,1)

        self.apiClient = screen.apiclient

        self.spools={}
        SpoolmanSpool.theme_path = screen.theme
        GObject.type_register(SpoolmanSpool)
        self.load_spools()

        grid = Gtk.Grid()
        grid.set_column_homogeneous(True)
        grid.set_row_spacing(10)

        mmu = self._printer.get_stat("mmu")
        num_gates = len(mmu['gate_status'])

        for i in range(num_gates):
            status_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
            available = self.labels[f'available_{i}'] = Gtk.Label("Unknown")
            available.get_style_context().add_class("mmu_status_text")
            status_box.pack_start(available, True, True, 0)

            gate_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
            gate_label = self.labels[f'gate_label_{i}'] = Gtk.Label(f'#{i}')
            gate_label.get_style_context().add_class("mmu_spoolman_gate_text")
            gate_box.pack_start(gate_label, True, True, 0)

            color = self.labels[f'color_{i}'] = Gtk.Label(f'⬤')
            color.get_style_context().add_class("mmu_spoolman_color_swatch")
            color.set_xalign(0.0)
            color_image = self.labels[f'color_image_{i}'] = self._gtk.Image()
            color_image.get_style_context().add_class("mmu_color_image")

            material = self.labels[f'material_{i}'] = Gtk.Label("n/a")
            material.get_style_context().add_class("mmu_spoolman_material_text")
            material.set_xalign(0)

            filament = self.labels[f'filament_{i}'] = Gtk.Label("n/a")
            filament.get_style_context().add_class("mmu_filament_text")
            filament.set_xalign(0)

            vendor = self.labels[f'vendor_{i}'] = Gtk.Label("n/a")
            vendor.get_style_context().add_class("mmu_vendor_text")
            vendor.set_xalign(0)

            usage = self.labels[f'usage_{i}'] = Gtk.Label("n/a")
            usage.get_style_context().add_class("mmu_usage_text")
            usage.set_xalign(0)

            remaining_weight = self.labels[f'remaining_weight_{i}'] = Gtk.Label("n/a")
            remaining_weight.get_style_context().add_class("mmu_remaining_weight_text")
            remaining_weight.set_xalign(1)

            remaining_percentage = self.labels[f'remaining_percentage_{i}'] = Gtk.Label("n/a")
            remaining_percentage.get_style_context().add_class("mmu_remaining_percentage_text")
            remaining_percentage.set_xalign(1)

            tools = self.labels[f'tools_{i}'] = Gtk.Label("n/a")
            tools.get_style_context().add_class("mmu_spoolman_tool_text")
            tools.set_xalign(0.3)

            grid.attach(gate_box,             0, i, 1, 1)
            grid.attach(tools,                1, i, 1, 1)
            grid.attach(color,                2, i, 1, 1)
            #grid.attach(color_image,          2, i, 1, 1)
            grid.attach(material,             3, i, 1, 1)
            grid.attach(filament,             4, i, 3, 1)
            grid.attach(remaining_weight,     7, i, 1, 1)
            grid.attach(remaining_percentage, 8, i, 1, 1)
            grid.attach(status_box,           9, i, 2, 1)

        grid.set_row_spacing(0)
        grid.set_row_spacing(0)

        scroll = self._gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.add(grid)

        self.labels['layers'] = layers = Gtk.Notebook()
        layers.set_show_tabs(False)
        layers.insert_page(scroll, None, 0)

        self.content.add(layers)

    def async_spools_refresh(self):
        while self.is_running:
            self.load_spools()
            GLib.timeout_add_seconds(2, self.refresh)
            time.sleep(10)

    def load_spools(self):
        hide_archived=False
        spools = self.apiClient.post_request("server/spoolman/proxy", json={
            "request_method": "GET",
            "path": f"/v1/spool?allow_archived={not hide_archived}",
        })
        if not spools or "result" not in spools:
            logging.error("Exception when trying to fetch spools")
            return
        self.spools.clear()
        for spool in spools["result"]:
            spoolObject = SpoolmanSpool(**spool)
            self.spools[str(spoolObject.id)]=spoolObject

    def activate(self):
        self.is_running=True
        self.timer=threading.Timer(10,self.async_spools_refresh)
        self.timer.start()
        self.refresh()

    def refresh(self):
        self.gate_tool_map = self.build_gate_tool_map()
        mmu = self._printer.get_stat("mmu")
        gate_status = mmu['gate_status']
        gate_material = mmu['gate_material']
        gate_spool_id = mmu['gate_spool_id']
        gate_color = mmu['gate_color']
        num_gates = len(gate_status)
        gate= mmu['gate']
        for i in range(num_gates):
            g_map = self.gate_tool_map[i]
            status_icon, status_str, status_color = self.get_status_details(gate_status[i])
            tool_str = self.get_tool_details(g_map['tools'])
            color = self.get_color_details(gate_color[i])
            background_color=None
            if gate == i:
                self.labels[f'gate_label_{i}'].set_label(f'> #{i}')
                self.labels[f'gate_label_{i}'].override_color(Gtk.StateType.NORMAL, self.COLOR_GREEN)
                background_color=self.COLOR_DARK_GREY
            else:
                self.labels[f'gate_label_{i}'].set_label(f'#{i}')
                self.labels[f'gate_label_{i}'].override_color(Gtk.StateType.NORMAL, None)

            self.labels[f'available_{i}'].set_label(status_str)
            self.labels[f'available_{i}'].override_color(Gtk.StateType.NORMAL, status_color)
            self.labels[f'color_{i}'].override_color(Gtk.StateType.NORMAL, color)

            for a in [self.labels[f'gate_label_{i}'],self.labels[f'available_{i}'], self.labels[f'tools_{i}'], self.labels[f'filament_{i}'],self.labels[f'remaining_percentage_{i}'],self.labels[f'remaining_weight_{i}'],self.labels[f'material_{i}'],self.labels[f'color_{i}']]:
                a.override_background_color(Gtk.StateType.NORMAL, background_color)

            material="-"
            vendor=""
            filament="-"
            usage=""
            remaining_length=""
            remaining_weight=""
            remaining_percentage=""
            remaining_percentage_val=0
            if str(gate_spool_id[i]) in self.spools:
                spool=self.spools[str(gate_spool_id[i])]
                material=spool.filament.material
                if spool.filament.vendor:
                    vendor=spool.filament.vendor.name
                else:
                    vendor = "n/a"
                filament=spool.filament.name
                pixbuf=spool.icon
                used_length=spool.used_length/10.0
                if hasattr(spool,"remaining_length"):
                    remaining_length_val=spool.remaining_length/10.0
                    remaining_length=f"{remaining_length_val:.2f}cm"
                if hasattr(spool,"remaining_weight"):
                    remaining_weight_val=spool.remaining_weight
                    remaining_weight=f"{remaining_weight_val:.0f}g"
                    remaining_percentage_val=100/(spool.filament.weight/spool.remaining_weight) if spool.remaining_weight else 0
                    remaining_percentage=f"{remaining_percentage_val:.0f}%"

                color_hex=spool.filament.color_hex[:6].lower() if hasattr(spool.filament, 'color_hex') else ''
                color = Gdk.RGBA()
                if not Gdk.RGBA.parse(color, color_hex):
                    Gdk.RGBA.parse(color, '#' + color_hex)
                self.labels[f'color_{i}'].override_color(Gtk.StateType.NORMAL, color)
                usage=f"{used_length:.2f}" 
                self.labels[f'color_image_{i}'].set_from_pixbuf(pixbuf.scale_simple(pixbuf.get_width()*0.9, pixbuf.get_height()*0.9, 1))

            self.labels[f'remaining_weight_{i}'].set_label(remaining_weight) 
            self.labels[f'remaining_percentage_{i}'].set_label(remaining_percentage) 

            color = self.COLOR_GREEN
            if remaining_percentage_val < 5:
                color = self.COLOR_RED
            elif remaining_percentage_val < 30:
                color = self.COLOR_ORANGE
            self.labels[f'remaining_percentage_{i}'].override_color(Gtk.StateType.NORMAL,color)

            self.labels[f'material_{i}'].set_label(material[:6]) 
            self.labels[f'filament_{i}'].set_label(filament[:15])
            #self.labels[f'vendor_{i}'].set_label(vendor) 
            self.labels[f'tools_{i}'].set_label(tool_str)

        self.labels['layers'].set_current_page(0) # Gate list layer

    def deactivate(self):
        self.is_running=False

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

    def get_tool_details(self, tools):
        tool_str = ''
        if len(tools) > 0:
            tool_str = 'T' + ', '.join(map(str, tools[:1]))
            tool_str += '..' if len(tools) > 1 else ''
        return tool_str

    def get_color_details(self, gate_color):
        if gate_color == None:
            gate_color = ''
        color = Gdk.RGBA()
        if not Gdk.RGBA.parse(color, gate_color):
            Gdk.RGBA.parse(color, '#' + gate_color)
        return color

    # gate_tool_map = [ { 'tools': <list of tools mapped to this gate> } ]
    def build_gate_tool_map(self):
        gate_tool_map = []
        mmu = self._printer.get_stat("mmu")
        ttg_map = mmu['ttg_map']
        num_gates = len(ttg_map)
        for gate in range(num_gates):
            tools = []
            for tool in range(num_gates):
                if ttg_map[tool] == gate:
                    tools.append(tool)
            gate_tool_map.append({ 'tools': tools })
        return gate_tool_map

    def process_update(self, action, data):
        if action == "notify_status_update":
            if 'configfile' in data:
                return
            elif 'mmu' in data:
                e_data = data['mmu']
                if 'ttg_map' in e_data or 'gate' in e_data or 'gate_status' in e_data in e_data or 'gate_spool_id' in e_data:
                    self.refresh()

