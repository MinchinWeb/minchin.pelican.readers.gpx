import logging
import os
from pathlib import Path
from posixpath import join as posix_join
from urllib.parse import urljoin

from pelican.utils import is_selected_for_writing
from pelican.writers import Writer

from . import signals
from .constants import LOG_PREFIX

logger = logging.getLogger(__name__)


class EverythingWriter(Writer):
    """Pelican writer, extended to output XML files."""

    def __init__(self, output_path, settings=None):
        logger.debug("%s initialized" % LOG_PREFIX)
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


    def write_xml(self, name, template, context, xml, override_output=False, **kwargs):
        """
        Write out an XML file.

        Args:
        -----
            name: output filename
            template: currently ignored
            context: dict that would normally be passed to the templates
            xml: raw XML to write to disk
            override_output: boolean telling if we can override previous output
                with the same name (and if next files written with the same
                name should be skipped to keep that one)
            **kwargs: currently ignored
        """
        if (
            name is False
            or name == ""
            or not name
            or not is_selected_for_writing(
                self.settings, os.path.join(self.output_path, name)
            )
        ):
            return

        localcontext = context.copy()
        localcontext["output_file"] = name
        localcontext.update(kwargs)

        output_file = Path(self.output_path).resolve() / name
        # create root folders, if they don't already exist
        output_file.parent.mkdir(exist_ok=True, parents=True)

        with self._open_w(output_file, "utf-8", override=override_output) as f:
            f.write(xml)

        logger.info("%s Writing XML %s" % (LOG_PREFIX, output_file))
        # Send a signal to say we're writing a file with some specific
        # local context.
        signals.xml_content_written.send(
            output_file,
            context=localcontext,
        )

    def write_heatmap(self, xml, output_path):
        pass
