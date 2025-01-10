# Happy Hare MMU Software
# Basic manual operation panel (generally in recovery situation)
#
# Copyright (C) 2023-2025  moggieuk#6538 (discord)
#                          moggieuk@hotmail.com
#
import logging, gi

gi.require_version("Gtk", "3.0")

from gi.repository import Gtk, GLib, Pango
from ks_includes.screen_panel import ScreenPanel

class Panel(ScreenPanel):
    TOOL_UNKNOWN = -1
    TOOL_BYPASS = -2

    NOT_SET = -99

    def __init__(self, screen, title):
        super().__init__(screen, title)

        # We need to keep track of just a little bit of UI state
        self.ui_sel_gate = self.NOT_SET
        self.ui_action_button_name = self.ui_action_button_label = None

        self.has_bypass = False
        self.min_gate = 0
        self.has_bypass = self._printer.get_stat("mmu")['has_bypass']
        if self.has_bypass:
            self.min_gate = self.TOOL_BYPASS

        # btn_states: The "gaps" are what functionality the state takes away. Multiple states are combined
        self.btn_states = {
            'all':             ['gate', 'checkgate', 'recover', 'load', 'unload', 'home', 'motors_off', 'servo_up', 'servo_move', 'servo_down', 'grip', 'release', 'load_ext', 'unload_ext', 'sync', 'unsync'],
            'homed':           ['gate', 'checkgate', 'recover', 'load', 'unload', 'home', 'motors_off', 'servo_up', 'servo_move', 'servo_down', 'grip', 'release', 'load_ext', 'unload_ext', 'sync', 'unsync'],
            'not_homed':       [                     'recover',         'unload', 'home', 'motors_off', 'servo_up', 'servo_move', 'servo_down', 'grip', 'release', 'load_ext', 'unload_ext', 'sync', 'unsync'],
            'servo_up':        ['gate', 'checkgate', 'recover', 'load', 'unload', 'home', 'motors_off',             'servo_move', 'servo_down', 'grip', 'release', 'load_ext', 'unload_ext', 'sync', 'unsync'],
            'servo_move':      ['gate', 'checkgate', 'recover', 'load', 'unload', 'home', 'motors_off', 'servo_up',               'servo_down', 'grip', 'release', 'load_ext', 'unload_ext', 'sync', 'unsync'],
            'servo_down':      ['gate', 'checkgate', 'recover', 'load', 'unload', 'home', 'motors_off', 'servo_up', 'servo_move',               'grip', 'release', 'load_ext', 'unload_ext', 'sync', 'unsync'],
            'gripped':         ['gate', 'checkgate', 'recover', 'load', 'unload', 'home', 'motors_off', 'servo_up', 'servo_move', 'servo_down',         'release', 'load_ext', 'unload_ext', 'sync', 'unsync'],
            'released':        ['gate', 'checkgate', 'recover', 'load', 'unload', 'home', 'motors_off', 'servo_up', 'servo_move', 'servo_down', 'grip',            'load_ext', 'unload_ext', 'sync', 'unsync'],
            'bypass_loaded':   [                     'recover',         'unload',         'motors_off', 'servo_up', 'servo_move', 'servo_down', 'grip', 'release',             'unload_ext', 'sync', 'unsync'],
            'bypass_unloaded': ['gate', 'checkgate', 'recover', 'load',           'home', 'motors_off', 'servo_up', 'servo_move', 'servo_down', 'grip', 'release', 'load_ext', 'unload_ext', 'sync', 'unsync'],
            'bypass_unknown':  ['gate', 'checkgate', 'recover', 'load', 'unload', 'home', 'motors_off', 'servo_up', 'servo_move', 'servo_down', 'grip', 'release', 'load_ext', 'unload_ext', 'sync', 'unsync'],
            'tool_loaded':     [                     'recover',         'unload',         'motors_off', 'servo_up', 'servo_move', 'servo_down', 'grip', 'release',             'unload_ext', 'sync', 'unsync'],
            'tool_unloaded':   ['gate', 'checkgate', 'recover', 'load', 'unload', 'home', 'motors_off', 'servo_up', 'servo_move', 'servo_down', 'grip', 'release', 'load_ext', 'unload_ext', 'sync', 'unsync'],
            'tool_unknown':    ['gate', 'checkgate', 'recover', 'load', 'unload', 'home', 'motors_off', 'servo_up', 'servo_move', 'servo_down', 'grip', 'release', 'load_ext', 'unload_ext', 'sync', 'unsync'],
            'synced':          ['gate', 'checkgate', 'recover', 'load', 'unload', 'home', 'motors_off', 'servo_up', 'servo_move', 'servo_down', 'grip', 'release', 'load_ext', 'unload_ext',         'unsync'],
            'unsynced':        ['gate', 'checkgate', 'recover', 'load', 'unload', 'home', 'motors_off', 'servo_up', 'servo_move', 'servo_down', 'grip', 'release', 'load_ext', 'unload_ext', 'sync',         ],
            'busy':            [                                                                                                                                                                             ],
            'disabled':        [                                                                                                                                                                             ],
        }

        self.labels = {
            'g_decrease': self._gtk.Button('decrease', None, scale=self.bts * 1.2),
            'gate': self._gtk.Button('mmu_select_gate', 'Gate', 'color4'),
            'g_increase': self._gtk.Button('increase', None, scale=self.bts * 1.2),
            'servo_up': self._gtk.Button('arrow-up', 'Servo Up', 'color1'),
            'servo_move': self._gtk.Button('arrow-right', 'Servo Move', 'color2'),
            'servo_down': self._gtk.Button('arrow-down', 'Servo Down', 'color3'),
            'grip': self._gtk.Button('arrow-down', 'Grip', 'color2'),
            'release': self._gtk.Button('arrow-up', 'Release', 'color3'),
            'home': self._gtk.Button('home', 'Home', 'color2'),
            'motors_off': self._gtk.Button('motor-off', 'Motors Off', 'color3'),
            'checkgate': self._gtk.Button('mmu_checkgates', 'Check Gate', 'color4'),
            'recover': self._gtk.Button('mmu_maintenance', 'Recover State...', 'color1'),
            'load': self._gtk.Button('mmu_load', 'Load', 'color1'),
            'unload': self._gtk.Button('mmu_unload', 'Unload', 'color1'), # Doubles as eject button
            'sync': self._gtk.Button('mmu_synced_extruder', 'Sync', 'color2'),
            'unsync': self._gtk.Button('mmu_extruder', 'Unsync', 'color2'),
            'load_ext': self._gtk.Button('mmu_load_extruder', 'Load Ext', 'color3'),
            'unload_ext': self._gtk.Button('mmu_unload_extruder', 'Unload Ext', 'color3'),
            'eject_img': self._gtk.Image('mmu_eject'), # Alternative for unload button to fully eject
        }
        self.labels['unload_img'] = self.labels['unload'].get_image()

        self.labels['g_decrease'].connect("clicked", self.select_gate, -1)
        self.labels['gate'].connect("clicked", self.select_gate, 0)
        self.labels['g_increase'].connect("clicked", self.select_gate, 1)
        self.labels['checkgate'].connect("clicked", self.select_checkgate)
        self.labels['recover'].connect("clicked", self.menu_item_clicked, {"panel": "mmu_recover", "name": "MMU State Recovery"})
        self.labels['load'].connect("clicked", self.select_load)
        self.labels['unload'].connect("clicked", self.select_unload_eject)
        self.labels['home'].connect("clicked", self.select_home)
        self.labels['motors_off'].connect("clicked", self.select_motors_off)
        self.labels['servo_up'].connect("clicked", self.select_servo_up)
        self.labels['servo_move'].connect("clicked", self.select_servo_move)
        self.labels['servo_down'].connect("clicked", self.select_servo_down)
        self.labels['grip'].connect("clicked", self.select_grip)
        self.labels['release'].connect("clicked", self.select_release)
        self.labels['load_ext'].connect("clicked", self.select_load_extruder)
        self.labels['unload_ext'].connect("clicked", self.select_unload_extruder)
        self.labels['sync'].connect("clicked", self.select_sync)
        self.labels['unsync'].connect("clicked", self.select_unsync)

        self.labels['g_increase'].set_hexpand(False)
        self.labels['g_increase'].get_style_context().add_class("mmu_sel_increase")
        self.labels['g_decrease'].set_hexpand(False)
        self.labels['g_decrease'].get_style_context().add_class("mmu_sel_decrease")

        selector_type = self._printer.get_stat("mmu")['selector_type']
        grid = Gtk.Grid()
        grid.set_column_homogeneous(True)
        grid.set_row_homogeneous(True)
        if selector_type in ['RotarySelector', 'LinearSelector']:
            grid.attach(self.labels['g_decrease'], 0, 0, 1, 1)
            grid.attach(self.labels['gate'],       1, 0, 1, 1)
            grid.attach(self.labels['g_increase'], 2, 0, 1, 1)
            if selector_type == 'RotarySelector':
                grid.attach(self.labels['grip'],       4, 0, 1, 1)
                grid.attach(self.labels['release'],    5, 0, 1, 1)
            elif selector_type == 'LinearSelector':
                grid.attach(self.labels['servo_up'],   3, 0, 1, 1)
                grid.attach(self.labels['servo_move'], 4, 0, 1, 1)
                grid.attach(self.labels['servo_down'], 5, 0, 1, 1)
            grid.attach(self.labels['recover'],    0, 1, 2, 1)
            grid.attach(self.labels['checkgate'],  2, 1, 2, 1)
            grid.attach(self.labels['home'],       4, 1, 1, 1)
            grid.attach(self.labels['motors_off'], 5, 1, 1, 1)
            grid.attach(self.labels['load'],       0, 2, 1, 1)
            grid.attach(self.labels['unload'],     1, 2, 1, 1)
            if selector_type == 'LinearSelector':
                grid.attach(self.labels['sync'],       2, 2, 1, 1)
                grid.attach(self.labels['unsync'],     3, 2, 1, 1)
            grid.attach(self.labels['load_ext'],   4, 2, 1, 1)
            grid.attach(self.labels['unload_ext'], 5, 2, 1, 1)
        else:
            grid.attach(self.labels['g_decrease'], 0, 0, 1, 1)
            grid.attach(self.labels['gate'],       1, 0, 2, 1)
            grid.attach(self.labels['g_increase'], 3, 0, 1, 1)
            grid.attach(self.labels['motors_off'], 5, 0, 1, 1)
            grid.attach(self.labels['recover'],    0, 1, 2, 1)
            grid.attach(self.labels['checkgate'],  2, 1, 2, 1)
            grid.attach(self.labels['load'],       0, 2, 2, 1)
            grid.attach(self.labels['unload'],     2, 2, 2, 1)
            grid.attach(self.labels['load_ext'],   4, 2, 1, 1)
            grid.attach(self.labels['unload_ext'], 5, 2, 1, 1)

        scroll = self._gtk.ScrolledWindow()
        scroll.add(grid)
        self.content.add(scroll)

        self.ui_sel_gate = self.NOT_SET
        self.ui_action_button_name = None
        self.ui_action_button_label = ""

    def activate(self):
        self.init_gate_values()
        if self.ui_action_button_name != None:
            self.labels[self.ui_action_button_name].set_label(self.ui_action_button_label)

    def process_update(self, action, data):
        if action == "notify_status_update":
            if 'mmu' in data:
                e_data = data['mmu']
                if 'gate' in e_data:
                    self.ui_sel_gate = e_data['gate']
                    if e_data['gate'] >= 0:
                        self.labels['load'].set_label(f"Load #{e_data['gate']}")
                    else:
                        self.labels['load'].set_label(f"Load")
                if 'action' in e_data:
                    action = e_data['action']
                    if self.ui_action_button_name != None:
                        if action == "Idle" or action == "Unknown":
                            self.labels[self.ui_action_button_name].set_label(self.ui_action_button_label) # Restore original button label
                            self.ui_action_button_name = None
                        else:
                            self.labels[self.ui_action_button_name].set_label(action) # Use button to convey action status
                self.update_active_buttons()

    def init_gate_values(self):
        # Get starting values
        mmu = self._printer.get_stat("mmu")
        if self.ui_sel_gate == self.NOT_SET and mmu['gate'] != self.TOOL_UNKNOWN:
            self.ui_sel_gate = mmu['gate']
        else:
            self.ui_sel_gate = 0

    def select_gate(self, widget, param=0):
        mmu = self._printer.get_stat("mmu")
        num_gates = len(mmu['gate_status'])

        if param < 0 and self.ui_sel_gate > self.min_gate:
            self.ui_sel_gate -= 1
            if self.ui_sel_gate == self.TOOL_UNKNOWN:
                self.ui_sel_gate = self.TOOL_BYPASS
        elif param > 0 and self.ui_sel_gate < num_gates - 1:
            self.ui_sel_gate += 1
            if self.ui_sel_gate == self.TOOL_UNKNOWN:
                self.ui_sel_gate = 0
        elif param == 0:
            self.ui_action_button_name = 'gate'
            self.ui_action_button_label = self.labels[self.ui_action_button_name].get_label()
            if self.ui_sel_gate == self.TOOL_BYPASS:
                self._screen._ws.klippy.gcode_script(f"MMU_SELECT_BYPASS")
            elif mmu['filament'] != "Loaded":
                self._screen._ws.klippy.gcode_script(f"MMU_SELECT GATE={self.ui_sel_gate}")
            return
        self.update_gate_buttons()

    def select_gatebutton(self, widget):
        self.ui_action_button_name = 'gate'
        self.ui_action_button_label = self.labels[self.ui_action_button_name].get_label()
        self._screen._ws.klippy.gcode_script(f"MMU_SELECT GATE={self.ui_sel_gate}")

    def select_checkgate(self, widget):
        self.ui_action_button_name = 'checkgate'
        self.ui_action_button_label = self.labels[self.ui_action_button_name].get_label()
        mmu = self._printer.get_stat("mmu")
        current_gate = mmu['gate']
        self._screen._ws.klippy.gcode_script(f"MMU_CHECK_GATE GATE={current_gate} QUIET=1")

    def select_sync(self, widget):
        self._screen._ws.klippy.gcode_script("MMU_SYNC_GEAR_MOTOR SYNC=1")

    def select_unsync(self, widget):
        self._screen._ws.klippy.gcode_script("MMU_SYNC_GEAR_MOTOR SYNC=0")

    def select_load(self, widget):
        self.ui_action_button_name = 'load'
        self.ui_action_button_label = self.labels[self.ui_action_button_name].get_label()
        self._screen._ws.klippy.gcode_script(f"MMU_LOAD")

    def select_unload_eject(self, widget):
        self.ui_action_button_name = 'unload'
        self.ui_action_button_label = self.labels[self.ui_action_button_name].get_label()
        mmu = self._printer.get_stat("mmu")
        filament = mmu['filament']
        if filament != "Unloaded":
            self._screen._ws.klippy.gcode_script(f"MMU_UNLOAD")
        else:
            self._screen._ws.klippy.gcode_script(f"MMU_EJECT")

    def select_home(self, widget):
        self.ui_action_button_name = 'home'
        self.ui_action_button_label = self.labels[self.ui_action_button_name].get_label()
        self._screen._ws.klippy.gcode_script(f"MMU_HOME")

    def select_motors_off(self, widget):
        self._screen._confirm_send_action(
            None,
            "This will reset MMU positional state and require re-homing\n\nSure you want to continue?",
            "printer.gcode.script",
            {'script': "MMU_MOTORS_OFF"}
        )

    def select_servo_up(self, widget):
        self._screen._ws.klippy.gcode_script(f"MMU_SERVO POS=up")

    def select_servo_move(self, widget):
        self._screen._ws.klippy.gcode_script(f"MMU_SERVO POS=move")

    def select_servo_down(self, widget):
        self._screen._ws.klippy.gcode_script(f"MMU_SERVO POS=down")

    def select_grip(self, widget):
        self._screen._ws.klippy.gcode_script(f"MMU_GRIP")

    def select_release(self, widget):
        self._screen._ws.klippy.gcode_script(f"MMU_RELEASE")

    def select_load_extruder(self, widget):
        self.ui_action_button_name = 'load_ext'
        self.ui_action_button_label = self.labels[self.ui_action_button_name].get_label()
        self._screen._ws.klippy.gcode_script(f"MMU_LOAD EXTRUDER_ONLY=1")

    def select_unload_extruder(self, widget):
        self.ui_action_button_name = 'unload_ext'
        self.ui_action_button_label = self.labels[self.ui_action_button_name].get_label()
        self._screen._ws.klippy.gcode_script(f"MMU_UNLOAD EXTRUDER_ONLY=1")

    # Dynamically update button sensitivity based on state
    def update_active_buttons(self):
        mmu = self._printer.get_stat("mmu")
        enabled = mmu['enabled']
        is_homed = mmu['is_homed']
        gate = mmu['gate']
        tool = mmu['tool']
        action = mmu['action']
        filament = mmu['filament']
        sync_drive = mmu['sync_drive']
        selector_type = mmu['selector_type']

        ui_state = []
        if enabled:
            ui_state.append("homed" if is_homed else "not_homed")

            if tool == self.TOOL_BYPASS:
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

            if filament != "Unloaded":
                self.labels['unload'].set_image(self.labels['unload_img'])
                self.labels['unload'].set_label("Unload")
            else:
                self.labels['unload'].set_image(self.labels['eject_img'])
                self.labels['unload'].set_label("Eject")

            if selector_type == 'RotarySelector':
                grip = mmu.get('grip', None)
                ui_state.append("gripped" if grip.lower() == 'gripped'  else "released")
            elif selector_type == 'LinearSelector':
                servo = mmu.get('servo', None)
                servo_states = {
                    'Up': ['servo_up'],
                    'Down': ['servo_down'],
                    'Move': ['servo_move'],
                    'Unknown': [],
                    'default': ['servo_up', 'servo_down', 'servo_move', 'homed']
                }
                ui_state.extend(servo_states.get(servo, servo_states['default']))
                ui_state.append("synced" if sync_drive else "unsynced")

            if action != "Idle" and action != "Unknown":
                ui_state.append("busy")
        else:
            ui_state.append("disabled")

        logging.debug(f"mmu_manage: ui_state={ui_state}")
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
            if label == "gate":
                gate_sensitive = sensitive
        self.update_gate_buttons(gate_sensitive)

    def update_gate_buttons(self, gate_sensitive=True):
        mmu = self._printer.get_stat("mmu")
        gate = mmu['gate']
        filament = mmu['filament']
        num_gates = len(mmu['gate_status'])
        action = mmu['action']
        if (gate == self.TOOL_BYPASS and filament != "Unloaded") or not gate_sensitive:
            self.labels['g_decrease'].set_sensitive(False)
            self.labels['g_increase'].set_sensitive(False)
        else:
            if self.ui_sel_gate == self.min_gate:
                self.labels['g_decrease'].set_sensitive(False)
            else:
                self.labels['g_decrease'].set_sensitive(True)

            if self.ui_sel_gate == num_gates -1:
                self.labels['g_increase'].set_sensitive(False)
            else:
                self.labels['g_increase'].set_sensitive(True)

        if action == "Idle":
            if self.ui_sel_gate >= 0:
                self.labels['gate'].set_label(f"Gate #{self.ui_sel_gate}")
                if mmu['gate'] == self.ui_sel_gate:
                    self.labels['gate'].set_sensitive(False)
                else:
                    self.labels['gate'].set_sensitive(gate_sensitive)
            elif self.ui_sel_gate == self.TOOL_BYPASS:
                self.labels['gate'].set_label(f"Bypass")
                if mmu['gate'] == self.ui_sel_gate:
                    self.labels['gate'].set_sensitive(False)
                else:
                    self.labels['gate'].set_sensitive(gate_sensitive)
            else:
                self.labels['gate'].set_label(f"Unknown")
        else:
            self.labels['gate'].set_label(action)
            self.labels['gate'].set_sensitive(False)

        if self.ui_sel_gate == self.TOOL_BYPASS:
            self.labels['checkgate'].set_sensitive(False)
        elif gate_sensitive:
            self.labels['checkgate'].set_sensitive(True)

