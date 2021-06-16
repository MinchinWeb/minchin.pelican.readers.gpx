import logging
from pathlib import Path

import gpxpy

from pelican.readers import BaseReader
from pelican.utils import pelican_open

from .constants import INDENT, LOG_PREFIX, test_enabled
from .gpx import clean_gpx, generate_metadata, simplify_gpx
from .heatmap import generate_heatmap

logger = logging.getLogger(__name__)


class GPXReader(BaseReader):
    enabled = test_enabled(log=True)

    file_extensions = [
        "gpx",
    ]

    def read(self, source_filename):
        logger.debug("%s read file: %s" % (LOG_PREFIX, source_filename))

        # gpx_settings = MergedConfiguration(self.settings)

        source_file = Path(source_filename).resolve()

        gpx_file_out = (
            Path().cwd()
            / self.settings["OUTPUT_PATH"]
            / self.settings["GPX_OUTPUT_FOLDER"]
            / f"{source_file.stem}-cleaned.gpx"
        )

        # create gpx and image output folder if needed
        gpx_file_out.parent.mkdir(exist_ok=True)
        for k in self.settings["GPX_HEATMAPS"].keys():
            heatmap_folder = (
                Path().cwd()
                / self.settings["OUTPUT_PATH"]
                / self.settings["GPX_OUTPUT_FOLDER"]
                / k
            )
            heatmap_folder.mkdir(exist_ok=True)

        # with pelican_open(source_filename) as fn:
        with pelican_open(source_file) as fn:
            gpx = gpxpy.parse(fn)

        clean_gpx(gpx)
        simplify_gpx(gpx, self.settings)

        logger.debug(f"{INDENT}GPX cleaned file at {gpx_file_out}")
        with gpx_file_out.open(mode="w") as fn:
            print(gpx.to_xml(), file=fn)

        for k in self.settings["GPX_HEATMAPS"].keys():
            heatmap_image_out = (
                Path().cwd()
                / self.settings["OUTPUT_PATH"]
                / self.settings["GPX_OUTPUT_FOLDER"]
                / k
                / f"{source_file.stem}.png"
            )

            generate_heatmap(
                gpx_file_in=gpx_file_out,
                heatmap_image_out=heatmap_image_out,
                heatmap_raw_settings=self.settings["GPX_HEATMAPS"][k],
            )

        metadata, start_time, end_time = generate_metadata(
            gpx=gpx,
            source_file=source_file,
            pelican_settings=self.settings,
            gpx_file_out=gpx_file_out,
        )

        parsed_metadata = {}
        for key, value in metadata.items():
            key = key.lower()
            parsed_metadata[key] = self.process_metadata(key, value)

        content = f"""
        <div class="article-body">
            <div class="gpx-details">
                <p>gpx file: {source_file.name}</p>
                <p>
                    Runs from {start_time} to {end_time}.
                    Contains {metadata["gpx_tracks"]:,} track(s),
                    {metadata["gpx_segments"]:,} segment(s),
                    and {metadata["gpx_points"]:,} points.
                    Minimum elevation of {metadata["gpx_min_elevation"]:,.1f} m and
                    maximum of  {metadata["gpx_max_elevation"]:,.1f} m.
                    Latitude and longitude bounds of
                    {abs(metadata["gpx_min_latitude"]):.3f}&deg;{'N' if metadata["gpx_min_latitude"] >= 0 else 'S'},
                    {abs(metadata["gpx_min_longitude"]):.3f}&deg;{'E' if metadata["gpx_min_longitude"] >= 0 else 'W'} and 
                    {abs(metadata["gpx_max_latitude"]):.3f}&deg;{'N' if metadata["gpx_max_latitude"] >= 0 else 'S'},
                    {abs(metadata["gpx_max_longitude"]):.3f}&deg;{'E' if metadata["gpx_max_longitude"] >= 0 else 'W'}.
                    Travel distance of {metadata["gpx_length_km"]:,.1f}&nbsp;km.
                </p>
            </div>
        """

        for k in self.settings["GPX_HEATMAPS"].keys():
            content += f"""
            <div class="gpx-image gpx-image-{k}">
                <img src="{self.settings["SITEURL"]}/{self.settings["GPX_OUTPUT_FOLDER"]}/{k}/{source_file.stem}.png" alt="{k} GPX track for {source_file.name}" />
            </div>
        """

        content += """
        </div>
       """

        return content, parsed_metadata
