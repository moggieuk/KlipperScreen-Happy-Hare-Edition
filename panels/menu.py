import json
import logging

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
from jinja2 import Template
from ks_includes.screen_panel import ScreenPanel
from ks_includes.widgets.autogrid import AutoGrid


class Panel(ScreenPanel):

    def __init__(self, screen, title, items=None):
        super().__init__(screen, title)
        self.menu_callbacks = {} # Happy Hare
        self.items = items
        self.j2_data = self._printer.get_printer_status_data()
        self.create_menu_items()
        self.scroll = self._gtk.ScrolledWindow()
        self.scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.autogrid = AutoGrid()

    def activate(self):
        self.j2_data = self._printer.get_printer_status_data()
        self.add_content()

    def add_content(self):
        for child in self.scroll.get_children():
            self.scroll.remove(child)
        self.scroll.add(self.arrangeMenuItems(self.items))
        if not self.content.get_children():
            self.content.add(self.scroll)

    # Happy Hare vvv
    def process_update(self, action, data):
        if action != "notify_status_update":
            return

        j2_refreshed = False
        unique_cbs = []
        for x in data:
            for i in data[x]:
                if ("printer.%s.%s" % (x, i)) in self.menu_callbacks:
                    for cb in self.menu_callbacks["printer.%s.%s" % (x, i)]:
                        if cb not in unique_cbs:
                            unique_cbs.append(cb)

        # Call specific associated callbacks
        if unique_cbs:
            self.j2_data = self._printer.get_printer_status_data() # Happy Hare: must refresh for dynamic sensitive state
            j2_refreshed = True
        for cb in unique_cbs:
            cb[0](cb[1])

        # New Klipperscreen "active" support
        for item in self.autogrid:
            key = item.get_name()
            for item_dict in self.items:
                if key in item_dict and 'active' in item_dict[key]:
                    if not j2_refreshed:
                        self.j2_data = self._printer.get_printer_status_data()
                        j2_refreshed = True
                    if self.evaluate_enable(item_dict[key]['active']):
                        item.get_style_context().add_class("menu_active")
                    else:
                        item.get_style_context().remove_class("menu_active")
                    break

    def register_callback(self, var, method, arg): # Happy Hare
        if var in self.menu_callbacks:
            self.menu_callbacks[var].append([method, arg])
        else:
            self.menu_callbacks[var] = [[method, arg]]

    def check_enable(self, i): # Happy Hare
        item = self.items[i]
        key = list(item.keys())[0]
        enable = self.evaluate_enable(item[key]['enable'])
        self.labels[key].set_sensitive(enable)
    # Happy Hare ^^^

    def arrangeMenuItems(self, items, columns=None, expand_last=False):
        self.autogrid.clear()
        enabled = []
        for item in items:
            key = list(item)[0]
            show_disabled = item[key].get('show_disabled', "False").strip().lower() == "true"
            is_enabled = self.evaluate_enable(item[key]['enable'])
            if show_disabled:
                self.labels[key].set_sensitive(is_enabled)
            else:
                if not self.evaluate_enable(item[key]['enable']):
                    logging.debug(f"X > {key}")
                    continue
            enabled.append(self.labels[key])
        self.autogrid.__init__(enabled, columns, expand_last, self._screen.vertical_mode)
        return self.autogrid

    def create_menu_items(self):
        # Happy Hare vvv
        count = 0
        for i in self.items:
            x = i[next(iter(i))] # Happy Hare 'show_disabled' check to speed up!
            if x.get('show_disabled', "False").strip().lower() == "true" or self.evaluate_enable(x['enable']):
                count += 1
        #count = sum(bool(self.evaluate_enable(i[next(iter(i))]['enable'])) for i in self.items) # Happy Hare: Don't count disabled items it show_disabled
        # Happy Hare ^^^

        scale = 1.1 if 12 < count <= 16 else None  # hack to fit a 4th row
        for i in range(len(self.items)):
            key = list(self.items[i])[0]
            item = self.items[i][key]

            name = self._screen.env.from_string(item['name']).render(self.j2_data)
            icon = self._screen.env.from_string(item['icon']).render(self.j2_data) if item['icon'] else None
            style = self._screen.env.from_string(item['style']).render(self.j2_data) if item['style'] else None

            if icon == "notifications" and (
                bool(self._screen.server_info["warnings"])
                or bool(self._printer.warnings)
                or bool(self._screen.server_info["failed_components"])
                or bool(self._screen.server_info["missing_klippy_requirements"])
            ):
                icon = "notification_important"

            b = self._gtk.Button(icon, name, style or f"color{i % 4 + 1}", scale=scale)

            if item['panel']:
                b.connect("clicked", self.menu_item_clicked, item)
            elif item['method']:
                params = {}

                if item['params'] is not False:
                    try:
                        p = self._screen.env.from_string(item['params']).render(self.j2_data)
                        params = json.loads(p)
                    except Exception as e:
                        logging.exception(f"Unable to parse parameters for [{name}]:\n{e}")
                        params = {}

                if item['confirm'] is not None:
                    b.connect("clicked", self._screen._confirm_send_action, item['confirm'], item['method'], params)
                else:
                    params['show_disabled'] = item.get('show_disabled', "False").strip().lower() == "true" # Happy Hare: Need to know if dynamic sensitivity
                    b.connect("clicked", self._screen._send_action, item['method'], params)
            else:
                b.connect("clicked", self._screen._go_to_submenu, key)

            if item['refresh_on'] is not None: # Happy Hare
                for var in item['refresh_on'].split(', '):
                    self.register_callback(var, self.check_enable, i)

            self.labels[key] = b

    def evaluate_enable(self, enable):
        if enable == "{{ moonraker_connected }}":
            logging.info(f"moonraker connected {self._screen._ws.connected}")
            return self._screen._ws.connected
        self.j2_data["klipperscreen"] = { # Happy Hare: to allow for menu button rather than side bar navigation
                "side_mmu_shortcut": self._config.get_main_config().getboolean("side_mmu_shortcut")
                }
        try:
            j2_temp = Template(enable, autoescape=True)
            return j2_temp.render(self.j2_data) == 'True'
        except Exception as e:
            logging.debug(f"Error evaluating enable statement: {enable}\n{e}")
            return False
