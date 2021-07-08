from pelican import signals as pelican_signals

from .constants import __version__
from .generator import GPXArticleGenerator, GPXGenerator, display_stats
from .initialize import check_settings
from .reader import GPXReader


def add_reader(readers):
    readers.reader_classes["gpx"] = GPXReader


def add_generator(pelican):
    return GPXGenerator


def register():
    """Register the plugin pieces with Pelican."""
    pelican_signals.initialized.connect(check_settings)
    pelican_signals.readers_init.connect(add_reader)
    pelican_signals.get_generators.connect(add_generator)
    pelican_signals.finalized.connect(display_stats)
