import glob
import logging
import os
import pathlib
import random
import json

from gi.repository import GdkPixbuf, GLib, Gtk


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
        }

        self.images = []
        self.index = -1
        self.timer = None
        self.enabled = False

        self.set_hexpand(True)
        self.set_vexpand(True)
        self.set_visible(False)
        self.state_file = os.path.expanduser("~/.config/KlipperScreen/background_state.json")

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
            state[self.screen.theme] = {
                "index": self.index
            }
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
    
    def set_image_directory(self, directory):
        """Set the image directory, resolving relative paths inside the active theme."""
        self.settings["directory"] = self._resolve_image_dir(directory)
        logging.debug(f"BackgroundManager image_dir = {self.settings['directory']}")

    def enable(self):
        """Enable the slideshow and start rotating backgrounds."""
        if self.enabled:
            return

        self.enabled = True
        self._find_images()
        self._restore_index()
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

        logging.debug(f"BackgroundManager found {len(self.images)} images")

    def _show_next(self):
        path = self._get_next_image_path()

        if path is None:
            return

        pixbuf = self._load_pixbuf(path)

        if pixbuf is None:
            return

        self.set_from_pixbuf(pixbuf)
        self._save_state()
        logging.debug(f"BackgroundManager showing {path}")

    def _get_next_image_path(self):
        if not self.images:
            return None

        mode = self.settings["mode"].lower()

        if mode == "random":
            self.index = random.randrange(len(self.images))
            return self.images[self.index]

        if mode == "sequential":
            self.index = (self.index + 1) % len(self.images)
            return self.images[self.index]

        logging.warning(f"Unknown background mode '{mode}', using random")
        self.index = random.randrange(len(self.images))
        return self.images[self.index]
        
    def _load_pixbuf(self, path):
        try:
            pixbuf = self.screen.gtk.PixbufFromFile(path)

            if pixbuf is None:
                return None

            return self._scale_pixbuf_cover(
                pixbuf,
                self.screen.width,
                self.screen.height,
            )

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