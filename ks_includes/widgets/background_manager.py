import glob
import logging
import os
import random
import pathlib

from gi.repository import GdkPixbuf, GLib, Gtk


class BackgroundManager(Gtk.Image):
    def __init__(self, screen):
        super().__init__()

        self.screen = screen
        self.image_dir = os.path.expanduser("~/backgrounds")
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
        bg = options.get("dynamic_background", {})

        directory = bg.get("directory", "backgrounds")

        if os.path.isabs(directory) or directory.startswith("~"):
            self.image_dir = os.path.expanduser(directory)
        else:
            self.image_dir = os.path.join(
                pathlib.Path(__file__).parent.resolve().parent.parent,
                "styles",
                self.screen.theme,
                directory,
            )
            logging.warning(f"BackgroundManager image_dir = {self.image_dir}")

        self.interval = int(bg.get("interval", 300))
        self.randomize = bool(bg.get("random", True))

    def enable(self):
        if self.enabled:
            return

        self.enabled = True
        self.load_images()
        self.rotate_background()
        self.set_visible(True)

        if self.timer is None:
            self.timer = GLib.timeout_add_seconds(self.interval, self.rotate_background)

        logging.warning("BackgroundManager enabled")

    def disable(self):
        if not self.enabled:
            return

        self.enabled = False
        self.clear()
        self.set_visible(False)

        if self.timer is not None:
            GLib.source_remove(self.timer)
            self.timer = None

        logging.warning("BackgroundManager disabled")

    def load_images(self):
        patterns = ["*.png", "*.jpg", "*.jpeg", "*.webp"]
        self.images = []

        for pattern in patterns:
            self.images.extend(glob.glob(os.path.join(self.image_dir, pattern)))

        self.images.sort()
        logging.warning(f"BackgroundManager found {len(self.images)} images")

    def rotate_background(self):
        if not self.enabled:
            return False

        if not self.images:
            return True

        if self.randomize:
            path = random.choice(self.images)
        else:
            self.index = (self.index + 1) % len(self.images)
            path = self.images[self.index]

        try:
            pixbuf = self.screen.gtk.PixbufFromFile(
                path,
                self.screen.width,
                self.screen.height,
            )
            if pixbuf is not None:
                self.set_from_pixbuf(pixbuf)
                logging.warning(f"BackgroundManager showing {path}")
        except Exception as e:
            logging.exception(f"BackgroundManager failed loading {path}: {e}")

        return True