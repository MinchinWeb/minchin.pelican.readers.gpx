from pelican import signals

from .constants import __version__
from .initialize import check_settings
from .reader import GPXReader


def add_reader(readers):
    readers.reader_classes["gpx"] = GPXReader


def register():
    """Register the plugin pieces with Pelican."""
    signals.initialized.connect(check_settings)
    signals.readers_init.connect(add_reader)
