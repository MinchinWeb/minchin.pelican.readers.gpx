from datetime import datetime
import logging
from pathlib import Path

import gpxpy
from pytz import timezone
from timezonefinder import TimezoneFinder

from pelican import signals
from pelican.readers import BaseReader
from pelican.utils import pelican_open

from ._vendor.heatmap import heatmap
from .initialize import check_settings
from .constants import __version__, INDENT, LOG_PREFIX


logger = logging.getLogger(__name__)


class heatmap_options_base(object):
    def __init__(self, heatmap_settings):
        self.scale = heatmap_settings["scale"]
        self.background = heatmap_settings["background"]
        self.decay = heatmap_settings["decay"]
        self.radius = heatmap_settings["radius"]
        # self.kernel= heatmap.LinearKernel
        # self.extent=
        self.filetype = "gpx"

        ## defaults
        self.kernel = heatmap_settings["kernel"]
        self.projection = heatmap_settings["projection"]
        self.gradient = heatmap_settings["gradient"]
        self.hsva_min = heatmap_settings["hsva_min"]
        self.hsva_max = heatmap_settings["hsva_max"]
        self.points = None
        self.gpx = None
        self.csv = None
        self.shp_file = None
        self.extent = heatmap_settings["extent"]
        self.background_image = heatmap_settings["background_image"]


def clean_gpx(gpx):  # clean from basic issues
    for track in gpx.tracks:
        for segment in track.segments:
            cut_index = []
            for index, point in enumerate(segment.points):
                # Clear away points without a date (actually 1970-1-1)
                if point.time == datetime(1970, 1, 1):
                    cut_index.append(index)

                # Clear point if at 0N 0E
                if point.latitude == 0 and point.longitude == 0:
                    cut_index.append(index)

                # <src>network</src>
                if point.source == "network":
                    cut_index.append(index)

            # remove duplicates
            cut_index = list(set(cut_index))
            # remove points from the end of the list first
            cut_index.sort(reverse=True)
            for index in cut_index:
                segment.remove_point(index)

    logger.debug(f"{INDENT}{len(cut_index):,} 'bad' points dropped.")

    return gpx


def simplify_gpx(gpx, pelican_settings):
    # see GPXTrackSegment.simplify(self, max_distance=None)
    #   max_distance is the distance from the simplified line
    # uses http://en.wikipedia.org/wiki/Ramer%E2%80%93Douglas%E2%80%93Peucker_algorithm
    for i2, track in enumerate(gpx.tracks):
        for i3, segment in enumerate(track.segments):
            in_points = len(segment.points)
            segment.simplify(max_distance=pelican_settings["GPX_SIMPLIFY_DISTANCE"])
            out_points = len(segment.points)
            cut = in_points - out_points
            if cut > 0:
                logger.debug(f"{INDENT}{i2},{i3} - Simplified, {cut:,} points removed.")

    return gpx


def generate_heatmap(gpx_file_in, heatmap_image_out, heatmap_raw_settings):
    # hide heatmap logging calls
    old_logging_level = logging.getLogger().getEffectiveLevel()
    logging.getLogger().setLevel(logging.WARNING)

    heatmap_config = heatmap.Configuration()
    heatmap_options = heatmap_options_base(heatmap_raw_settings)
    heatmap_options.files = [
        str(gpx_file_in.resolve()),
    ]
    heatmap_config.set_from_options(options=heatmap_options)
    heatmap_config.fill_missing()
    heatmap_matrix = heatmap.process_shapes(heatmap_config)
    heatmap_matrix = heatmap_matrix.finalized()
    heatmap_image = heatmap.ImageMaker(heatmap_config).make_image(heatmap_matrix)
    # reset logging level
    logging.getLogger().setLevel(old_logging_level)
    logger.debug(f"{INDENT}Heatmap file at {heatmap_image_out}")

    heatmap_image.save(heatmap_image_out, format="png")
    # heatmap_image_buffer = BytesIO()
    # heatmap_image.save(heatmap_image_buffer, format="png")
    # heatmap_image_b64 = bytes(
    #     "data:image/png;base64,", encoding="utf-8"
    # ) + base64.b64encode(heatmap_image_buffer.getvalue())
    # return heatmap_image_b64


def generate_metadata(gpx, source_file, pelican_settings, gpx_file_out):
    tz_finder = TimezoneFinder()

    latlong_bounds = gpx.get_bounds()
    elev_bounds = gpx.get_elevation_extremes()
    time_bounds = gpx.get_time_bounds()

    logger.debug(f"{INDENT}start date is {time_bounds.start_time}")

    track_count = len(gpx.tracks)
    segment_count = 0
    point_count = 0

    for track in gpx.tracks:
        segment_count += len(track.segments)
        for segment in track.segments:
            point_count += len(segment.points)

    logger.debug(
        f"{INDENT}{track_count:,} track(s), {segment_count:,} segment(s), "
        f"and {point_count:,} points."
    )

    travel_length_km = gpx.length_2d() / 1000
    logger.debug(f"{INDENT}travel length: {travel_length_km:,.1f} km")

    first_point = gpx.tracks[0].segments[0].points[0]
    tz_start = timezone(
        tz_finder.timezone_at(lng=first_point.longitude, lat=first_point.latitude)
    )
    start_time = time_bounds.start_time.astimezone(tz_start)

    last_point = gpx.tracks[-1].segments[-1].points[-1]
    tz_end = timezone(
        tz_finder.timezone_at(lng=last_point.longitude, lat=last_point.latitude)
    )
    end_time = time_bounds.end_time.astimezone(tz_end)

    metadata = {
        "title": f"GPX track for {source_file.name}",
        "category": pelican_settings["GPX_CATEGORY"],
        "date": str(start_time),
        # "tags": [
        #     "tag_a",
        #     "tag_b",
        # ],
        "author": pelican_settings["GPX_AUTHOR"],
        "slug": f"{source_file.name}".replace(".", "-"),
        "status": pelican_settings["GPX_STATUS"],
        "gpx_start_time": time_bounds.start_time,
        "gpx_end_time": time_bounds.end_time,
        "gpx_min_elevation": elev_bounds.minimum,
        "gpx_max_elevation": elev_bounds.maximum,
        "gpx_min_latitude": latlong_bounds.min_latitude,
        "gpx_min_longitude": latlong_bounds.min_longitude,
        "gpx_max_latitude": latlong_bounds.max_latitude,
        "gpx_max_longitude": latlong_bounds.max_longitude,
        "gpx_tracks": track_count,
        "gpx_segments": segment_count,
        "gpx_points": point_count,
        "gpx_length_km": travel_length_km,
        "gpx_cleaned_file": f'{pelican_settings["GPX_OUTPUT_FOLDER"]}/{gpx_file_out.name}',
        # "gpx_image_b64": heatmap_image_b64,
    }

    for k in pelican_settings["GPX_HEATMAPS"].keys():
        image_key = f"gpx_{k}_image"
        metadata[
            image_key
        ] = f'{pelican_settings["GPX_OUTPUT_FOLDER"]}/{k}/{source_file.stem}.png'

    return metadata, start_time, end_time


class GPXReader(BaseReader):
    # can test for project requirements before enabling
    if heatmap:
        enabled = True
        logger.info(
            "%s enabled, version %s, heatmap version %s"
            % (LOG_PREFIX, __version__, heatmap.__version__)
        )
    else:
        enabled = False
        logger.warn("%s disabled, version %s" % (LOG_PREFIX, __version__))

    file_extensions = [
        "gpx",
    ]

    def read(self, source_filename):
        logger.debug("%s file: %s" % (LOG_PREFIX, source_filename))

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


def add_reader(readers):
    readers.reader_classes["gpx"] = GPXReader


def register():
    """Register the plugin pieces with Pelican."""
    signals.initialized.connect(check_settings)
    signals.readers_init.connect(add_reader)
