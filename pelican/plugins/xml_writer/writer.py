import logging
from posixpath import join as posix_join
from urllib.parse import urljoin

from pelican.writers import Writer

from .constants import LOG_PREFIX

logger = logging.getLogger(__name__)


class XMLWriter(Writer):
    """Pelican writer, extended to output XML files."""

    def __init__(self, output_path, settings=None):
        logger.debug("%s XMLWriter initialized" % LOG_PREFIX)
        try:
            super().__init__(output_path, settings=settings)
        except KeyError:
            # c.f https://github.com/getpelican/pelican/pull/2882
            self.output_path = output_path
            self.reminder = dict()
            self.settings = settings or {}
            self._written_files = set()
            self._overridden_files = set()

            # See Content._link_replacer for details
            if "RELATIVE_URLS" in self.settings and self.settings["RELATIVE_URLS"]:
                self.urljoiner = posix_join
            else:
                self.urljoiner = lambda base, url: urljoin(
                    base if base.endswith("/") else base + "/", url
                )

    def write_xml(self, xml, output_path):
        pass

    def write_heatmap(self, xml, output_path):
        pass
