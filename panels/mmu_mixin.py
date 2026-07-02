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
#

import logging
from gi.repository import Gdk


TOOL_GATE_UNKNOWN = -1
TOOL_GATE_BYPASS = -2

GATE_UNKNOWN = -1
GATE_EMPTY = 0
GATE_AVAILABLE = 1 # Available to load from either buffer or spool
GATE_AVAILABLE_FROM_BUFFER = 2

FILAMENT_POS_UNKNOWN = -1
FILAMENT_POS_UNLOADED = 0       # Parked in gate
FILAMENT_POS_HOMED_GATE = 1     # Homed at either gate or mmu exit sensor (currently assumed mutually exclusive sensors)
FILAMENT_POS_START_BOWDEN = 2   # Point of fast load portion
FILAMENT_POS_IN_BOWDEN = 3      # Some unknown position in the bowden
FILAMENT_POS_END_BOWDEN = 4     # End of fast load portion
FILAMENT_POS_HOMED_ENTRY = 5    # Homed at entry sensor
FILAMENT_POS_HOMED_EXTRUDER = 6 # Collision homing case at extruder gear entry
FILAMENT_POS_EXTRUDER_ENTRY = 7 # Past extruder gear entry
FILAMENT_POS_HOMED_TS = 8       # Homed at toolhead sensor
FILAMENT_POS_IN_EXTRUDER = 9    # In extruder past toolhead sensor
FILAMENT_POS_LOADED = 10        # Homed to nozzle

FILAMENT_POS_NAME_MAP = {
   -1: "UNKNOWN",
    0: "UNLOADED AND PARKED",
    1: "HOMED AT GATE",
    2: "START OF BOWDEN",
    3: "IN BOWDEN",
    4: "END OF BOWDEN",
    5: "HOMED AT EXTRUDER SENSOR",
    6: "AT EXTRUDER GEAR",
    7: "PAST EXTRUDER_GEAR",
    8: "HOMED AT TOOLHEAD SENSOR",
    9: "IN EXTRUDER",
   10: "LOADED IN NOZZLE",
}

DIRECTION_LOAD = 1
DIRECTION_UNKNOWN = 0
DIRECTION_UNLOAD = -1

# Standard sensor and endstop or pseudo endstop names
SENSOR_ENCODER           = "encoder"               # Fake Gate endstop using encoder
SENSOR_SHARED_EXIT       = "mmu_shared_exit"
SENSOR_EXIT_PREFIX       = "mmu_exit"

SENSOR_EXTRUDER_NONE     = "none"                  # Fake Extruder endstop aka don't attempt home
SENSOR_EXTRUDER_ENCODER  = "encoder"               # Fake Extruder endstop (uses encoder to detect collision)
SENSOR_EXTRUDER_ENTRY    = "extruder"              # Extruder entry sensor
SENSOR_GEAR_TOUCH        = "mmu_gear_touch"        # Stallguard based detection

SENSOR_COMPRESSION       = "filament_compression"  # Filament sync-feedback compression detection
SENSOR_TENSION           = "filament_tension"      # Filament sync-feedback tension detection
SENSOR_PROPORTIONAL      = "filament_proportional" # Proportional sync-feedback sensor

SENSOR_TOOLHEAD          = "toolhead"
SENSOR_EXTRUDER_TOUCH    = "mmu_ext_touch"

SENSOR_SELECTOR_TOUCH    = "mmu_sel_touch"  # For LinearSelector and LinearServoSelector
SENSOR_SELECTOR_HOME     = "mmu_sel_home"   # For LinearSelector and LinearServoSelector
SENSOR_ENTRY_PREFIX      = "mmu_entry"

# Old v3 endstop/sensor names
V3_SENSOR_GATE           = "mmu_gate"
V3_SENSOR_GEAR           = "mmu_gear"

# Standard symbolic color names
W3C_COLORS = {
    'aliceblue': '#F0F8FF',
    'antiquewhite': '#FAEBD7',
    'aqua': '#00FFFF',
    'aquamarine': '#7FFFD4',
    'azure': '#F0FFFF',
    'beige': '#F5F5DC',
    'bisque': '#FFE4C4',
    'black': '#000000',
    'blanchedalmond': '#FFEBCD',
    'blue': '#0000FF',
    'blueviolet': '#8A2BE2',
    'brown': '#A52A2A',
    'burlywood': '#DEB887',
    'cadetblue': '#5F9EA0',
    'chartreuse': '#7FFF00',
    'chocolate': '#D2691E',
    'coral': '#FF7F50',
    'cornflowerblue': '#6495ED',
    'cornsilk': '#FFF8DC',
    'crimson': '#DC143C',
    'cyan': '#00FFFF',
    'darkblue': '#00008B',
    'darkcyan': '#008B8B',
    'darkgoldenrod': '#B8860B',
    'darkgray': '#A9A9A9',
    'darkgreen': '#006400',
    'darkgrey': '#A9A9A9',
    'darkkhaki': '#BDB76B',
    'darkmagenta': '#8B008B',
    'darkolivegreen': '#556B2F',
    'darkorange': '#FF8C00',
    'darkorchid': '#9932CC',
    'darkred': '#8B0000',
    'darksalmon': '#E9967A',
    'darkseagreen': '#8FBC8F',
    'darkslateblue': '#483D8B',
    'darkslategray': '#2F4F4F',
    'darkslategrey': '#2F4F4F',
    'darkturquoise': '#00CED1',
    'darkviolet': '#9400D3',
    'deeppink': '#FF1493',
    'deepskyblue': '#00BFFF',
    'dimgray': '#696969',
    'dimgrey': '#696969',
    'dodgerblue': '#1E90FF',
    'firebrick': '#B22222',
    'floralwhite': '#FFFAF0',
    'forestgreen': '#228B22',
    'fuchsia': '#FF00FF',
    'gainsboro': '#DCDCDC',
    'ghostwhite': '#F8F8FF',
    'gold': '#FFD700',
    'goldenrod': '#DAA520',
    'gray': '#808080',
    'green': '#008000',
    'greenyellow': '#ADFF2F',
    'grey': '#808080',
    'honeydew': '#F0FFF0',
    'hotpink': '#FF69B4',
    'indianred': '#CD5C5C',
    'indigo': '#4B0082',
    'ivory': '#FFFFF0',
    'khaki': '#F0E68C',
    'lavender': '#E6E6FA',
    'lavenderblush': '#FFF0F5',
    'lawngreen': '#7CFC00',
    'lemonchiffon': '#FFFACD',
    'lightblue': '#ADD8E6',
    'lightcoral': '#F08080',
    'lightcyan': '#E0FFFF',
    'lightgoldenrodyellow': '#FAFAD2',
    'lightgray': '#D3D3D3',
    'lightgreen': '#90EE90',
    'lightgrey': '#D3D3D3',
    'lightpink': '#FFB6C1',
    'lightsalmon': '#FFA07A',
    'lightseagreen': '#20B2AA',
    'lightskyblue': '#87CEFA',
    'lightslategray': '#778899',
    'lightslategrey': '#778899',
    'lightsteelblue': '#B0C4DE',
    'lightyellow': '#FFFFE0',
    'lime': '#00FF00',
    'limegreen': '#32CD32',
    'linen': '#FAF0E6',
    'magenta': '#FF00FF',
    'maroon': '#800000',
    'mediumaquamarine': '#66CDAA',
    'mediumblue': '#0000CD',
    'mediumorchid': '#BA55D3',
    'mediumpurple': '#9370DB',
    'mediumseagreen': '#3CB371',
    'mediumslateblue': '#7B68EE',
    'mediumspringgreen': '#00FA9A',
    'mediumturquoise': '#48D1CC',
    'mediumvioletred': '#C71585',
    'midnightblue': '#191970',
    'mintcream': '#F5FFFA',
    'mistyrose': '#FFE4E1',
    'moccasin': '#FFE4B5',
    'navajowhite': '#FFDEAD',
    'navy': '#000080',
    'oldlace': '#FDF5E6',
    'olive': '#808000',
    'olivedrab': '#6B8E23',
    'orange': '#FFA500',
    'orangered': '#FF4500',
    'orchid': '#DA70D6',
    'palegoldenrod': '#EEE8AA',
    'palegreen': '#98FB98',
    'paleturquoise': '#AFEEEE',
    'palevioletred': '#DB7093',
    'papayawhip': '#FFEFD5',
    'peachpuff': '#FFDAB9',
    'peru': '#CD853F',
    'pink': '#FFC0CB',
    'plum': '#DDA0DD',
    'powderblue': '#B0E0E6',
    'purple': '#800080',
    'rebeccapurple': '#663399',
    'red': '#FF0000',
    'rosybrown': '#BC8F8F',
    'royalblue': '#4169E1',
    'saddlebrown': '#8B4513',
    'salmon': '#FA8072',
    'sandybrown': '#F4A460',
    'seagreen': '#2E8B57',
    'seashell': '#FFF5EE',
    'sienna': '#A0522D',
    'silver': '#C0C0C0',
    'skyblue': '#87CEEB',
    'slateblue': '#6A5ACD',
    'slategray': '#708090',
    'slategrey': '#708090',
    'snow': '#FFFAFA',
    'springgreen': '#00FF7F',
    'steelblue': '#4682B4',
    'tan': '#D2B48C',
    'teal': '#008080',
    'thistle': '#D8BFD8',
    'tomato': '#FF6347',
    'turquoise': '#40E0D0',
    'violet': '#EE82EE',
    'wheat': '#F5DEB3',
    'white': '#FFFFFF',
    'whitesmoke': '#F5F5F5',
    'yellow': '#FFFF00',
    'yellowgreen': '#9ACD32',
}

NO_FILAMENT_COLOR = '#808182E3'

COLOR_RED        = Gdk.RGBA(1,0,0,1)
COLOR_GREEN      = Gdk.RGBA(0,1,0,1)
COLOR_DARK_GREY  = Gdk.RGBA(0.2,0.2,0.2,1)
COLOR_LIGHT_GREY = Gdk.RGBA(0.5,0.5,0.5,1)
COLOR_ORANGE     = Gdk.RGBA(1,0.8,0,1)

COLOR_SWATCH = '⬤'
EMPTY_SWATCH = '◯'


class MmuMixin:

    def check_sensor(self, s):
        # v4...
        mmu = self._printer.get_stat("mmu")
        sensors = mmu.get('sensors')
        if sensors is not None:
            return sensors.get(s)

        # v3...
        sensor = self._printer.get_stat(f"filament_switch_sensor {s}_sensor")
        if sensor:
            if sensor['enabled']:
                return sensor['filament_detected']

        return None


    def has_sensor(self, s):
        # v4...
        mmu = self._printer.get_stat("mmu")
        sensors = mmu.get('sensors')
        if sensors is not None:
            if sensors.get(s) is not None:
                return True
            return False

        # v3...
        if s == SENSOR_SHARED_EXIT:
            s = V3_SENSOR_GATE
        elif s == SENSOR_EXIT:
            s = V3_SENSOR_GEAR
        sensor = self._printer.get_stat(f"filament_switch_sensor {s}_sensor")
        if sensor:
            return sensor['enabled']

        return False


    def has_encoder(self):
        # v4...
        mmu = self._printer.get_stat("mmu")
        encoder = mmu.get('encoder')
        if encoder is not None:
            return True

        # v3...
        encoder = self._printer.get_stat('mmu_encoder mmu_encoder', None)
        if encoder:
            return True

        return False


    def get_encoder_data(self):
        # v4...
        mmu = self._printer.get_stat("mmu")
        encoder = mmu.get('encoder')
        if encoder is not None:
            return encoder

        # v3...
        encoder = self._printer.get_stat('mmu_encoder mmu_encoder', None)
        if encoder:
            return encoder

        return {}


    def has_buffer(self):
        return any(
            self.has_sensor(sensor)
            for sensor in (
                SENSOR_COMPRESSION,
                SENSOR_TENSION,
                SENSOR_PROPORTIONAL,
            )
        )


    def get_selector_type(self):
        # >v3.1 method...
        mmu = self._printer.get_stat("mmu")
        gate = mmu['gate']
        mmu_unit = self.get_mmu_unit(gate)
        if mmu_unit is not None:
            return mmu_unit['selector_type']

        # v3.0...
        mmu = self._printer.get_stat("mmu")
        selector_type = mmu.get('selector_type', None)
        if selector_type:
            return selector_type

        # Prior to v3.0
        return 'LinearServoSelector'


    def get_mmu_unit(self, gate):
        mmu_machine = self._printer.get_stat("mmu_machine")
        if mmu_machine is None: return None

        if gate == TOOL_GATE_UNKNOWN:
            return mmu_machine['unit_0']

        for key, unit in mmu_machine.items():
            if not key.startswith("unit_"):
                continue

            if gate == TOOL_GATE_BYPASS:
                if unit.get("has_bypass", False):
                    return unit
                continue

            first_gate = unit["first_gate"]
            num_gates = unit["num_gates"]

            if first_gate <= gate < first_gate + num_gates:
                return unit

        return None


    def get_tools_for_gate(self, gate):
        mmu = self._printer.get_stat("mmu")
        ttg_map = mmu["ttg_map"]

        return [
            tool
            for tool, mapped_gate in enumerate(ttg_map)
            if mapped_gate == gate
        ]


    def get_endless_spool_group_order(self, gate):
        mmu = self._printer.get_stat("mmu")
        groups = mmu["endless_spool_groups"]
        if gate < 0 or gate >= len(groups):
            return []

        group = groups[gate]
        if group is None or group < 0:
            return [gate]

        gates = [
            g for g, gate_group in enumerate(groups)
            if gate_group == group
        ]

        if gate not in gates:
            return []

        i = gates.index(gate)
        return gates[i:] + gates[:i]


# -------------------------------------------------------------------------------------------
# Common helper/utilities methods
# -------------------------------------------------------------------------------------------

class MmuUtils:

    @staticmethod
    def parse_color(color):
        rgba = Gdk.RGBA()
        if color and rgba.parse(color):
            return rgba.red, rgba.green, rgba.blue, rgba.alpha
        return 0.502, 0.506, 0.510, 0.890 # #808182E3 convention I used in other UI's


    @staticmethod
    def get_rgb_color(gate_color):
        if gate_color and len(gate_color) == 8:
            try:
                int(gate_color, 16)
                gate_color = gate_color[:6]
            except ValueError:
                pass
        color = Gdk.RGBA()
        if not Gdk.RGBA.parse(color, gate_color.lower() if gate_color else ""):
            if not Gdk.RGBA.parse(color, '#' + gate_color if gate_color else ""):
                return "" # TODO: NO_FILAMENT_COLOR better?
        rgb_color = "#{:02x}{:02x}{:02x}".format(int(color.red * 255), int(color.green * 255), int(color.blue * 255))
        return rgb_color


    @staticmethod
    def filament_text_color(filament_color):
        """
        Returns an RGB tuple for text that contrasts with the filament color.

        Accepts CSS colors such as:
            #RRGGBB
            #RRGGBBAA
            #RGB
        """
        r, g, b, a = MmuUtils.parse_color(filament_color)

        # W3C relative luminance weighting.
        perceived_lightness = (
            r * 0.2126 +
            g * 0.7152 +
            b * 0.0722
        )

        if perceived_lightness > 0.6:
            return (0.13, 0.13, 0.13)   # #222222
        else:
            return (1.0, 1.0, 1.0)      # White
