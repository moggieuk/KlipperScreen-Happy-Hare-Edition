# -*- coding: utf-8 -*-
# Happy Hare MMU Software
#
# Copyright (C) 2022-2026  moggieuk#6538 (discord)
#                          moggieuk@hotmail.com
#
# Implements MMU_TEST_CONFIG command
#
#
# (\_/)
# ( *,*)
# (")_(") Happy Hare Ready
#
# This file may be distributed under the terms of the GNU GPLv3 license.
# Happy Hare MMU Software
#
import logging, gi, re
import math, html, cairo

gi.require_version("Gtk", "3.0")

from gi.repository import Gtk, Gdk, GLib, Pango
from ks_includes.screen_panel import ScreenPanel
from panels.mmu_mixin import *

NOT_SET = -99


class Panel(ScreenPanel, MmuMixin):

    def __init__(self, screen, title):
        super().__init__(screen, title)

        # We need to keep track of just a little bit of UI state
        self.ui_runout_mark = 0.
        self.ui_sel_tool = NOT_SET
        self.min_tool = TOOL_GATE_BYPASS
        self._last_sync_feedback_bias_rounded = -9.9

        self._select_gate_timer = None
        self._select_gate_delay_ms = 700

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
            'unit_label': Gtk.Label('Unit0'),
            'select_bypass_img': self._gtk.Image('mmu_select_bypass'), # Alternative for tool
            'load_bypass_img': self._gtk.Image('mmu_load_bypass'),     # Alternative for picker
            'unload_bypass_img': self._gtk.Image('mmu_unload_bypass'), # Alternative for unload/eject
            'eject_img': self._gtk.Image('mmu_eject'),                 # Alternative for unload button to fully eject
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
        self.labels['unit_label'].set_xalign(1)
        self.labels["unit_label"].get_style_context().add_class("mmu_unit_text")

        # In print Encoder guage ---------
        encoder_gauge = EncoderDialGauge()
        self.labels['encoder_gauge'] = encoder_gauge

        encoder_frame = Gtk.Frame()
        self.labels['encoder_frame'] = encoder_frame
        encoder_frame.set_label("FlowGuard")
        encoder_frame.set_label_align(0.5, 0)
        encoder_frame.add(encoder_gauge)

        # In print sync-feedback flowguard  guage ---------
        flowguard_gauge = FlowGuardDialGauge()
        self.labels['flowguard_gauge'] = flowguard_gauge

        flowguard_frame = Gtk.Frame()
        self.labels['flowguard_frame'] = flowguard_frame
        flowguard_frame.set_label("FlowGuard")
        flowguard_frame.set_label_align(0.5, 0)
        flowguard_frame.add(flowguard_gauge)

        # MMU Manage screen ---------
        manage_grid = Gtk.Grid()
        manage_grid.set_column_homogeneous(True)

# No need for this now - status self scales
#        mmu = self._printer.get_stat("mmu")
#        num_gates = len(mmu['gate_status'])
#        if num_gates > 9:
#            manage_grid.attach(Gtk.Label(),           0, 0, 1, 3)
#            manage_grid.attach(self.labels['manage'], 1, 0, 2, 3)
#        else:
#            manage_grid.attach(self.labels['manage'], 0, 0, 3, 3)
        manage_grid.attach(self.labels['manage'], 0, 0, 3, 3)

        # Notebook layers for three possible uses of top right corner ----------
        notebook_corner = Gtk.Notebook()
        self.labels['notebook_corner'] = notebook_corner
        notebook_corner.set_show_tabs(False)
        notebook_corner.insert_page(manage_grid, None, 0)
        notebook_corner.insert_page(self._clickable_page(flowguard_frame), None, 1)
        notebook_corner.insert_page(self._clickable_page(encoder_frame), None, 2)
        notebook_corner.set_current_page(0)

        # TextView has problems in this use case so use 5 separate labels... Simple!
        status_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        for i in range(5):
            name = (f'status{i+1}')
            label = Gtk.Label()
            self.labels[name] = label
            label.get_style_context().add_class("mmu_unicode_mono")
            label.set_xalign(0)
            if i < 4:
                label.get_style_context().add_class("mmu_status")
                status_box.pack_start(label, False, True, 0)
            else:
                label.get_style_context().add_class("mmu_status_filament")

        top_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        top_box.pack_start(self.labels['tool_icon'], False, True, 0)
        top_box.pack_start(self.labels['tool_label'], True, True, 0)
        top_box.pack_start(self.labels['filament'], True, True, 0)
        top_box.pack_start(self.labels['unit_label'], False, True, 12)

        pause_layer = Gtk.Notebook()
        self.labels['pause_layer'] = pause_layer
        pause_layer.set_show_tabs(False)
        pause_layer.insert_page(self.labels['pause'], None, 0)
        pause_layer.insert_page(self.labels['message'], None, 1)

        top_grid = Gtk.Grid()
        top_grid.set_vexpand(False)
        top_grid.set_column_homogeneous(True)
        top_grid.attach(top_box,                0, 0,  9, 1)
        top_grid.attach(notebook_corner,        9, 0,  3, 3)
        top_grid.attach(status_box,             0, 1, 10, 1) # Should be 9, not 10 (but this prevents screen expansion)
        top_grid.attach(self.labels['status5'], 0, 2, 12, 1) # Allows filament line line to extend

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
        main_grid.attach(self.labels['unload'],       8, 0, 2, 1)
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
        self.ui_sel_tool = NOT_SET
        self.init_tool_value()
        self.config_update()


    def _next_notebook_corner_page(self, widget, event):
        notebook = self.labels["notebook_corner"]
        if self.has_buffer() and self.has_encoder():
            # Toggle flowguard monitor dials (unlikely user will have both)
            page = notebook.get_current_page()
            notebook.set_current_page(2 if page == 1 else 1)
        return True


    def _clickable_page(self, child):
        event_box = Gtk.EventBox()
        event_box.add(child)
        event_box.connect("button-press-event", self._next_notebook_corner_page)
        return event_box


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
        if action == "notify_status_update" and data is not None:
            filament_status_updated = False

            try:
                # v3 encoder
                if self.has_encoder() and 'mmu_encoder mmu_encoder' in data: # There is only one mmu_encoder on v3
                    ee_data = data['mmu_encoder mmu_encoder']
                    self.update_encoder(ee_data)

                # v4 contains everything required in 'printer.mmu'
                if 'mmu' in data:
                    mmu = self._printer.get_stat("mmu")
                    e_data = data['mmu']

                    # v4 encoder
                    if self.has_encoder() and 'encoder' in e_data:
                        self.update_encoder()

                    # v4 buffer
                    if (
                        not filament_status_updated
                        and self.has_buffer()
                    ):
                        if 'sync_feedback_state' in e_data:
                            self.update_filament_status()
                            filament_status_updated = True
                        elif 'sync_feedback_bias_modelled' in e_data and self._should_update_proportional():
                            self.update_filament_status()
                            filament_status_updated = True

                    # Flowguard
                    if (
                        self.has_buffer()
                        and any(
                            key in e_data
                            for key in ('sync_feedback_flow_rate', 'flowguard')
                        )
                    ):
                        self.update_flowguard()

                    # Tool, gate or maps
                    if any(
                        key in e_data
                        for key in ('tool', 'gate', 'ttg_map', 'gate_status', 'gate_color')
                    ):
                        self.update_status()

                    if (
                        not filament_status_updated
                        or any(
                            key in e_data
                            for key in ('tool', 'filament_pos', 'filament_direction', 'sensors')
                        )
                    ):
                        self.update_filament_status()
                        filament_status_updated = True

                    if any(
                        key in e_data
                        for key in ('tool', 'next_tool', 'sync_drive', 'filament')
                    ):
                        self.update_tool()

                    if 'enabled' in e_data:
                        self.update_enabled()

                    if any(
                        key in e_data
                        for key in ('action', 'print_state')
                    ):
                        ee_data = self.get_encoder_data()
                        if ee_data:
                            self.update_movement(encoder_position=ee_data['encoder_pos'])
                        else:
                            self.update_movement()

                    if 'print_state' in e_data:
                        self.update_active_buttons()

                    self.update_active_buttons()

            except KeyError as ke:
                # Almost certainly a version mismatch of Happy Hare on the printer
                msg = "You are probably trying to connect to an incompatible"
                msg += "\nversion of Happy Hare on your printer. Ensure Happy Hare"
                msg += "\nis up-to-date, re-run Happy-Hare/install.sh on the"
                msg += "\nprinter, then make sure you restart Klipper."
                msg += "\n\nI'll bet this will work out for you :-)"
                self._screen.show_popup_message(msg, 3, save=True)
                logging.info("Happy Hare: KeyError: %s" % str(ke))


    def init_tool_value(self):
        mmu = self._printer.get_stat("mmu")
        if self.ui_sel_tool == NOT_SET and mmu['tool'] != TOOL_GATE_UNKNOWN:
            self.ui_sel_tool = mmu['tool']
        else:
            self.ui_sel_tool = 0


    def _mm_format(self, w, v):
        return f"{-v:.1f}mm"


    # Prevent unecessary updates
    def _should_update_proportional(self):
        mmu = self._printer.get_stat("mmu")
        value = mmu.get("sync_feedback_bias_modelled")
        return round(value, 1) != self._last_sync_feedback_bias_rounded


    def select_check_gates(self, widget):
        self._screen._confirm_send_action(
            None,
            "Check filament availabily in all MMU gates?\n\nAre you sure you want to continue?",
            "printer.gcode.script",
            {'script': "MMU_CHECK_GATE ALL=1 QUIET=1"}
        )


    def _schedule_gate_select(self):
        if self._select_gate_timer is not None:
            GLib.source_remove(self._select_gate_timer)

        self._select_gate_timer = GLib.timeout_add(
            self._select_gate_delay_ms,
            self.select_pending_gate,
        )


    def select_pending_gate(self):
        self._select_gate_timer = None

        mmu = self._printer.get_stat("mmu")
        if mmu['filament'] == "Unloaded":
            if self.ui_sel_tool == TOOL_GATE_BYPASS:
                self._screen._ws.api.gcode_script("MMU_SELECT_BYPASS")
            elif self.ui_sel_tool >= 0:
                self._screen._ws.api.gcode_script(f"MMU_SELECT TOOL={self.ui_sel_tool} QUIET=1")
        else:
            # At least include visual includes gate of interest
            self.update_status(self.ui_sel_tool)

        return False


    def select_tool(self, widget, param=0):
        mmu = self._printer.get_stat("mmu")
        num_gates = len(mmu['gate_status'])
        tool = mmu['tool']

        if param < 0 and self.ui_sel_tool > self.min_tool:
            self.ui_sel_tool -= 1
            if self.ui_sel_tool == TOOL_GATE_UNKNOWN:
                self.ui_sel_tool = TOOL_GATE_BYPASS

            self.update_tool_buttons()
            self._schedule_gate_select()
            return

        elif param > 0 and self.ui_sel_tool < num_gates - 1:
            self.ui_sel_tool += 1
            if self.ui_sel_tool == TOOL_GATE_UNKNOWN:
                self.ui_sel_tool = 0

            self.update_tool_buttons()
            self._schedule_gate_select()
            return

        elif param == 0:
            if self._select_gate_timer is not None:
                GLib.source_remove(self._select_gate_timer)
                self._select_gate_timer = None

            if self.ui_sel_tool == TOOL_GATE_BYPASS:
                self._screen._ws.api.gcode_script("MMU_SELECT_BYPASS")
            elif self.ui_sel_tool != tool or mmu['filament'] != "Loaded":
                self._screen._ws.api.gcode_script(f"MMU_CHANGE_TOOL TOOL={self.ui_sel_tool} QUIET=1")

        self.update_tool_buttons()


    def select_unload_eject(self, widget):
        mmu = self._printer.get_stat("mmu")
        filament = mmu['filament']
        if filament != "Unloaded":
            self._screen._ws.api.gcode_script(f"MMU_UNLOAD")
        else:
            self._screen._ws.api.gcode_script(f"MMU_EJECT")


    def select_picker(self, widget):
        # This is a multipurpose button to select subpanel or load bypass
        mmu = self._printer.get_stat("mmu")
        tool = mmu['tool']
        if tool == TOOL_GATE_BYPASS:
            self._screen._ws.api.gcode_script(f"MMU_LOAD EXTRUDER_ONLY=1")
        else:
            self._screen.show_panel('mmu_picker', 'MMU Tool Picker')


    def select_pause(self, widget):
        self._screen._ws.api.gcode_script(f"MMU_PAUSE FORCE_IN_PRINT=1")


    def select_message(self, widget):
        last_toolchange = self._printer.get_stat('mmu', 'last_toolchange')
        self._screen.show_last_popup_message(f"Last Toolchange: {last_toolchange}")


    def select_resume(self, widget):
        self._screen._ws.api.gcode_script(f"RESUME")


    def select_unlock(self, widget):
        self._screen._ws.api.gcode_script(f"MMU_UNLOCK")


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
        if next_tool != TOOL_GATE_UNKNOWN:
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
        if tool == TOOL_GATE_BYPASS:
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
        if (tool == TOOL_GATE_BYPASS and filament == "Loaded") or not tool_sensitive:
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
            elif self.ui_sel_tool == TOOL_GATE_BYPASS:
                self.labels['tool'].set_label(f"Bypass")
                self.labels['tool'].set_sensitive(tool_sensitive)
            else:
                self.labels['tool'].set_label(f"n/a")
                self.labels['tool'].set_sensitive(tool_sensitive)
        else:
            self.labels['tool'].set_label(action[:11])
            self.labels['tool'].set_sensitive(False)

        if self.ui_sel_tool == TOOL_GATE_BYPASS:
            self.labels['tool'].set_image(self.labels['select_bypass_img'])
        else:
            self.labels['tool'].set_image(self.labels['tool_img'])


    def update_flowguard(self):
        if self._printer.get_stat("print_stats")['state'] != "printing":
            return

        mmu = self._printer.get_stat("mmu")
        data = mmu['flowguard']
        flowrate = mmu["sync_feedback_flow_rate"]

        gauge = self.labels['flowguard_gauge']
        gauge.update(data, flowrate)

        # Update frame heading
        enabled = data['enabled']
        active = data['active']
        if not enabled:
            mode_str = "FlowGuard"
        elif active:
            mode_str = "FlowGuard Active"
        else:
            mode_str = "FlowGuard Inactive"
        self.labels['flowguard_frame'].set_label(f'{mode_str}')
        self.labels['flowguard_frame'].set_sensitive(enabled)


    def update_encoder(self, data=None):
        if self._printer.get_stat("print_stats")['state'] != "printing":
            return

        mmu = self._printer.get_stat("mmu")
        data = data or mmu['encoder']
        gauge = self.labels['encoder_gauge']
        gauge.update(data)

        # Update frame heading
        detection_mode = data['detection_mode']
        enabled = data['enabled']
        if detection_mode == 2:
            mode_str = "Encoder (Clog Auto)"
        elif detection_mode == 1:
            mode_str = "Encoder (Clog Man)"
        else:
            mode_str = "Encoder Off"
        self.labels['encoder_frame'].set_label(f'{mode_str}')
        self.labels['encoder_frame'].set_sensitive(detection_mode and enabled)

        # Encoder pos is displayed in filament position status
        self.update_movement(data['encoder_pos'])


    def update_movement(self, encoder_position=None):
        mmu = self._printer.get_stat("mmu")
        print_state = mmu["print_state"]
        action = mmu["action"]
        filament = mmu["filament"]

        filament_position = mmu["filament_position"]
        filament_text = f"{filament_position:.1f}mm"
        encoder_text = (
            f" (e:{int(encoder_position)}mm)"
            if encoder_position is not None
            else ""
        )

        if print_state in {"complete", "error", "cancelled", "started"}:
            label = print_state.capitalize()
        elif action == "Idle":
            label = (
                "Filament: Unloaded"
                if filament == "Unloaded"
                else f"Filament: {filament_text}{encoder_text}"
            )
        elif action in {"Loading", "Unloading"}:
            label = f"{action}: {filament_text}"
        else:
            label = action

        self.labels["filament"].set_label(label)


    def update_filament_status(self):
        if self.markup_filament:
            self.labels['status5'].set_markup(self.get_filament_text(markup=True, bold=self.bold_filament))
        else:
            self.labels['status5'].set_label(self.get_filament_text(bold=self.bold_filament))


    def update_status(self, show_gate=None):
        text, current_unit_name, multi_tool = self.get_status_text(show_gate=show_gate, markup=self.markup_status)
        for i in range(4):
            name = (f'status{i+1}')
            if self.markup_status:
                self.labels[name].set_markup(text[i])
            else:
                self.labels[name].set_label(text[i])

        self.labels['unit_label'].set_label(current_unit_name)


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
            if tool == TOOL_GATE_BYPASS:
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

            page = 0 # Manage recovery button
            if "printing" in ui_state:
                page = self.labels['notebook_corner'].get_current_page()
                if page == 0 and self.has_buffer():
                    page = 1 # Flowguard display
                elif page == 0 and self.has_encoder():
                    page = 2 # Encoder display
            self.labels['notebook_corner'].set_current_page(page)

            if ("paused" not in ui_state and "pause_locked" not in ui_state) or "no_message" in ui_state:
                self.labels['pause_layer'].set_current_page(0) # Pause button
            else:
                self.labels['pause_layer'].set_current_page(1) # Recall last error

            if action != "Idle" and action != "Unknown":
                ui_state.append("busy")
        else:
            ui_state.append("disabled")
            self.labels['notebook_corner'].set_current_page(0) # Manage recovery button
            self.labels['t_increase'].set_sensitive(False)
            self.labels['t_decrease'].set_sensitive(False)

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


    def get_status_text(self, show_gate=None, markup=False):
        mmu = self._printer.get_stat("mmu")
        gate_status = mmu['gate_status']
        tool_to_gate_map = mmu['ttg_map']
        gate_selected = mmu['gate']
        tool_selected = mmu['tool']
        gate_color = mmu['gate_color']

        unit_selected = mmu.get("unit")
        display_limit = 13 # Max number of gate "columns" to display (includes bypass and gaps)

        if unit_selected is not None:
            mmu_machine = self._printer.get_stat("mmu_machine")

            gate_indices = []
            bypass_found = False

            for unit_index in range(mmu_machine["num_units"]):
                if gate_indices:
                    gate_indices.append(None) # Unit separator

                unit = mmu_machine[f"unit_{unit_index}"]
                first_gate = unit["first_gate"]
                num_gates = unit["num_gates"]

                gate_indices.extend(
                    range(first_gate, first_gate + num_gates)
                )

                if unit.get("has_bypass", False):
                    gate_indices.append(TOOL_GATE_BYPASS)
                    bypass_found = True

                if unit_index == unit_selected:
                    current_unit_name = unit.get("display_name") or unit.get("name")

            if not bypass_found:
                gate_indices.append(None)
                gate_indices.append(TOOL_GATE_BYPASS)

        else:
            # Early v3 single fixed unit
            unit_selected = 0
            first_gate = 0
            num_gates = len(gate_status)
            current_unit_name = "Unit0"

        # Trim displayed gates to the display limit
        current_unit_name = current_unit_name[:1].upper() + current_unit_name[1:]

        if show_gate is None:
            show_gate = gate_selected

        display_offset = 0
        if len(gate_indices) > display_limit:
            try:
                selected_idx = gate_indices.index(show_gate)
            except ValueError:
                display_offset = 0
                display_gate_indices = gate_indices[:display_limit]
            else:
                display_offset = max(0, selected_idx - display_limit // 2)
                display_offset = min(display_offset, len(gate_indices) - display_limit)
                display_gate_indices = gate_indices[display_offset:display_offset + display_limit]
        else:
            display_gate_indices = gate_indices

        multi_tool = False
        msg_gates = ""
        msg_tools = ""
        msg_avail = ""
        msg_selct = ""

        if len(gate_indices) <= 10:
            msg_gates += "Gates "
            msg_tools += "Tools "
            msg_avail += "Avail "
            msg_selct += "Selct "

        for i, g in enumerate(display_gate_indices):
            full_idx = display_offset + i
            prev_g = gate_indices[full_idx - 1] if full_idx > 0 else None
            next_g = gate_indices[full_idx + 1] if full_idx + 1 < len(gate_indices) else None
            at_unit_start = prev_g is None
            at_unit_end = next_g is None

            if g is None:
                # Unit separator: 3-character spacing
                msg_gates += "│  "
                msg_tools += "│  "
                msg_avail += "│  "
                msg_selct += "│  " if gate_selected == prev_g else "╛  "
                continue

            if g == TOOL_GATE_BYPASS:
                msg_gates += "│Byp"
                msg_tools += "│ - "
                msg_avail += "│   "

            else:
                # Regular gate
                color = self.get_rgb_color(gate_color[g])
                filament_icon = ("█") if not markup or color == "" else (f"<span color='{color}'>█</span>")
                msg_gates += ("│#%d " % g)[:4]

                if gate_status[g] in (GATE_AVAILABLE, GATE_AVAILABLE_FROM_BUFFER):
                    avail = filament_icon
                elif gate_status[g] == GATE_EMPTY:
                    avail = " "
                else:
                    avail = "?"
                msg_avail += f"│ {avail} "

                # Find tool associated with gate
                tool_str = ""
                prefix = ""
                for t in range(num_gates):
                    if tool_to_gate_map[t] == g:
                        if len(prefix) > 0: multi_tool = True
                        tool_str += "%sT%d" % (prefix, t)
                        prefix = "+"
                if tool_str == "": tool_str = "   "
                msg_tools += ("│%s " % tool_str)[:4]

            # Selected ("open") gate
            if gate_selected == g:
                icon = (
                    " "
                    if g == TOOL_GATE_BYPASS
                    else filament_icon
                    if gate_status[g] in (GATE_AVAILABLE, GATE_AVAILABLE_FROM_BUFFER)
                    else " "
                    if gate_status[g] == GATE_EMPTY
                    else "?"
                )
                msg_selct += ("╡ %s " % icon) if not (at_unit_start or gate_selected == prev_g) else ("│ %s " % icon)
            else:
                msg_selct += (
                    "╞═══"
                    if gate_selected != GATE_UNKNOWN and gate_selected == prev_g
                    else "╘═══"
                    if at_unit_start
                    else "╧═══"
                )

        if g is not None:
            msg_gates += "│"
            msg_tools += "│"
            msg_avail += "│"
            msg_selct += "│" if gate_selected == g else "╛" if at_unit_end else "╧"

        n = display_limit * 4 + 1
        return [msg_gates[:n], msg_tools[:n], msg_avail[:n], msg_selct[:n]], current_unit_name, multi_tool


    def get_filament_text(self, markup=False, bold=False):
        mmu = self._printer.get_stat("mmu")
        tool = mmu["tool"]
        pos = mmu["filament_pos"]
        direction = mmu["filament_direction"]
        gate = mmu["gate"]
        gate_color = mmu["gate_color"]

        unit = self.get_mmu_unit(gate)
        cs = None
        if unit is not None:
            unit_name = unit['name']
            cs = self._printer.get_config_section(f"mmu_unit_parameters {unit_name}")
        if not cs:
            # V3...
            cs = self._printer.get_config_section("mmu")
        gate_homing_endstop = cs.get("gate_homing_endstop")
        if gate_homing_endstop is None:
            raise KeyError("gate_homing_endstop not found in mmu_parameters or mmu config")

        space = "┈"
        gate_mark = "┤"
        empty_sensor = "◯"
        trig_sensor = "◉"

        if bold:
            home, line, arrow = "▌", "█", "▌"
        else:
            home, line, arrow = "┫", "━", "▶"

        # Helpers --------

        def past(target_pos):
            return arrow if pos >= target_pos else space

        def sensor_label(sensor, label=""):
            marker = trig_sensor if self.check_sensor(sensor) else empty_sensor
            return marker + label

        def homed_segment(target_pos, label):
            if pos > target_pos:
                return arrow + label + arrow
            if pos == target_pos:
                return home + label + space
            return space + label + space

        def pad(target_pos, length):
            if pos > target_pos:
                return arrow * length
            if pos == target_pos:
                left = length - length // 2
                right = length // 2
                return arrow * left + space * right
            return space * length

        def optional_sensor(sensor, target_pos, width=3):
            if self.has_sensor(sensor):
                return homed_segment(target_pos, sensor_label(sensor))
            return pad(target_pos, width)

        def nozzle_segment():
            if pos >= FILAMENT_POS_LOADED:
                return arrow + home + "Nz" + arrow * 2
            return space + gate_mark + "Nz"

        def buffer_segment():
            t_sensor = self.check_sensor(SENSOR_TENSION)
            c_sensor = self.check_sensor(SENSOR_COMPRESSION)
            sf_state = mmu.get("sync_feedback_state")
            sf_value = mmu.get("sync_feedback_bias_modelled")

            sf_char = "?"
            if sf_state == "disabled":
                sf_char = "x"
            if sf_state == "inactive":
                sf_char = " "
            if sf_state == "compressed":
                sf_char = "C"
            if sf_state == "tension":
                return "T"
            if sf_state == "neutral":
                if self.has_sensor(SENSOR_PROPORTIONAL) and sf_value is not None:
                    self._last_sync_feedback_bias_rounded = round(value, 1)
                    return f"[{f'{value:.1f}'.center(5)}]"
                sf_char = "N"

            if c_sensor:
                return f"[ ▷{sf_char}◁ ]"
            elif t_sensor:
                return f" [◁{sf_char}▷] "
            return f" [ {sf_char} ] "

        # Impl --------

        if tool >= 0:
            tool_text = f"T{tool} "[:3]
        elif tool == TOOL_GATE_BYPASS:
            tool_text = "BYPASS "
        else:
            tool_text = "T? "

        bowden_length = max(1, 12 - len(tool_text))
        bowden_half = bowden_length // 2

        encoder_ref_pos = (
            FILAMENT_POS_START_BOWDEN
            if gate_homing_endstop == SENSOR_ENCODER
            else FILAMENT_POS_IN_BOWDEN
        )

        parts = [
            tool_text,
            past(FILAMENT_POS_UNLOADED) * 2,

            # This represents mmu_exit or mmu_shared_exit (whichever is used for gate homing)
            optional_sensor(gate_homing_endstop, FILAMENT_POS_HOMED_GATE),

            (
                "En" + past(encoder_ref_pos) * 2
                if self.has_encoder()
                else pad(encoder_ref_pos, 4)
            ),

            past(FILAMENT_POS_IN_BOWDEN) * bowden_half,

            (
                buffer_segment()
                if self.has_buffer()
                else pad(FILAMENT_POS_IN_BOWDEN, 7)
            ),

            past(FILAMENT_POS_END_BOWDEN) * bowden_half,

            optional_sensor(SENSOR_EXTRUDER_ENTRY, FILAMENT_POS_HOMED_ENTRY),

            homed_segment(FILAMENT_POS_HOMED_EXTRUDER, "Ex"),
            past(FILAMENT_POS_EXTRUDER_ENTRY),

            optional_sensor(SENSOR_TOOLHEAD, FILAMENT_POS_HOMED_TS),

            past(FILAMENT_POS_IN_EXTRUDER),
            nozzle_segment(),
        ]

        if pos == FILAMENT_POS_LOADED:
            parts.append(" LOADED")
        elif pos == FILAMENT_POS_UNLOADED:
            parts.append(" UNLOADED")
        elif pos == FILAMENT_POS_UNKNOWN:
            parts.append(" UNKNOWN")
        elif direction == DIRECTION_LOAD:
            parts.append(" ▷▷▷")
        elif direction == DIRECTION_UNLOAD:
            parts.append(" ◁◁◁")

        visual = "".join(parts)

        last_home = visual.rfind(home)
        last_arrow = visual.rfind(arrow)

        visual = visual.replace(arrow, line)

        if last_arrow != -1 and (last_home == -1 or not bold):
            visual = visual[:last_arrow] + arrow + visual[last_arrow + 1:]

        if markup and gate >= 0:
            color = self.get_rgb_color(gate_color[gate])
            if color:
                visual = self._add_color_markup(visual, color, line)

        return visual


    def _add_color_markup(self, text, color, *chars):
        chars = set(chars)

        result = []
        in_markup = False

        for ch in text:
            should_markup = ch in chars

            if should_markup and not in_markup:
                result.append(f"<span color='{color}'>")
                in_markup = True
            elif not should_markup and in_markup:
                result.append("</span>")
                in_markup = False

            result.append(ch)

        if in_markup:
            result.append("</span>")

        return "".join(result)



# -------------------------------------------------------------------------------------------
# ENCODER DIAL GUAGE
# -------------------------------------------------------------------------------------------

class EncoderDialGauge(Gtk.DrawingArea):
    def __init__(self):
        super().__init__()

        self.value = 0.0
        self.max_value = 30.0
        self.desired_headroom = 10.0
        self.min_headroom = 30.0
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
        self._draw_text_centered(cr, "Tangle", x + 2, y + 24)

        x, y = self._point_on_arc(cx, cy, r, 1.0)
        self._draw_text_centered(cr, "Clog", x - 2, y + 24)

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
