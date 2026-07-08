"""
Theme-controlled dynamic background widget for KlipperScreen.

BackgroundManager displays a rotating image behind the main UI using the
application Gtk.Overlay. It is configured by the active theme's style.conf
file and supports theme-local background directories.

Images are loaded through KlipperScreen's existing image helpers and scaled
to cover the screen without stretching.
"""

import glob
import json
import logging
import os
import pathlib
import random
from collections import OrderedDict

from gi.repository import GdkPixbuf, GLib, Gtk

# Maximum number of fully scaled background images to retain.
#
# A cache size of 5 provides nearly instantaneous background changes while
# keeping memory usage around 10–15 MB at 1024×600. Increasing this value
# reduces image decode frequency at the expense of additional RAM.
DEFAULT_PIXBUF_CACHE_SIZE = 5


class BackgroundManager(Gtk.Image):
    """Theme-controlled slideshow background widget for KlipperScreen."""

    IMAGE_PATTERNS = ("*.png", "*.jpg", "*.jpeg", "*.webp")

    def __init__(self, screen):
        super().__init__()

        self.screen = screen
        self.settings = {
            "directory": "",
            "interval": 300,
            "mode": "random",
            "preload": False,
        }

        self.pixbuf_cache_limit = DEFAULT_PIXBUF_CACHE_SIZE
        self.images = []
        self.shuffle_bag = []
        self.index = -1
        self.timer = None
        self.enabled = False

        self.set_hexpand(True)
        self.set_vexpand(True)
        self.set_visible(False)
        self.state_file = os.path.expanduser("~/.config/KlipperScreen/background_state.json")
        self.pixbuf_cache = OrderedDict()
        self.pixbuf_cache_limit = 5

    def _load_state(self):
        try:
            with open(self.state_file) as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_state(self):
        try:
            os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
            state = self._load_state()
            state[self.screen.theme] = {"index": self.index}
            with open(self.state_file, "w") as f:
                json.dump(state, f)
        except Exception as e:
            logging.debug(f"BackgroundManager failed saving state: {e}")

    def _restore_index(self):
        state = self._load_state()
        theme_state = state.get(self.screen.theme, {})
        self.index = int(theme_state.get("index", -1))

        if self.images:
            self.index %= len(self.images)

    def configure(self, options):
        """Apply dynamic background settings from the active theme options."""
        bg = options.get("dynamic_background", {})

        self.settings["interval"] = int(bg.get("interval", 300))
        self.settings["mode"] = bg.get("mode", "random")

        self.set_image_directory(bg.get("directory", "backgrounds"))
        self.settings["preload"] = bool(bg.get("preload", False))

    def set_image_directory(self, directory):
        """Set the image directory, resolving relative paths inside the active theme."""
        image_dir = self._resolve_image_dir(directory)

        if image_dir != self.settings["directory"]:
            self.pixbuf_cache.clear()

        self.settings["directory"] = image_dir
        logging.debug(f"BackgroundManager image_dir = {self.settings['directory']}")

    def enable(self):
        """Enable the slideshow and start rotating backgrounds."""
        if self.enabled:
            return

        self.enabled = True
        self._find_images()
        self._restore_index()
        if self.settings["preload"]:
            self._prime_cache()
        self._show_next()
        self.set_visible(True)
        self._start_timer()

        logging.debug("BackgroundManager enabled")

    def disable(self):
        """Disable the slideshow and hide the background image."""
        if not self.enabled:
            self.clear()
            self.set_from_pixbuf(None)
            self.hide()
            return

        self.enabled = False
        self._stop_timer()
        self.clear()
        self.set_from_pixbuf(None)
        self.hide()

        logging.debug("BackgroundManager disabled")

    def rotate_background(self):
        if not self.enabled:
            return False

        self._show_next()
        return True

    def _resolve_image_dir(self, directory):
        if os.path.isabs(directory) or directory.startswith("~"):
            return os.path.expanduser(directory)

        klipperscreen_dir = pathlib.Path(__file__).parent.resolve().parent.parent

        return os.path.join(
            klipperscreen_dir,
            "styles",
            self.screen.theme,
            directory,
        )

    def _find_images(self):
        self.images = []

        if not os.path.isdir(self.settings["directory"]):
            logging.warning(f"BackgroundManager directory not found: {self.settings['directory']}")
            return

        for pattern in self.IMAGE_PATTERNS:
            self.images.extend(glob.glob(os.path.join(self.settings["directory"], pattern)))

        self.images.sort()
        self.index = -1
        self.shuffle_bag = []

        logging.debug(f"BackgroundManager found {len(self.images)} images")

    def _prime_cache(self):
        """
        Preload the pixbuf cache with the first N wallpapers.

        Only enough images to fill the configured cache are loaded. This reduces
        CPU usage during the first few background changes while maintaining a
        bounded memory footprint.
        """
        for path in self.images[: self.pixbuf_cache_limit]:
            self._load_pixbuf(path)

        logging.debug(f"BackgroundManager primed {len(self.pixbuf_cache)} cached wallpapers")

    def _show_next(self):
        path = self._get_next_image_path()

        if path is None:
            return

        pixbuf = self._load_pixbuf(path)

        if pixbuf is None:
            return

        self.set_from_pixbuf(pixbuf)
        self._save_state()
        # logging.debug(f"BackgroundManager showing {path}")

    def _get_next_image_path(self):
        if not self.images:
            return None

        mode = self.settings["mode"].lower()

        if mode == "random":
            return self._get_random_image_path()

        if mode == "sequential":
            return self._get_sequential_image_path()

        logging.warning(f"Unknown background mode '{mode}', using random")
        return self._get_random_image_path()

    def _get_random_image_path(self):
        if not self.shuffle_bag:
            self.shuffle_bag = list(range(len(self.images)))
            random.shuffle(self.shuffle_bag)
            # logging.debug("BackgroundManager reshuffling image order")

        self.index = self.shuffle_bag.pop()
        return self.images[self.index]

    def _get_sequential_image_path(self):
        self.index = (self.index + 1) % len(self.images)
        return self.images[self.index]

    def _load_pixbuf(self, path):
        cache_key = (
            path,
            self.screen.width,
            self.screen.height,
        )

        if cache_key in self.pixbuf_cache:
            self.pixbuf_cache.move_to_end(cache_key)
            return self.pixbuf_cache[cache_key]

        try:
            pixbuf = self.screen.gtk.PixbufFromFile(path)

            if pixbuf is None:
                return None

            pixbuf = self._scale_pixbuf_cover(
                pixbuf,
                self.screen.width,
                self.screen.height,
            )

            self.pixbuf_cache[cache_key] = pixbuf
            self.pixbuf_cache.move_to_end(cache_key)

            while len(self.pixbuf_cache) > self.pixbuf_cache_limit:
                self.pixbuf_cache.popitem(last=False)

            return pixbuf

        except Exception as e:
            logging.exception(f"BackgroundManager failed loading {path}: {e}")
            return None

    def _scale_pixbuf_cover(self, pixbuf, target_width, target_height):
        source_width = pixbuf.get_width()
        source_height = pixbuf.get_height()

        scale = max(
            target_width / source_width,
            target_height / source_height,
        )

        scaled_width = int(source_width * scale)
        scaled_height = int(source_height * scale)

        scaled = pixbuf.scale_simple(
            scaled_width,
            scaled_height,
            GdkPixbuf.InterpType.BILINEAR,
        )

        crop_x = int((scaled_width - target_width) / 2)
        crop_y = int((scaled_height - target_height) / 2)

        return scaled.new_subpixbuf(
            crop_x,
            crop_y,
            target_width,
            target_height,
        )

    def _start_timer(self):
        if self.timer is None:
            self.timer = GLib.timeout_add_seconds(
                self.settings["interval"],
                self.rotate_background,
            )

    def _stop_timer(self):
        if self.timer is not None:
            GLib.source_remove(self.timer)
            self.timer = None
