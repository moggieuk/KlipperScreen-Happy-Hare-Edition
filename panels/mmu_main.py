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
from panels.mmu_gauges import *

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

        # In print Encoder gauge
        encoder_gauge = EncoderDialGauge()
        self.labels['encoder_gauge'] = encoder_gauge
        encoder_frame = Gtk.Frame()
        self.labels['encoder_frame'] = encoder_frame
        encoder_frame.set_label("FlowGuard")
        encoder_frame.set_label_align(0.5, 0)
        encoder_frame.add(encoder_gauge)

        # In print sync-feedback flowguard gauge
        flowguard_gauge = FlowGuardDialGauge()
        self.labels['flowguard_gauge'] = flowguard_gauge
        flowguard_frame = Gtk.Frame()
        self.labels['flowguard_frame'] = flowguard_frame
        flowguard_frame.set_label("FlowGuard")
        flowguard_frame.set_label_align(0.5, 0)
        flowguard_frame.add(flowguard_gauge)

        # Notebook corner "layers" ---------------------------------
        notebook_corner = Gtk.Notebook()
        self.labels['notebook_corner'] = notebook_corner
        notebook_corner.set_show_tabs(False)
        notebook_corner.insert_page(self.labels['manage'], None, 0)
        notebook_corner.insert_page(self._clickable_page(flowguard_frame), None, 1)
        notebook_corner.insert_page(self._clickable_page(encoder_frame), None, 2)
        notebook_corner.set_current_page(0)

        # Pause button "layers" ------------------------------------
        pause_layer = Gtk.Notebook()
        self.labels['pause_layer'] = pause_layer
        pause_layer.set_show_tabs(False)
        pause_layer.insert_page(self.labels['pause'], None, 0)
        pause_layer.insert_page(self.labels['message'], None, 1)


        # Assemble "classic" view --------------------------------------

        self.classic_status = False
        if self.classic_status:

            # Top line status ------------------------------------------
            top_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            top_box.pack_start(self.labels['tool_icon'], False, True, 0)
            top_box.pack_start(self.labels['tool_label'], True, True, 0)
            top_box.pack_start(self.labels['filament'], True, True, 0)
            top_box.pack_start(self.labels['unit_label'], False, True, 12)


            # Main textual status area ---------------------------------

            status_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
            # TextView has problems in this use case so use 5 separate labels...
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
                    self.labels['filament_pos'] = label # Alias for status5
                    label.get_style_context().add_class("mmu_status_filament")


            # Assemble upper section of panel ---------------------------

            top_grid = Gtk.Grid()
            top_grid.set_vexpand(False)
            top_grid.set_column_homogeneous(True)

            top_grid.attach(top_box,                      0, 0,  9, 1)
            top_grid.attach(notebook_corner,              9, 0,  3, 3)
            top_grid.attach(status_box,                   0, 1, 10, 1) # Should be 9, not 10 (but this prevents screen expansion)
            top_grid.attach(self.labels['filament_pos'],  0, 2, 12, 1) # Allows filament line line to extend

            # Assemble the two primary button rows ------------
            tool_grid = Gtk.Grid()
            tool_grid.set_column_homogeneous(False)
            tool_grid.attach(self.labels['t_decrease'],   0, 0, 1, 1)
            tool_grid.attach(self.labels['tool'],         1, 0, 1, 1)
            tool_grid.attach(self.labels['t_increase'],   2, 0, 1, 1)

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


        else:
            l = self.labels
            l['spool_tray'] = MmuSpoolTray(self._printer)

            l['filament_pos'] = label = Gtk.Label()
            label.get_style_context().add_class("mmu_unicode_mono")
            label.get_style_context().add_class("mmu_status_filament")
            label.set_xalign(0)

            'unload': self._gtk.Button('mmu_unload', 'Unload', 'color4'), # Doubles as eject button

            main_grid = Gtk.Grid()
            main_grid.set_vexpand(True)
            #main_grid.set_row_homogeneous(True) # PAUL
            main_grid.set_column_homogeneous(True)

            # PAUL debug vvv
            dframe = Gtk.Frame()
            css = b"""
            .debug-cell {
                background-color: rgba(255, 255, 0, 0.35);
                border: 1px solid red;
            }
            """
            provider = Gtk.CssProvider()
            provider.load_from_data(css)
            Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
            dframe.get_style_context().add_class("debug-cell")
            # PAUL debug ^^^

            dframe.add(l['spool_tray'])
            main_grid.attach(dframe,               0,  0,  9,  5)
            main_grid.attach(l['notebook_corner'], 9,  0,  3,  5)
            main_grid.attach(l['tool_label'],      0,  5,  1,  1)
            main_grid.attach(l['filament_pos'],    1,  5,  10, 1)
            main_grid.attach(l['tool_icon'],      11,  5,  1,  1)
 
            main_grid.attach(l['pause_layer'],     0,  6,  3,  2)
            main_grid.attach(l['unlock'],          3,  6,  2,  2)
            main_grid.attach(l['resume'],          5,  6,  2,  2)
            main_grid.attach(l['extrude'],         7,  6,  2,  2)
            main_grid.attach(l['more'],            9,  6,  3,  2)

            scroll = self._gtk.ScrolledWindow()
            scroll.add(main_grid)

            # This creates a "click shield" to allow catching of all clicks when
            # popup menu is active. Without this Gtk tries to handle close and
            # doesn't propogate to the spool_tray preventing quick selection of spools
            overlay = Gtk.Overlay()
            overlay.add(scroll)

            spool_click_shield = Gtk.EventBox()
            spool_click_shield.set_visible_window(False)
            spool_click_shield.set_hexpand(True)
            spool_click_shield.set_vexpand(True)
            spool_click_shield.hide()
            overlay.add_overlay(spool_click_shield)
            overlay.set_overlay_pass_through(spool_click_shield, True)
            l['spool_tray'].set_click_shield(spool_click_shield, overlay)

            self.content.add(overlay)


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

            except KeyError:
                # Almost certainly a version mismatch of Happy Hare on the printer
                msg = "You are probably trying to connect to an incompatible"
                msg += "\nversion of Happy Hare on your printer. Ensure Happy Hare"
                msg += "\nis up-to-date, re-run Happy-Hare/install.sh on the"
                msg += "\nprinter, then make sure you restart Klipper."
                msg += "\n\nI'll bet this will work out for you :-)"
                self._screen.show_popup_message(msg, 3, save=True)
                logging.exception("Happy Hare KeyError")


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
        if self.classic_status:
            for i in range(5):
                name = (f'status{i+1}')
                if enabled:
                    self.labels[name].get_style_context().remove_class("mmu_disabled_text")
                else:
                    self.labels[name].get_style_context().add_class("mmu_disabled_text")
        else:
            pass # PAUL todo


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
            self.labels['filament_pos'].set_markup(self.get_filament_text(markup=True, bold=self.bold_filament))
        else:
            self.labels['filament_pos'].set_label(self.get_filament_text(bold=self.bold_filament))


    def update_status(self, show_gate=None):
        if self.classic_status:
            text, current_unit_name, multi_tool = self.get_status_text(show_gate=show_gate, markup=self.markup_status)
            for i in range(4):
                name = (f'status{i+1}')
                if self.markup_status:
                    self.labels[name].set_markup(text[i])
                else:
                    self.labels[name].set_label(text[i])

            self.labels['unit_label'].set_label(current_unit_name)
        else:
            self.labels['spool_tray'].refresh()


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
                color = MmuUtils.get_rgb_color(gate_color[g])
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

        return [msg_gates, msg_tools, msg_avail, msg_selct], current_unit_name, multi_tool


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
            color = MmuUtils.get_rgb_color(gate_color[gate])
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
# MMU SPOOL TRAY WIDGET
# -------------------------------------------------------------------------------------------

class MmuSpoolTray(Gtk.DrawingArea):

    def __init__(self, printer):
        super().__init__()
        self._printer = printer
        self._items = None
        self._spool_cache = {}

        # Pop-up menus
        self._hitboxes = []  # list of (gate, x, y, w, h)
        self._popover = None
        self._popover_timeout_id = None
        self._click_shield = None

        # Drag scrolling
        self._scroll_x = 0
        self._drag_active = False
        self._drag_start_x = 0
        self._drag_start_scroll_x = 0

        self.add_events(
            Gdk.EventMask.BUTTON_PRESS_MASK |
            Gdk.EventMask.BUTTON_RELEASE_MASK |
            Gdk.EventMask.POINTER_MOTION_MASK |
            Gdk.EventMask.SCROLL_MASK
        )
        self.connect("button-press-event", self._on_button_press)
        self.connect("button-release-event", self._on_button_release)
        self.connect("motion-notify-event", self._on_motion)
        self.connect("scroll-event", self._on_scroll)

        self.set_app_paintable(True)
        self.connect("draw", self._draw)


    def do_get_preferred_height(self):
        return (72, 128) # minimum, natural


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

        return groups


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

        layout = self._get_layout(width, height)

        spool_h = layout["spool_h"]
        spool_w = layout["spool_w"]
        tray_pad_ratio = layout["tray_pad_ratio"]
        group_gap = layout["group_gap"]
        margin = layout["margin"]
        slot_w = layout["slot_w"]
        scroll_pad = layout["scroll_pad"]
        spool_cy = layout["spool_cy"]
        tray_top = layout["tray_top"]
        tray_h = layout["tray_h"]
    
        content_w = (
            total_spools * slot_w +
            max(0, len(groups) - 1) * group_gap +
            scroll_pad * 2 +
            margin * 2
        )
    
        max_scroll_x = max(0, content_w - width)
        self._scroll_x = max(0, min(self._scroll_x, max_scroll_x))
    
        # Spool layout and tray extensions are separate.
        # The tray may extend before/after a unit, but spool centers and hitboxes
        # should be based only on actual spool slots.
        spool_start_x = margin + scroll_pad - self._scroll_x
    
        tray_rects = []
        lid_rects = []
        gate_badges = []
    
        cr.save()
        cr.rectangle(0, 0, width, height)
        cr.clip()
    
        x = spool_start_x
    
        for group in groups:
            group_start = x
            group_w = slot_w * len(group)
    
            positioned_items = []
    
            for item in group:
                cx = x + slot_w / 2
    
                # Lift selected spool upward from tray
                selected_lift = spool_h * 0.05 if item["selected"] else 0
                item_spool_cy = spool_cy - selected_lift
    
                spool_x = cx - spool_w / 2 - 7
                spool_y = item_spool_cy - spool_h / 2 - 7

                # Use non-overlapping slot hitboxes, not full spool image hitboxes.
                # The spools overlap visually, but each gate should own one click slot.
                hitbox_x = x
                hitbox_y = item_spool_cy - spool_h / 2
                hitbox_w = slot_w
                hitbox_h = height - hitbox_y
                positioned_items.append((item, cx, item_spool_cy, spool_x, spool_y))
                visible_x = max(0, hitbox_x)
                visible_w = min(width, hitbox_x + hitbox_w) - visible_x
                if visible_w > 0:
                    self._hitboxes.append((item["gate"], visible_x, hitbox_y, visible_w, hitbox_h))
                gate_badges.append((item, cx, tray_top, tray_h, slot_w, spool_h))
    
                x += slot_w
    
            # Draw right-to-left so leftward spools visually overlap correctly.
            for item, cx, item_spool_cy, spool_x, spool_y in reversed(positioned_items):
                self._draw_spool(
                    cr,
                    cx,
                    item_spool_cy,
                    spool_w,
                    spool_h,
                    item["color"],
                    empty=item["empty"],
                    selected=item["selected"],
                )
    
            tray_pad = slot_w * tray_pad_ratio
            tray_x = group_start - tray_pad
            tray_w = group_w + tray_pad * 2
    
            tray_rects.append((tray_x, tray_top, tray_w, tray_h))
    
            lid_top = 1
            lid_height = tray_top + tray_h * 0.1
            lid_rects.append((tray_x, lid_top, tray_w, lid_height, spool_h))
    
            x += group_gap
    
        # Draw glass lids after spools but before trays.
        for rect in lid_rects:
            self._draw_unit_lid(cr, *rect)
    
        # Draw trays in foreground so they cover the lower part of the spools.
        for rect in tray_rects:
            self._draw_tray(cr, *rect)
    
        # Draw gate badges on top of the tray.
        for item, cx, tray_top, tray_h, slot_w, spool_h in gate_badges:
            self._draw_gate_status(cr, item, cx, tray_top, tray_h, slot_w, spool_h)

#        # PAUL DEBUG: Visualize hitboxes
#        for gate, x, y, w, h in self._hitboxes:
#            cr.save()
#            cr.set_source_rgba(1.0, 0.0, 0.0, 0.18)
#            cr.rectangle(x, y, w, h)
#            cr.fill()
#            cr.set_source_rgb(1.0, 0.0, 0.0)
#            cr.set_line_width(1.0)
#            cr.rectangle(x, y, w, h)
#            cr.stroke()
#            cr.restore()
#        # PAUL DEBUG
    
        cr.restore()
    
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

        if selected:
            # Lighted-from-below effect
            grad = cairo.RadialGradient(
                cx,
                cy + h * 0.40,
                h * 0.02,      # inner radius
                cx,
                cy + h * 0.28,
                h * 0.30,      # outer radius
            )
            grad.add_color_stop_rgba(0.00, 1.00, 1.00, 1.00, 0.90)  # pure white
            grad.add_color_stop_rgba(0.18, 1.00, 0.98, 0.88, 0.70)  # warm white
            grad.add_color_stop_rgba(0.45, 1.00, 0.90, 0.45, 0.35)  # warm yellow
            grad.add_color_stop_rgba(1.00, 1.00, 0.65, 0.00, 0.00)  # deep yellow, transparent

            cr.save()
            cr.arc(cx, cy + h * 0.08, h * 0.42, 0, math.tau)
            cr.clip()
            cr.set_source(grad)
            cr.paint()
            cr.restore()


    def _render_spool(self, cr, w, h, color, empty, filament_pct=100):
        fr, fg, fb = self._parse_color(color)
        filament_pct = max(0.0, min(1.0, filament_pct / 100.0))

        # Cardboard colors
        cardboard      = (0.70, 0.52, 0.30)
        cardboard_dark = (0.38, 0.25, 0.12) # Recess on cardboard joins
        cardboard_edge = (0.20, 0.13, 0.06)

        spool_cx = w / 2

        body_w = w * 0.38 # width of filament
        body_x = spool_cx - body_w / 2

        left_x = body_x
        right_x = body_x + body_w

        outer_w = w * 0.16 # Orientation of spools to viewer
        outer_h = h * 0.88

        # Use the outer oval aspect ratio for all smaller ovals
        oval_ratio = outer_w / outer_h

        # Tube / center hole dimensions
        tube_h = outer_h * 0.38
        tube_w = tube_h * oval_ratio

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
        self._draw_oval(cr, right_x, h / 2, outer_w, outer_h, cardboard, cardboard_edge, stroke_width=2)

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


    def _draw_gate_status(self, cr, item, cx, tray_top, tray_h, slot_w, spool_h):
        badge_w = min(slot_w * 0.72, spool_h * 0.42)
        badge_h = min(tray_h * 0.42, spool_h * 0.18)
        badge_x = cx - badge_w / 2
        badge_y = tray_top + tray_h * 0.28
        radius = badge_h * 0.25

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

        self._draw_rounded_rect(cr, badge_x, badge_y, badge_w, badge_h, radius, fill_rgb=fill_rgba, stroke_rgb=stroke_rgb, stroke_width=2)

        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        font_size = max(8, min(badge_h * 0.68, spool_h * 0.12))
        cr.set_font_size(font_size)

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


    def _draw_unit_lid(self, cr, x, y, w, h, spool_h):
        radius = spool_h * 0.10

        # Main glass tint.
        glass_grad = cairo.LinearGradient(0, y, 0, y + h)
        glass_grad.add_color_stop_rgba(0.00, 1.00, 1.00, 1.00, 0.10)
        glass_grad.add_color_stop_rgba(0.25, 0.80, 0.90, 1.00, 0.04)
        glass_grad.add_color_stop_rgba(1.00, 0.20, 0.24, 0.28, 0.05)

        self._draw_rounded_rect(
            cr, x, y, w, h, radius,
            fill_rgb=glass_grad,
            stroke_rgb=(1.0, 1.0, 1.0, 0.14),
            stroke_width=max(1.0, spool_h * 0.012),
        )

        # Top glossy reflection band.
        highlight_h = spool_h * 0.16
        highlight_grad = cairo.LinearGradient(0, y, 0, y + highlight_h)
        highlight_grad.add_color_stop_rgba(0.00, 1.0, 1.0, 1.0, 0.18)
        highlight_grad.add_color_stop_rgba(1.00, 1.0, 1.0, 1.0, 0.00)

        cr.save()
        self._rounded_rect_path(cr, x + 1, y + 1, w - 2, highlight_h, radius * 0.75)
        cr.clip()
        cr.set_source(highlight_grad)
        cr.paint()
        cr.restore()


    def scroll_gate_into_view(self, gate, center=False):
        if self._items is None:
            self._items = self._build_items()

        alloc = self.get_allocation()
        width = alloc.width
        height = alloc.height

        groups = self._items
        total_spools = sum(len(g) for g in groups)
        if total_spools == 0 or width <= 0:
            return

        layout = self._get_layout(width, height)

        slot_w = layout["slot_w"]
        group_gap = layout["group_gap"]
        margin = layout["margin"]
        scroll_pad = layout["scroll_pad"]

        content_w = (
            total_spools * slot_w +
            max(0, len(groups) - 1) * group_gap +
            scroll_pad * 2 +
            margin * 2
        )

        max_scroll_x = max(0, content_w - width)

        x = margin + scroll_pad

        for group in groups:
            for item in group:
                slot_x = x
                slot_center = slot_x + slot_w / 2

                if item["gate"] == gate:
                    fully_visible = (
                        slot_x >= self._scroll_x and
                        slot_x + slot_w <= self._scroll_x + width
                    )

                    if fully_visible and not center:
                        return

                    target_scroll_x = slot_center - width / 2
                    self._scroll_x = max(0, min(target_scroll_x, max_scroll_x))
                    self.queue_draw()
                    return

                x += slot_w

            x += group_gap


    # ---------------------------------------------------------------------------
    # Scrolling and Pop-up action handling
    # ---------------------------------------------------------------------------

    def _hit_test_spool(self, px, py):
        # Hitboxes are stored left-to-right, which matches the visual topmost
        # order when spools are drawn right-to-left.
        for gate, x, y, w, h in self._hitboxes:
            if x <= px <= x + w and y <= py <= y + h:
                return gate
        return None


    def _on_button_press(self, widget, event):
        if event.button != 1:
            return False

        # A new touch/drag on the tray should cancel any existing popup/shield.
        self._close_gate_popover()

        self._drag_active = True
        self._drag_start_x = event.x
        self._drag_start_scroll_x = self._scroll_x
        return True


    def _on_motion(self, widget, event):
        if not self._drag_active:
            return False

        dx = event.x - self._drag_start_x
        self._scroll_x = self._drag_start_scroll_x - dx
        self.queue_draw()
        return True


    def _on_button_release(self, widget, event):
        if not self._drag_active:
            return False

        self._drag_active = False

        device = event.get_device()
        if device is not None:
            device.ungrab(event.time)

        # Treat short drags as taps/clicks.
        if abs(event.x - self._drag_start_x) < 8:
            gate = self._hit_test_spool(event.x, event.y)
            if gate is not None:
                self._show_gate_popover(gate, event.x, event.y)

        return True


    def _on_scroll(self, widget, event):
        step = self.get_allocation().height * 0.45

        if event.direction == Gdk.ScrollDirection.LEFT:
            self._scroll_x -= step
        elif event.direction == Gdk.ScrollDirection.RIGHT:
            self._scroll_x += step
        elif event.direction == Gdk.ScrollDirection.UP:
            self._scroll_x -= step
        elif event.direction == Gdk.ScrollDirection.DOWN:
            self._scroll_x += step
        else:
            return False

        self.queue_draw()
        return True


    def _on_shield_button_press(self, shield, event):

        coords = shield.translate_coordinates(self, event.x, event.y)

        self._close_gate_popover()

        if coords is not None:
            x, y = coords

            self._drag_active = True
            self._drag_start_x = x
            self._drag_start_scroll_x = self._scroll_x

            # Grab pointer motion after the shield is hidden.
            window = self.get_window()
            if window is not None:
                device = event.get_device()
                if window is not None and device is not None:
                    Gdk.Device.grab(
                        device,
                        window,
                        Gdk.GrabOwnership.NONE,
                        False,
                        Gdk.EventMask.BUTTON_RELEASE_MASK |
                        Gdk.EventMask.POINTER_MOTION_MASK,
                        None,
                        event.time,
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
        title.set_margin_bottom(2)
        box.pack_start(title, False, False, 0)

        button_grid = Gtk.Grid()
        button_grid.set_row_spacing(4)
        button_grid.set_column_spacing(4)
        button_grid.set_margin_top(4)

        load_btn = Gtk.Button(label="Load")
        unload_btn = Gtk.Button(label="Unload")
        select_btn = Gtk.Button(label="Select")
        cancel_btn = Gtk.Button(label="Close")

        load_btn.connect("clicked", self._on_gate_action, gate, "load")
        unload_btn.connect("clicked", self._on_gate_action, gate, "unload")
        select_btn.connect("clicked", self._on_gate_action, gate, "select")
        cancel_btn.connect("clicked", lambda button: self._close_gate_popover())

        button_grid.attach(load_btn,   0, 0, 1, 1)
        button_grid.attach(unload_btn, 1, 0, 1, 1)
        button_grid.attach(select_btn, 0, 1, 1, 1)
        button_grid.attach(cancel_btn, 1, 1, 1, 1)

        box.pack_start(button_grid, False, False, 0)

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
    #  ---------------------------------------------------------------------------

    def _get_layout(self, width, height):
        """
        Centralized layout sizing logic for tweaking look and feel of major components
        """
        spool_h = height * 0.86        # Height drives spool size. Everything else is derived from spool_h
        spool_w = spool_h * 0.80       # Overall drawing width allocated to one spool image

        tray_pad_ratio = 0.25
        group_gap = spool_h * 0.18     # Gap between separate MMU units, in spool-height units

        margin = spool_h * 0.0         # Left/right outer margin inside this widget

        slot_w = spool_w * 0.5         # Horizontal spacing between spool centers; Smaller = tighter overlap inside a unit.
        scroll_pad = slot_w * 0.10     # Extra scroll padding before first and after last spool

        spool_cy = height * 0.44       # Vertical center of normal spools

        # Tray anchored to spool position. Larger value = tray starts lower = covers less of the spool.
        tray_top = spool_cy + spool_h * 0.24
        tray_h = height - tray_top - 2

        return {
            "spool_h": spool_h,
            "spool_w": spool_w,
            "tray_pad_ratio": tray_pad_ratio,
            "group_gap": group_gap,
            "margin": margin,
            "slot_w": slot_w,
            "scroll_pad": scroll_pad,
            "spool_cy": spool_cy,
            "tray_top": tray_top,
            "tray_h": tray_h,
        }


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


    def _rounded_rect_path(self, cr, x, y, w, h, r):
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
