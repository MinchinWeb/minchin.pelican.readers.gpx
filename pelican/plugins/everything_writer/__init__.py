from pelican import signals as pelican_signals

from .constants import __version__
from .writer import EverythingWriter


def add_writer(pelican):
    return EverythingWriter


def register():
    """Register the plugin pieces with Pelican."""
    pelican_signals.get_writer.connect(add_writer)
