import logging
from pathlib import Path

import gpxpy

from pelican.readers import BaseReader
from pelican.utils import pelican_open

from .constants import INDENT, LOG_PREFIX, test_enabled
from .exceptions import TooShortGPXException
from .gpx import clean_gpx, generate_metadata, simplify_gpx, get_start_end_times

logger = logging.getLogger(__name__)


class GPXReader(BaseReader):
    """
    Pelican Reader for GPX files.

    Rather than returning HTML (as is typically done with Pelican), it returns
    the (raw, but cleaned) XML of the GPX file.
    """

    enabled = test_enabled(log=True)
    file_extensions = [
        "gpx",
    ]
    extensions = None

    def read(self, source_path):
        # TODO: Show relative path?
        logger.debug("%s read file: %s", LOG_PREFIX, source_path)

        source_file = Path(source_path).resolve()
        with pelican_open(source_file) as fn:
            gpx = gpxpy.parse(fn)

        clean_gpx(gpx)
        simplify_gpx(gpx, self.settings)

        content = gpx.to_xml()

        try:
            metadata = generate_metadata(
                gpx=gpx,
                source_file=source_file,
                pelican_settings=self.settings,
            )
        except TooShortGPXException as e:
            logger.info(
                "%sGPX tracks is too short. Skipping file (%s)",
                INDENT,
                source_file.name,
            )
            # dummy information to keep Pelican from crashing, but to skip this
            # file
            start_time, _ = get_start_end_times(gpx=gpx, pelican_settings=self.settings)
            return None, {
                "title": f"GPX track for {source_file.name}",
                "date": start_time,
                "heatmap": None,
                "valid": False,
            }

        parsed_metadata = {}
        for key, value in metadata.items():
            key = key.lower()
            parsed_metadata[key] = self.process_metadata(key, value)

        return content, parsed_metadata
