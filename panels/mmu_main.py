# Happy Hare MMU Software
# Main MMU management panel
#
# Copyright (C) 2023-2025  moggieuk#6538 (discord)
#                          moggieuk@hotmail.com
#
import logging, gi, re

gi.require_version("Gtk", "3.0")

from gi.repository import Gtk, Gdk, GLib, Pango
from ks_includes.screen_panel import ScreenPanel

class Panel(ScreenPanel):
    # These are a subset of constants from main Happy Hare for convenience and coding consistency
    TOOL_GATE_UNKNOWN = -1
    TOOL_GATE_BYPASS = -2

    GATE_UNKNOWN = -1
    GATE_EMPTY = 0
    GATE_AVAILABLE = 1
    GATE_AVAILABLE_FROM_BUFFER = 2

    FILAMENT_POS_UNKNOWN = -1
    FILAMENT_POS_UNLOADED = 0
    FILAMENT_POS_HOMED_GATE = 1
    FILAMENT_POS_START_BOWDEN = 2
    FILAMENT_POS_IN_BOWDEN = 3
    FILAMENT_POS_END_BOWDEN = 4
    FILAMENT_POS_HOMED_ENTRY = 5
    FILAMENT_POS_HOMED_EXTRUDER = 6
    FILAMENT_POS_EXTRUDER_ENTRY = 7
    FILAMENT_POS_HOMED_TS = 8
    FILAMENT_POS_IN_EXTRUDER = 9    # AKA FILAMENT_POS_PAST_TS
    FILAMENT_POS_LOADED = 10        # AKA FILAMENT_POS_HOMED_NOZZLE

    DIRECTION_LOAD = 1
    DIRECTION_UNLOAD = -1

    ENDSTOP_ENCODER  = "encoder"    # Fake Gate endstop
    ENDSTOP_GATE     = "mmu_gate"   # Gate
    ENDSTOP_EXTRUDER = "extruder"   # Extruder
    ENDSTOP_TOOLHEAD = "toolhead"

    NOT_SET = -99

    def __init__(self, screen, title):
        super().__init__(screen, title)

        # We need to keep track of just a little bit of UI state
        self.ui_runout_mark = 0.
        self.ui_sel_tool = self.NOT_SET

        self.has_bypass = False
        self.min_tool = 0
        self.has_bypass = self._printer.get_stat("mmu")['has_bypass']
        if self.has_bypass:
            self.min_tool = self.TOOL_GATE_BYPASS

        # btn_states: The "gaps" are what functionality the state takes away. Multiple states are combined
        self.btn_states = {
            'all':             ['check_gates', 'tool', 'unload', 'picker', 'pause', 'message', 'extrude', 'unlock', 'resume', 'manage', 'more'],
            'printing':        [                                           'pause',                                                     'more'],
            'pause_locked':    ['check_gates', 'tool', 'unload', 'picker',          'message',            'unlock', 'resume', 'manage', 'more'],
            'paused':          ['check_gates', 'tool', 'unload', 'picker',          'message', 'extrude',           'resume', 'manage', 'more'],
            'idle':            ['check_gates', 'tool', 'unload', 'picker', 'pause', 'message', 'extrude',                     'manage', 'more'],
            'bypass_loaded':   [                       'unload',           'pause', 'message', 'extrude', 'unlock', 'resume', 'manage', 'more'],
            'bypass_unloaded': ['check_gates', 'tool',           'picker', 'pause', 'message', 'extrude', 'unlock', 'resume', 'manage', 'more'],
            'bypass_unknown':  ['check_gates', 'tool', 'unload', 'picker', 'pause', 'message', 'extrude', 'unlock', 'resume', 'manage', 'more'],
            'tool_loaded':     ['check_gates', 'tool', 'unload', 'picker', 'pause', 'message', 'extrude', 'unlock', 'resume', 'manage', 'more'],
            'tool_unloaded':   ['check_gates', 'tool', 'unload', 'picker', 'pause', 'message', 'extrude', 'unlock', 'resume', 'manage', 'more'],
            'tool_unknown':    ['check_gates', 'tool', 'unload', 'picker', 'pause', 'message', 'extrude', 'unlock', 'resume', 'manage', 'more'],
            'no_message':      ['check_gates', 'tool', 'unload', 'picker', 'pause',            'extrude', 'unlock', 'resume', 'manage', 'more'],
            'busy':            [                                                                                              'manage', 'more'],
            'disabled':        [                                                                                                              ],
        }

        self.labels = {
            'check_gates': self._gtk.Button('mmu_checkgates', "Gates", 'color1'),
            'manage': self._gtk.Button('mmu_manage', "Manage...",'color2'),
            't_decrease': self._gtk.Button('decrease', None, scale=self.bts * 1.2),
            'tool': self._gtk.Button('mmu_extruder', 'Load T0', 'color2'),
            't_increase': self._gtk.Button('increase', None, scale=self.bts * 1.2),
            'picker': self._gtk.Button('mmu_tool_picker', 'Tools...', 'color3'),
            'unload': self._gtk.Button('mmu_unload', 'Unload', 'color4'), # Doubles as eject button
            'pause': self._gtk.Button('pause', 'MMU Pause', 'color1'),
            'message': self._gtk.Button('warning', 'Last Error', 'color1'),
            'unlock': self._gtk.Button('heat-up', 'Unlock', 'color2'),
            'resume': self._gtk.Button('resume', 'Resume', 'color3'),
            'extrude': self._gtk.Button('extrude', 'Extrude...', 'color4'),
            'more': self._gtk.Button('mmu_more', 'More...', 'color1'),
            'tool_icon': self._gtk.Image('mmu_extruder', self._gtk.img_width * 0.8, self._gtk.img_height * 0.8),
            'tool_label': Gtk.Label('Unknown'),
            'filament': Gtk.Label('Filament: Unknown'),
            'sensor': Gtk.Label('Ts:'),
            'sensor_state': Gtk.Label('   '),
            'select_bypass_img': self._gtk.Image('mmu_select_bypass'), # Alternative for tool
            'load_bypass_img': self._gtk.Image('mmu_load_bypass'),     # Alternative for picker
            'unload_bypass_img': self._gtk.Image('mmu_unload_bypass'), # Alternative for unload/eject
            'eject_img': self._gtk.Image('mmu_eject'), # Alternative for unload button to fully eject
            'sync_drive_img': self._gtk.Image('mmu_synced_extruder', self._gtk.img_width * 0.8, self._gtk.img_height * 0.8), # Alternative for tool_icon
        }
        self.labels['unload_img'] = self.labels['unload'].get_image()
        self.labels['tool_img'] = self.labels['tool'].get_image()
        self.labels['tool_picker_img'] = self.labels['picker'].get_image()
        self.labels['tool_icon_pixbuf'] = self.labels['tool_icon'].get_pixbuf()
        self.labels['sync_drive_pixbuf'] = self.labels['sync_drive_img'].get_pixbuf()

        self.labels['check_gates'].connect("clicked", self.select_check_gates)
        self.labels['manage'].connect("clicked", self.menu_item_clicked, {"panel": "mmu_manage", "name": "MMU Manage"})
        self.labels['t_decrease'].connect("clicked", self.select_tool, -1)
        self.labels['tool'].connect("clicked", self.select_tool, 0)
        self.labels['t_increase'].connect("clicked", self.select_tool, 1)
        self.labels['picker'].connect("clicked", self.select_picker)
        self.labels['unload'].connect("clicked", self.select_unload_eject)
        self.labels['pause'].connect("clicked", self.select_pause)
        self.labels['message'].connect("clicked", self.select_message)
        self.labels['unlock'].connect("clicked", self.select_unlock)
        self.labels['resume'].connect("clicked", self.select_resume)
        self.labels['extrude'].connect("clicked", self.menu_item_clicked, {"panel": "extrude", "name": "Extrude"})
        self.labels['more'].connect("clicked", self._screen._go_to_submenu, "mmu")

        self.labels['t_increase'].set_hexpand(False)
        self.labels['t_increase'].get_style_context().add_class("mmu_sel_increase")
        self.labels['t_decrease'].set_hexpand(False)
        self.labels['t_decrease'].get_style_context().add_class("mmu_sel_decrease")

        self.labels['manage'].get_style_context().add_class("mmu_manage_button")
        self.labels['manage'].set_valign(Gtk.Align.CENTER)
        self.labels['tool_icon'].get_style_context().add_class("mmu_tool_image")
        self.labels['tool_label'].get_style_context().add_class("mmu_tool_text")
        self.labels['tool_label'].set_xalign(0)
        self.labels['filament'].set_xalign(0)
        self.labels['sensor'].set_xalign(1)
        self.labels['sensor_state'].set_xalign(0)
        self.labels['sensor_state'].get_style_context().add_class("mmu_sensor_text")

        scale = Gtk.Scale.new_with_range(orientation=Gtk.Orientation.VERTICAL, min=-30., max=0., step=0.1)
        self.labels['scale'] = scale
        scale.add_mark(0., Gtk.PositionType.RIGHT, f"0")
        scale.set_show_fill_level(True)
        scale.set_restrict_to_fill_level(False)
        scale.set_inverted(True)
        scale.set_value_pos(Gtk.PositionType.TOP)
        scale.set_digits(1)
        scale.set_can_focus(False)
        scale.get_style_context().add_class("mmu_runout")
        scale.connect("format_value", self._mm_format)

        runout_frame = Gtk.Frame()
        self.labels['runout_frame'] = runout_frame
        runout_frame.set_label(f"Clog")
        runout_frame.set_label_align(0.5, 0)
        runout_frame.add(scale)

        manage_grid = Gtk.Grid()
        manage_grid.set_column_homogeneous(True)

        mmu = self._printer.get_stat("mmu")
        num_gates = len(mmu['gate_status'])
        if num_gates > 9:
            manage_grid.attach(Gtk.Label(),           0, 0, 1, 3)
            manage_grid.attach(self.labels['manage'], 1, 0, 2, 3)
        else:
            manage_grid.attach(self.labels['manage'], 0, 0, 3, 3)

        runout_layer = Gtk.Notebook()
        self.labels['runout_layer'] = runout_layer
        runout_layer.set_show_tabs(False)
        runout_layer.insert_page(manage_grid, None, 0)
        runout_layer.insert_page(runout_frame, None, 1)
        runout_layer.set_current_page(0)
        
        # TextView has problems in this use case so use 5 separate labels... Simple!
        status_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        for i in range(5):
            name = (f'status{i+1}')
            self.labels[name] = Gtk.Label()
            self.labels[name].get_style_context().add_class("mmu_status")
            self.labels[name].set_xalign(0)
            if i < 4:
                status_box.pack_start(self.labels[name], False, True, 0)
            else:
                self.labels[name].get_style_context().add_class("mmu_status_filament")

        top_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        top_box.pack_start(self.labels['tool_icon'], False, True, 0)
        top_box.pack_start(self.labels['tool_label'], True, True, 0)
        top_box.pack_start(self.labels['filament'], True, True, 0)
        top_box.pack_start(self.labels['sensor'], False, True, 0)
        top_box.pack_start(self.labels['sensor_state'], False, True, 0)

        pause_layer = Gtk.Notebook()
        self.labels['pause_layer'] = pause_layer
        pause_layer.set_show_tabs(False)
        pause_layer.insert_page(self.labels['pause'], None, 0)
        pause_layer.insert_page(self.labels['message'], None, 1)

        top_grid = Gtk.Grid()
        top_grid.set_vexpand(False)
        top_grid.set_column_homogeneous(True)
        top_grid.attach(top_box,                0, 0,  9, 1)
        top_grid.attach(runout_layer,           9, 0,  3, 3)
        top_grid.attach(status_box,             0, 1, 10, 1)
        top_grid.attach(self.labels['status5'], 0, 2, 12, 1)

        tool_grid = Gtk.Grid()
        tool_grid.set_column_homogeneous(False)
        tool_grid.attach(self.labels['t_decrease'], 0, 0, 1, 1)
        tool_grid.attach(self.labels['tool'],       1, 0, 1, 1)
        tool_grid.attach(self.labels['t_increase'], 2, 0, 1, 1)

        main_grid = Gtk.Grid()
        main_grid.set_vexpand(True)
        main_grid.set_column_homogeneous(True)
        main_grid.attach(tool_grid,                   0, 0, 6, 1)
        main_grid.attach(self.labels['picker'],       6, 0, 2, 1)
        main_grid.attach(self.labels['unload'],        8, 0, 2, 1)
        main_grid.attach(self.labels['check_gates'], 10, 0, 2, 1)
        main_grid.attach(self.labels['pause_layer'],  0, 1, 3, 1)
        main_grid.attach(self.labels['unlock'],       3, 1, 2, 1)
        main_grid.attach(self.labels['resume'],       5, 1, 2, 1)
        main_grid.attach(self.labels['extrude'],      7, 1, 2, 1)
        main_grid.attach(self.labels['more'],         9, 1, 3, 1)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        box.pack_start(top_grid, False, True, 0)
        box.add(main_grid)

        scroll = self._gtk.ScrolledWindow()
        scroll.add(box)
        self.content.add(scroll)

        # Was in activate() but now process_update can occur before activate() !?
        self.ui_sel_tool = self.NOT_SET
        self.init_tool_value()
        self.config_update()

    def activate(self):
        self.config_update()
        self.update_status()
        self.update_filament_status()

    def post_attach(self):
        # Gtk Notebook will only change layer after show_all() hence this extra callback to fix state
        self.update_active_buttons()

    def config_update(self):
        self.markup_status = self._config.get_main_config().getboolean("mmu_color_gates", True)
        self.markup_filament = self._config.get_main_config().getboolean("mmu_color_filament", False)
        self.bold_filament = self._config.get_main_config().getboolean("mmu_bold_filament", False)

    def process_update(self, action, data):
        if action == "notify_status_update":
            try:
                if 'mmu_encoder mmu_encoder' in data: # There is only one mmu_encoder
                    ee_data = data['mmu_encoder mmu_encoder']
                    self.update_encoder(ee_data)

                if 'filament_switch_sensor toolhead_sensor' in data or 'filament_switch_sensor mmu_gate_sensor' in data or 'filament_switch_sensor extruder_sensor' in data:
                    self.update_filament_status()

                if 'mmu' in data:
                    e_data = data['mmu']
                    if 'tool' in e_data or 'gate' in e_data or 'ttg_map' in e_data or 'gate_status' in e_data or 'gate_color' in e_data:
                        self.update_status()
                    if 'tool' in e_data or 'filament_pos' in e_data or 'filament_direction' in e_data:
                        self.update_filament_status()
                    if 'tool' in e_data or 'next_tool' in e_data or 'sync_drive' in e_data or 'filament' in e_data:
                        self.update_tool()
                    if 'enabled' in e_data:
                        self.update_enabled()
                    if 'action' in e_data or 'print_state' in e_data:
                        ee_data = self._printer.get_stat('mmu_encoder mmu_encoder', None)
                        if ee_data:
                            self.update_movement(ee_data['encoder_pos'], ee_data['flow_rate'])
                        else:
                            self.update_movement()
                    if 'print_state' in e_data:
                        self.update_active_buttons()
                    self.update_active_buttons()
            except KeyError as ke:
                # Almost certainly a mismatch of Happy Hare on the printer
                msg = "You are probably trying to connect to an incompatible"
                msg += "\nversion of Happy Hare on your printer. Ensure Happy Hare"
                msg += "\nis up-to-date, re-run Happy-Hare/install.sh on the"
                msg += "\nprinter, then make sure you restart Klipper."
                msg += "\n\nI'll bet this will work out for you :-)"
                self._screen.show_popup_message(msg, 3, save=True)
                logging.info("Happy Hare: %s" % str(ke))

    def init_tool_value(self):
        mmu = self._printer.get_stat("mmu")
        if self.ui_sel_tool == self.NOT_SET and mmu['tool'] != self.TOOL_GATE_UNKNOWN:
            self.ui_sel_tool = mmu['tool']
        else:
            self.ui_sel_tool = 0

    def _mm_format(self, w, v):
        return f"{-v:.1f}mm"

    def select_check_gates(self, widget):
        self._screen._confirm_send_action(
            None,
            "Check filament availabily in all MMU gates?\n\nAre you sure you want to continue?",
            "printer.gcode.script",
            {'script': "MMU_CHECK_GATE ALL=1 QUIET=1"}
        )

    def select_tool(self, widget, param=0):
        mmu = self._printer.get_stat("mmu")
        num_gates = len(mmu['gate_status'])
        tool = mmu['tool']
        if param < 0 and self.ui_sel_tool > self.min_tool:
            self.ui_sel_tool -= 1
            if self.ui_sel_tool == self.TOOL_GATE_UNKNOWN:
                self.ui_sel_tool = self.TOOL_GATE_BYPASS
        elif param > 0 and self.ui_sel_tool < num_gates - 1:
            self.ui_sel_tool += 1
            if self.ui_sel_tool == self.TOOL_GATE_UNKNOWN:
                self.ui_sel_tool = 0
        elif param == 0:
            if self.ui_sel_tool == self.TOOL_GATE_BYPASS:
                self._screen._ws.klippy.gcode_script(f"MMU_SELECT_BYPASS")
            elif self.ui_sel_tool != tool or mmu['filament'] != "Loaded":
                self._screen._ws.klippy.gcode_script(f"MMU_CHANGE_TOOL TOOL={self.ui_sel_tool} QUIET=1")
            return
        self.update_tool_buttons()

    def select_unload_eject(self, widget):
        mmu = self._printer.get_stat("mmu")
        filament = mmu['filament']
        if filament != "Unloaded":
            self._screen._ws.klippy.gcode_script(f"MMU_UNLOAD")
        else:
            self._screen._ws.klippy.gcode_script(f"MMU_EJECT")

    def select_picker(self, widget):
        # This is a multipurpose button to select subpanel or load bypass
        mmu = self._printer.get_stat("mmu")
        tool = mmu['tool']
        if tool == self.TOOL_GATE_BYPASS:
            self._screen._ws.klippy.gcode_script(f"MMU_LOAD EXTRUDER_ONLY=1")
        else:
            self._screen.show_panel('mmu_picker', 'MMU Tool Picker')

    def select_pause(self, widget):
        self._screen._ws.klippy.gcode_script(f"MMU_PAUSE FORCE_IN_PRINT=1")

    def select_message(self, widget):
        last_toolchange = self._printer.get_stat('mmu', 'last_toolchange')
        self._screen.show_last_popup_message(f"Last Toolchange: {last_toolchange}")

    def select_resume(self, widget):
        self._screen._ws.klippy.gcode_script(f"RESUME")

    def select_unlock(self, widget):
        self._screen._ws.klippy.gcode_script(f"MMU_UNLOCK")

    def update_enabled(self):
        enabled = self._printer.get_stat('mmu', 'enabled')
        for i in range(5):
            name = (f'status{i+1}')
            if enabled:
                self.labels[name].get_style_context().remove_class("mmu_disabled_text")
            else:
                self.labels[name].get_style_context().add_class("mmu_disabled_text")

    def update_tool(self):
        mmu = self._printer.get_stat("mmu")
        tool = mmu['tool']
        next_tool = mmu['next_tool']
        last_tool = mmu['last_tool']
        sync_drive = mmu['sync_drive']
        filament = mmu['filament']
        if next_tool != self.TOOL_GATE_UNKNOWN:
            # Change in progress
            text = ("T%d " % last_tool) if (last_tool >= 0 and last_tool != next_tool) else "Bypass " if last_tool == -2 else "Unknown " if last_tool == -1 else ""
            text += ("> T%d" % next_tool) if next_tool >= 0 else ""
        else:
            text = ("T%d " % tool) if tool >= 0 else "Bypass " if tool == -2 else "Unknown " if tool == -1 else ""
        self.labels['tool_label'].set_text(text)
        if sync_drive:
            self.labels['tool_icon'].set_from_pixbuf(self.labels['sync_drive_pixbuf'])
        else:
            self.labels['tool_icon'].set_from_pixbuf(self.labels['tool_icon_pixbuf'])
        if tool == self.TOOL_GATE_BYPASS:
            self.labels['picker'].set_image(self.labels['load_bypass_img'])
            self.labels['picker'].set_label(f"Load")
            self.labels['unload'].set_image(self.labels['unload_bypass_img'])
            self.labels['unload'].set_label(f"Unload")
        else:
            self.labels['picker'].set_image(self.labels['tool_picker_img'])
            self.labels['picker'].set_label(f"Tools...")
            if filament != "Unloaded":
                self.labels['unload'].set_image(self.labels['unload_img'])
                self.labels['unload'].set_label("Unload")
            else:
                self.labels['unload'].set_image(self.labels['eject_img'])
                self.labels['unload'].set_label("Eject")

    def update_tool_buttons(self, tool_sensitive=True):
        mmu = self._printer.get_stat("mmu")
        num_gates = len(mmu['gate_status'])
        tool = mmu['tool']
        filament = mmu['filament']
        enabled = mmu['enabled']
        action = mmu['action']

        # Set sensitivity of +/- buttons
        if (tool == self.TOOL_GATE_BYPASS and filament == "Loaded") or not tool_sensitive:
            self.labels['t_decrease'].set_sensitive(False)
            self.labels['t_increase'].set_sensitive(False)
        else:
            if self.ui_sel_tool == self.min_tool:
                self.labels['t_decrease'].set_sensitive(False)
            else:
                self.labels['t_decrease'].set_sensitive(True)
    
            if self.ui_sel_tool == num_gates -1:
                self.labels['t_increase'].set_sensitive(False)
            else:
                self.labels['t_increase'].set_sensitive(True)

        # Set load button image and text
        if action == "Idle":
            if self.ui_sel_tool >= 0:
                self.labels['tool'].set_label(f"T{self.ui_sel_tool}")
                if mmu['tool'] == self.ui_sel_tool and filament == "Loaded":
                    self.labels['tool'].set_sensitive(False)
                else:
                    self.labels['tool'].set_sensitive(tool_sensitive)
            elif self.ui_sel_tool == self.TOOL_GATE_BYPASS:
                self.labels['tool'].set_label(f"Bypass")
                self.labels['tool'].set_sensitive(tool_sensitive)
            else:
                self.labels['tool'].set_label(f"n/a")
                self.labels['tool'].set_sensitive(tool_sensitive)
        else:
            self.labels['tool'].set_label(action)
            self.labels['tool'].set_sensitive(False)

        if self.ui_sel_tool == self.TOOL_GATE_BYPASS:
            self.labels['tool'].set_image(self.labels['select_bypass_img'])
        else:
            self.labels['tool'].set_image(self.labels['tool_img'])

    def update_encoder(self, data):
        scale = self.labels['scale']
        if 'desired_headroom' in data:
            desired_headroom = data['desired_headroom']
            if self.ui_runout_mark != desired_headroom:
                self.ui_runout_mark = desired_headroom
                scale.clear_marks()
                scale.add_mark(-desired_headroom, Gtk.PositionType.RIGHT, f"{desired_headroom}")
        if 'detection_length' in data:
            scale.set_range(-data['detection_length'], 0.)
        if 'min_headroom' in data:
            scale.set_fill_level(-data['min_headroom'])
        if 'headroom' in data:
            scale.set_value(-data['headroom'])
        if 'detection_mode' in data or 'enabled' in data:
            self.update_runout_mode()
        if 'encoder_pos' in data:
            flow_rate = self._printer.get_stat('mmu_encoder mmu_encoder')['flow_rate']
            self.update_movement(data['encoder_pos'], flow_rate)

    def update_runout_mode(self):
        detection_mode = self._printer.get_stat('mmu_encoder mmu_encoder')['detection_mode']
        enabled = self._printer.get_stat('mmu_encoder mmu_encoder')['enabled']
        detection_mode_str = "Disabled" if not enabled else "Clog (Auto)" if detection_mode == 2 else "Clog (Man)" if detection_mode == 1 else "Clog Off"
        self.labels['runout_frame'].set_label(f'{detection_mode_str}')
        self.labels['runout_frame'].set_sensitive(detection_mode and enabled)

    def update_movement(self, encoder_pos=None, flow_rate=None):
        mmu = self._printer.get_stat("mmu")
        if encoder_pos == None:
            encoder_pos = mmu['filament_position'] # Use real position instead
        encoder_pos=round(encoder_pos, 1)
        mmu_print_state = mmu['print_state']
        filament = mmu['filament']
        action = mmu['action']
        if mmu_print_state in ("complete", "error", "cancelled", "started"):
            pos_str = mmu_print_state.capitalize()
        elif action == "Idle":
            pos_str = (f"Filament: {encoder_pos}mm") if filament != "Unloaded" else "Filament: Unloaded"
            if flow_rate and self._printer.get_stat("print_stats")['state'] == "printing":
                pos_str += f"  ➥ {flow_rate}%"
        elif action == "Loading" or action == "Unloading":
            pos_str = (f"{action}: {encoder_pos}mm")
        else:
            pos_str = (f"{action}")
        self.labels['filament'].set_label(f"{pos_str}")

    def update_filament_status(self):
        if self.markup_filament:
            self.labels['status5'].set_markup(self.get_filament_text(markup=True, bold=self.bold_filament))
        else:
            self.labels['status5'].set_label(self.get_filament_text(bold=self.bold_filament))

        ts = self._check_sensor(self.ENDSTOP_TOOLHEAD)
        if ts != None:
            if ts == 1:
                self.labels['sensor'].get_style_context().remove_class("mmu_disabled_text")
                self.labels['sensor_state'].set_label("●  ")
                c_name = "green"
            elif ts == 0:
                self.labels['sensor'].get_style_context().remove_class("mmu_disabled_text")
                self.labels['sensor_state'].set_label("○  ")
                c_name = "red"
            else:
                self.labels['sensor'].get_style_context().add_class("mmu_disabled_text")
                self.labels['sensor_state'].set_label("◌  ")
                c_name = "grey"

            color = Gdk.RGBA()
            Gdk.RGBA.parse(color, c_name)
            self.labels['sensor_state'].override_color(Gtk.StateType.NORMAL, color)
        else:
            self.labels['sensor'].set_label("")
            self.labels['sensor_state'].set_label("")

    def update_status(self):
        text, multi_tool = self.get_status_text(markup=self.markup_status)
        for i in range(4):
            name = (f'status{i+1}')
            if self.markup_status:
                self.labels[name].set_markup(text[i])
            else:
                self.labels[name].set_label(text[i])

    # Dynamically update button sensitivity based on state
    def update_active_buttons(self):
        mmu = self._printer.get_stat("mmu")
        mmu_print_state = mmu['print_state']
        enabled = mmu['enabled']
        tool = mmu['tool']
        action = mmu['action']
        filament = mmu['filament']
        ui_state = []
        if enabled:
            if mmu_print_state in ("pause_locked", "paused"):
                ui_state.append(mmu_print_state)
            elif mmu_print_state in ("started",  "printing"):
                ui_state.append("printing")
                self._screen.clear_last_popup_message()
            else:
                ui_state.append("idle")
            if tool == self.TOOL_GATE_BYPASS:
                if filament == "Loaded":
                    ui_state.append("bypass_loaded")
                elif filament == "Unloaded":
                    ui_state.append("bypass_unloaded")
                else:
                    ui_state.append("bypass_unknown")
            elif tool >= 0:
                if filament == "Loaded":
                    ui_state.append("tool_loaded")
                elif filament == "Unloaded":
                    ui_state.append("tool_unloaded")
                else:
                    ui_state.append("tool_unknown")
            if not self._screen.have_last_popup_message():
                ui_state.append("no_message")

            if not "printing" in ui_state or not self._printer.get_stat('mmu_encoder mmu_encoder', None):
                self.labels['runout_layer'].set_current_page(0) # Manage recovery button
            else:
                self.labels['runout_layer'].set_current_page(1) # Clog display

            if ("paused" not in ui_state and "pause_locked" not in ui_state) or "no_messsage" in ui_state:
                self.labels['pause_layer'].set_current_page(0) # Pause button
            else:
                self.labels['pause_layer'].set_current_page(1) # Recall last error

            if action != "Idle" and action != "Unknown":
                ui_state.append("busy")
        else:
            ui_state.append("disabled")
            self.labels['runout_layer'].set_current_page(0) # Manage recovery button
            self.labels['t_increase'].set_sensitive(False)
            self.labels['t_decrease'].set_sensitive(False)

        logging.debug(f"mmu_main: ui_state={ui_state}")
        for label in self.btn_states['all']:
            sensitive = True
            for state in ui_state:
                if not label in self.btn_states[state]:
                    sensitive = False
                    break
            if sensitive:
                self.labels[label].set_sensitive(True)
            else:
                self.labels[label].set_sensitive(False)
            if label == "tool":
                tool_sensitive = sensitive
        self.update_tool_buttons(tool_sensitive)

    def get_rgb_color(self, gate_color):
        color = Gdk.RGBA()
        if not Gdk.RGBA.parse(color, gate_color.lower()):
            if not Gdk.RGBA.parse(color, '#' + gate_color):
                return ""
        rgb_color = "#{:02x}{:02x}{:02x}".format(int(color.red * 255), int(color.green * 255), int(color.blue * 255))
        return rgb_color

    def get_status_text(self, markup=False):
        mmu = self._printer.get_stat("mmu")
        gate_status = mmu['gate_status']
        tool_to_gate_map = mmu['ttg_map']
        gate_selected = mmu['gate']
        tool_selected = mmu['tool']
        gate_color = mmu['gate_color']
        num_gates = len(gate_status)

        multi_tool = False
        msg_gates = "Gates: "
        msg_tools = "Tools: "
        msg_avail = "Avail: "
        msg_selct = "Selct: "
        for g in range(num_gates):
            color = self.get_rgb_color(gate_color[g])
            filament_icon = ("█") if not markup or color == "" else (f"<span color='{color}'>█</span>")
            msg_gates += ("│#%d " % g)[:4]
            msg_avail += "│ %s " % (filament_icon if gate_status[g] in [self.GATE_AVAILABLE, self.GATE_AVAILABLE_FROM_BUFFER] else " " if gate_status[g] == self.GATE_EMPTY else "?")
            tool_str = ""
            prefix = ""
            for t in range(num_gates):
                if tool_to_gate_map[t] == g:
                    if len(prefix) > 0: multi_tool = True
                    tool_str += "%sT%d" % (prefix, t)
                    prefix = "+"
            if tool_str == "": tool_str = "   "
            msg_tools += ("│%s " % tool_str)[:4]
            if gate_selected == g:
                icon = filament_icon if gate_status[g] == self.GATE_AVAILABLE else filament_icon if gate_status[g] == self.GATE_AVAILABLE_FROM_BUFFER else " " if gate_status[g] == self.GATE_EMPTY else "?"
                msg_selct += ("╡ %s " % icon) if g != 0 else ("│ %s " % icon)
            else:
                msg_selct += "╞═══" if gate_selected != self.GATE_UNKNOWN and gate_selected == (g - 1) else "╧═══" if g != 0 else "╘═══"
        msg_gates += "│"
        msg_tools += "│"
        msg_avail += "│"
        msg_selct += "│" if gate_selected == (num_gates - 1) else "╛"
        msg = [msg_gates, msg_tools, msg_avail, msg_selct]
        return [msg_gates, msg_tools, msg_avail, msg_selct], multi_tool

    def get_filament_text(self, markup=False, bold=False):
        mmu = self._printer.get_stat("mmu")
        tool = mmu['tool']
        filament_pos = mmu['filament_pos']
        filament_direction = mmu['filament_direction']
        gate_color = mmu['gate_color']
        cs = self._printer.get_config_section("mmu")
        gate_homing_endstop = cs['gate_homing_endstop']

        arrow = "▶"
        line = "━"
        space = "┈"
        home  = "▉" if bold else "┫"
        gate  = "┤"
        gs = es = ts = '◯'
        past  = lambda pos: arrow if filament_pos >= pos else space
        homed = lambda pos, sensor: (arrow,arrow,sensor) if filament_pos > pos else (home,space,sensor) if filament_pos == pos else (space,space,sensor)
        nozz  = lambda pos: (arrow,arrow,arrow) if filament_pos == pos else (space,gate,' ')
        trig  = lambda name, sensor: re.sub(r'[a-zA-Z◯]', '●', name) if self._check_sensor(sensor) else name
        bseg = 4 + 2 * sum(not self._has_sensor(sensor) for sensor in [self.ENDSTOP_ENCODER, self.ENDSTOP_GATE, self.ENDSTOP_EXTRUDER, self.ENDSTOP_TOOLHEAD]) - (tool == self.TOOL_GATE_BYPASS)

        t_str   = ("T%s " % str(tool))[:3] if tool >= 0 else "BYPASS " if tool == self.TOOL_GATE_BYPASS else "T? "
        g_str   = "{0}{0}".format(past(self.FILAMENT_POS_UNLOADED))
        gs_str  = "{0}{2}{1}{1}{1}".format(*homed(self.FILAMENT_POS_HOMED_GATE, trig(gs, self.ENDSTOP_GATE))) if self._has_sensor(self.ENDSTOP_GATE) else ""
        en_str  = "En{0}{0}".format(past(self.FILAMENT_POS_IN_BOWDEN if gate_homing_endstop == self.ENDSTOP_GATE else self.FILAMENT_POS_START_BOWDEN)) if self._has_sensor(self.ENDSTOP_ENCODER) else ""
        bowden1 = "{0}".format(past(self.FILAMENT_POS_IN_BOWDEN)) * bseg
        bowden2 = "{0}".format(past(self.FILAMENT_POS_END_BOWDEN)) * bseg
        es_str  = "{0}{2}{1}{1}{1}".format(*homed(self.FILAMENT_POS_HOMED_ENTRY, trig(es, self.ENDSTOP_EXTRUDER))) if self._has_sensor(self.ENDSTOP_EXTRUDER) else ""
        ex_str  = "{0}{2}{1}{1}{1}".format(*homed(self.FILAMENT_POS_HOMED_EXTRUDER, "Ex"))
        ts_str  = "{0}{2}{1}{1}{1}".format(*homed(self.FILAMENT_POS_HOMED_TS, trig(ts, self.ENDSTOP_TOOLHEAD))) if self._has_sensor(self.ENDSTOP_TOOLHEAD) else ""
        nz_str  = "{0}{1}Nz{2}{2}".format(*nozz(self.FILAMENT_POS_LOADED))
        summary = " LOADED" if filament_pos == self.FILAMENT_POS_LOADED else " UNLOADED" if filament_pos == self.FILAMENT_POS_UNLOADED else " UNKNOWN" if filament_pos == self.FILAMENT_POS_UNKNOWN else " ▷▷▷" if filament_direction == self.DIRECTION_LOAD else " ◁◁◁" if filament_direction == self.DIRECTION_UNLOAD else ""

        visual = "".join((t_str, g_str, gs_str, en_str, bowden1, bowden2, es_str, ex_str, ts_str, nz_str, summary))

        last_home = visual.rfind(home)
        last_index = visual.rfind(arrow)
        visual = visual.replace(arrow, line)
        if last_index != -1 and (last_home == -1 or not bold):
                visual = visual[:last_index] + arrow + visual[last_index + 1:]

        if markup:
            if mmu['gate'] >= 0:
                color = self.get_rgb_color(gate_color[mmu['gate']])
                if color != "":
                    visual = self._add_markup(visual, color)

        if bold:
            visual = visual.replace(line, '█').replace(arrow, '▌')

        return visual

    def _add_markup(self, string, color):
        result = ""
        cc = "━●█"
        in_sequence = False
        for i, char in enumerate(string):
            if char in cc:
                if not in_sequence:
                    result += f"<span color='{color}'>"
                    in_sequence = True
                if i + 1 == len(string) or not string[i + 1] in cc:
                    result += char + f"</span>"
                    in_sequence = False
                else:
                    result += char
            else:
                result += char
        return result

    def _check_sensor(self, s):
        if s == self.ENDSTOP_ENCODER:
            encoder = self._printer.get_stat('mmu_encoder mmu_encoder', None)
            if encoder:
                return True
            else:
                return None

        sensor = self._printer.get_stat(f"filament_switch_sensor {s}_sensor")
        if sensor:
            if sensor['enabled']:
                if sensor['filament_detected']:
                    return 1
                else:
                    return 0
            return -1
        return None

    def _has_sensor(self, s):
        if s == self.ENDSTOP_ENCODER:
            return self._printer.get_stat('mmu_encoder mmu_encoder', None)

        sensor = self._printer.get_stat(f"filament_switch_sensor {s}_sensor")
        if sensor:
            return sensor['enabled']
        return False

