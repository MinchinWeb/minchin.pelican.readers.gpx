from datetime import datetime
import logging

from pytz import timezone
try:
    from timezonefinder import TimezoneFinder
except ImportError:
    TimezoneFinder = None

from .constants import INDENT

logger = logging.getLogger(__name__)


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


def generate_metadata(gpx, source_file, pelican_settings, gpx_file_out):
    if TimezoneFinder:
        tz_finder = TimezoneFinder()
    else:
        tz_finder = None

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
    last_point = gpx.tracks[-1].segments[-1].points[-1]

    if tz_finder:
        tz_start = timezone(
            tz_finder.timezone_at(lng=first_point.longitude, lat=first_point.latitude)
        )
        start_time = time_bounds.start_time.astimezone(tz_start)

        tz_end = timezone(
            tz_finder.timezone_at(lng=last_point.longitude, lat=last_point.latitude)
        )
        end_time = time_bounds.end_time.astimezone(tz_end)
    else:
        # TODO: default to site timezone
        start_time = time_bounds.start_time
        end_time = time_bounds.end_time


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
