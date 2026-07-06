import glob
import logging
import os
import pathlib
import random

from gi.repository import GLib, Gtk


class BackgroundManager(Gtk.Image):
    """Theme-controlled slideshow background widget for KlipperScreen."""
    IMAGE_PATTERNS = ("*.png", "*.jpg", "*.jpeg", "*.webp")

    def __init__(self, screen):
        super().__init__()

        self.screen = screen
        self.image_dir = ""
        self.interval = 300
        self.randomize = True

        self.images = []
        self.index = -1
        self.timer = None
        self.enabled = False

        self.set_hexpand(True)
        self.set_vexpand(True)
        self.set_visible(False)

    def configure(self, options):
        """Apply dynamic background settings from the active theme options."""
        bg = options.get("dynamic_background", {})

        self.interval = int(bg.get("interval", 300))
        self.randomize = bool(bg.get("random", True))

        self.set_image_directory(bg.get("directory", "backgrounds"))
    
    def set_image_directory(self, directory):
        """Set the image directory, resolving relative paths inside the active theme."""
        self.image_dir = self._resolve_image_dir(directory)
        logging.debug(f"BackgroundManager image_dir = {self.image_dir}")

    def enable(self):
        """Enable the slideshow and start rotating backgrounds."""
        if self.enabled:
            return

        self.enabled = True
        self._find_images()
        self._show_next()
        self.set_visible(True)
        self._start_timer()

        logging.debug("BackgroundManager enabled")

    def disable(self):
        """Disable the slideshow and hide the background image."""
        if not self.enabled:
            return

        self.enabled = False
        self.clear()
        self.set_visible(False)
        self._stop_timer()

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

        if not os.path.isdir(self.image_dir):
            logging.warning(f"BackgroundManager directory not found: {self.image_dir}")
            return

        for pattern in self.IMAGE_PATTERNS:
            self.images.extend(glob.glob(os.path.join(self.image_dir, pattern)))

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
        logging.debug(f"BackgroundManager showing {path}")

    def _get_next_image_path(self):
        if not self.images:
            return None

        if self.randomize:
            return random.choice(self.images)

        self.index = (self.index + 1) % len(self.images)
        return self.images[self.index]

    def _load_pixbuf(self, path):
        try:
            return self.screen.gtk.PixbufFromFile(
                path,
                self.screen.width,
                self.screen.height,
            )
        except Exception as e:
            logging.exception(f"BackgroundManager failed loading {path}: {e}")
            return None

    def _start_timer(self):
        if self.timer is None:
            self.timer = GLib.timeout_add_seconds(self.interval, self.rotate_background)

    def _stop_timer(self):
        if self.timer is not None:
            GLib.source_remove(self.timer)
            self.timer = None