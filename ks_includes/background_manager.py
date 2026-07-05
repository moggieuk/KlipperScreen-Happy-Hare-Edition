import glob
import logging
import os
import random

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

        self.set_hexpand(True)
        self.set_vexpand(True)

        self.load_images()
        self.rotate_background()

        GLib.timeout_add_seconds(self.interval, self.rotate_background)

    def load_images(self):
        patterns = ["*.png", "*.jpg", "*.jpeg", "*.webp"]
        self.images = []

        for pattern in patterns:
            self.images.extend(glob.glob(os.path.join(self.image_dir, pattern)))

        self.images.sort()
        logging.warning(f"BackgroundManager found {len(self.images)} images")

    def rotate_background(self):
        if not self.images:
            return True

        if self.randomize:
            path = random.choice(self.images)
        else:
            self.index = (self.index + 1) % len(self.images)
            path = self.images[self.index]

        try:
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                path,
                self.screen.width,
                self.screen.height,
                preserve_aspect_ratio=True,
            )
            self.set_from_pixbuf(pixbuf)
            logging.info(f"BackgroundManager showing {path}")
        except Exception as e:
            logging.exception(f"BackgroundManager failed loading {path}: {e}")

        return True