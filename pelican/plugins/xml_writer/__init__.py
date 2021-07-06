from pelican import signals

from .constants import __version__
from .writer import XMLWriter


def register():
    """Register the plugin pieces with Pelican."""
    signals.get_writer.connect(XMLWriter)
