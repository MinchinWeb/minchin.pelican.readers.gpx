import logging
from datetime import datetime
from pathlib import Path

from pelican import signals
from pelican.readers import BaseReader
from pelican.utils import pelican_open

try:
    import gpxpy

    from ._vendor.heatmap import heatmap
except ImportError:
    heatmap = None
    gpxpy = None


__title__ = "pelican.plugins.gpx_reader"
__version__ = "0.1.0+dev.0"
__description__ = "GPX Reader for Pelican"
__author__ = "William Minchin"
__email__ = "w_minchin@hotmail.com"
__url__ = "https://github.com/MinchinWeb/gpx_reader"
__license__ = "MIT License"


INDENT = " " * 4
GPX_SIMPLIFY_DISTANCE = 5  # in meters
GPX_SCALE = 250  # meters per pixel (approx.)
GPX_BACKGROUND = "black"  # output image background
GPX_DECAY = 0.81  # between [0..1]
GPX_RADIUS = 3  # point radius, default is 5
GPX_OUTPUT_FOLDER = "gpx"
GPX_KERNEL = "linear"
GPX_PROJECTION = "mercator"
GPX_GRADIENT = None
if heatmap:
    GPX_HSVA_MIN = heatmap.ColorMap().DEFAULT_HSVA_MIN_STR
    GPX_HSVA_MAX = heatmap.ColorMap().DEFAULT_HSVA_MAX_STR
else:
    GPX_HSVA_MIN = None
    GPX_HSVA_MAX = None
GPX_EXTENT = None
GPX_BACKGROUND_IMAGE = None


logger = logging.getLogger(__name__)


class GPXReader(BaseReader):

    # can test for project requirements before enabling
    if heatmap:
        enabled = True
        logger.info("[GPX Reader] enabled, heatmap version %s" % heatmap.__version__)
    else:
        enabled = False
        logger.warn("[GPX Reader] disabled")

    file_extensions = [
        "gpx",
    ]

    # def __init__(self, *args, **kwargs):
    #     super().__init__(*args, **kwargs)
    #     settings = self.settings['GPX']
    #     # settings.setdefault('extensions', [])

    def read(self, source_filename):
        logger.debug("[GPX Reader] file: %s" % source_filename)

        source_file = Path(source_filename).resolve()

        gpx_file_out = (
            Path().cwd()
            / (self.settings["OUTPUT_PATH"])
            / GPX_OUTPUT_FOLDER
            / (f"{source_file.stem}-cleaned.gpx")
        )
        heatmap_image_out = (
            Path().cwd()
            / (self.settings["OUTPUT_PATH"])
            / GPX_OUTPUT_FOLDER
            / (f"{source_file.stem}.png")
        )
        # create gpx output folder if needed
        gpx_file_out.parent.mkdir(exist_ok=True)

        # with pelican_open(source_filename) as fn:
        with pelican_open(source_file) as fn:
            gpx = gpxpy.parse(fn)

        first_point_datetime = None
        for track in gpx.tracks:
            for segment in track.segments:
                for point in segment.points:
                    first_point_datetime = point.time
                    if first_point_datetime:
                        break
                if first_point_datetime:
                    break
            if first_point_datetime:
                break

        if first_point_datetime is None:
            first_point_datetime = datetime.fromtimestamp(source_file.stat().st_ctime)
        # drop sub-seconds
        first_point_datetime = first_point_datetime.replace(microsecond=0)

        logger.debug(f"{INDENT}start date is {first_point_datetime}")

        last_point_datetime = None
        for track in reversed(gpx.tracks):
            for segment in reversed(track.segments):
                for point in reversed(segment.points):
                    last_point_datetime = point.time
                    if last_point_datetime:
                        break
                if last_point_datetime:
                    break
            if last_point_datetime:
                break

        track_count = len(gpx.tracks)
        segment_count = 0
        point_count = 0

        for track in gpx.tracks:
            segment_count += len(track.segments)
            for segment in track.segments:
                point_count += len(segment.points)

        logger.debug(
            f"{INDENT}{track_count:,} track(s), {segment_count:,} segment(s), and {point_count:,} points."
        )

        # clean from basic issues
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

        # see GPXTrackSegment.simplify(self, max_distance=None)
        #   max_distance is the distance from the simplified line
        # uses http://en.wikipedia.org/wiki/Ramer%E2%80%93Douglas%E2%80%93Peucker_algorithm
        for i2, track in enumerate(gpx.tracks):
            for i3, segment in enumerate(track.segments):
                in_points = len(segment.points)
                segment.simplify(max_distance=GPX_SIMPLIFY_DISTANCE)
                out_points = len(segment.points)
                cut = in_points - out_points
                if cut > 0:
                    logger.debug(
                        f"{INDENT}{i2},{i3} - Simplified, {cut:,} points removed."
                    )

        travel_length_km = gpx.length_2d()/1000
        logger.debug(f"{INDENT}travel length: {travel_length_km:,.1f} km")

        logger.debug(f"{INDENT}GPX cleaned file at {gpx_file_out}")
        with gpx_file_out.open(mode="w") as fn:
            print(gpx.to_xml(), file=fn)

        class heatmap_options_base(object):
            def __init__(self):
                self.scale = GPX_SCALE
                self.background = GPX_BACKGROUND
                self.decay = GPX_DECAY
                self.radius = GPX_RADIUS
                # self.kernel= heatmap.LinearKernel
                # self.extent=
                self.filetype = "gpx"

                ## defaults
                self.kernel = GPX_KERNEL
                self.projection = GPX_PROJECTION
                self.gradient = GPX_GRADIENT
                self.hsva_min = GPX_HSVA_MIN
                self.hsva_max = GPX_HSVA_MAX
                self.points = None
                self.gpx = None
                self.csv = None
                self.shp_file = None
                self.extent = GPX_EXTENT
                self.background_image = GPX_BACKGROUND_IMAGE

        # hide heatmap logging calls
        old_logging_level = logging.getLogger().getEffectiveLevel()
        logging.getLogger().setLevel(logging.WARNING)
        heatmap_config = heatmap.Configuration()
        heatmap_options = heatmap_options_base()
        heatmap_options.files = [
            str(gpx_file_out.resolve()),
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

        metadata = {
            "title": f"GPX track for {source_file.name}",
            "category": "GPX",
            "date": str(first_point_datetime),
            # "tags": [
            #     "tag_a",
            #     "tag_b",
            # ],
            "author": "GPX Reader",
            "slug": f"{source_file.name}".replace(".", "-"),
            "status": "published",
            "gpx_start": first_point_datetime,
            "gpx_end": last_point_datetime,
            "gpx_tracks": track_count,
            "gpx_segments": segment_count,
            "gpx_points": point_count,
            "gpx_length_km": travel_length_km,
            "gpx_cleaned_file": f"{GPX_OUTPUT_FOLDER}/{gpx_file_out.name}",
            "gpx_image": f"{GPX_OUTPUT_FOLDER}/{heatmap_image_out.name}",
            # "gpx_image_b64": heatmap_image_b64,
        }

        parsed_metadata = {}
        for key, value in metadata.items():
            key = key.lower()
            parsed_metadata[key] = self.process_metadata(key, value)

        content = f"""
        <div class="article-body">
            <div class="gpx-details">
                <p>gpx file: {source_file.name}</p>
                <p>
                    Runs from {first_point_datetime} to {last_point_datetime}.
                    Contains {track_count:,} track(s), {segment_count:,} segment(s),
                    and {point_count:,} points.
                    Travel distance of {travel_length_km:,.1f}&nbsp;km.
                </p>
            </div>
            <div class="gpx-image">
                <img src="{self.settings["SITEURL"]}/{GPX_OUTPUT_FOLDER}/{heatmap_image_out.name}" alt="GPX track for {source_file.name}" />
            </div>
        </div>
       """

        return content, parsed_metadata


def add_reader(readers):
    readers.reader_classes["gpx"] = GPXReader


def register():
    signals.readers_init.connect(add_reader)
