"""
GPX functionality that isn't directly tied to a piece of the Pelican system.
"""

from datetime import datetime
import logging

import gpxpy
from pytz import timezone

from .constants import LOG_PREFIX

try:
    from timezonefinder import TimezoneFinder
except ImportError:
    try:
        from timezonefinderL import TimezoneFinder
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

    logger.debug(
        f"{INDENT}{len(cut_index):,} 'bad' point{'s' if len(cut_index) != 1 else ''} dropped."
    )

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


def combine_gpx(gpxes, log_name=None):
    """
    Combine a series of gpx files.

    Args:
    ----
        gpxes: assumed to be an interable of the XML of a GPX file
        log_name: name to display in the debug log

    """
    combined_gpx = None
    for raw_gpx in gpxes:
        gpx_data = gpxpy.parse(raw_gpx)
        if combined_gpx is None:
            combined_gpx = gpx_data
        else:
            for track in gpx_data.tracks:
                combined_gpx.tracks.append(track)

    if log_name:
        track_count = len(combined_gpx.tracks)
        segment_count = 0
        point_count = 0

        for track in combined_gpx.tracks:
            segment_count += len(track.segments)
            for segment in track.segments:
                point_count += len(segment.points)

        travel_length_km = combined_gpx.length_2d() / 1000

        logger.debug(
            "%s combined GPX for %s",
            LOG_PREFIX,
            log_name,
        )
        logger.debug(
            f"{INDENT}{track_count:,} track{'s' if track_count != 1 else ''}, "
            f"{segment_count:,} segment{'s' if segment_count != 1 else ''}, "
            f"and {point_count:,} point{'s' if point_count != 1 else ''}. "
            f"{travel_length_km:,.1f} km long."
        )
    return combined_gpx


def clip_gpx(lat1, long1, lat2, long2, gpx, heatmap_name):
    """
    Trims a GPX file to bounds specified by (lat1, long1) and (lat2, long2).

    Args:
        lat1 (float):
        long1 (float):
        lat2 (float):
        long2 (float):
        gpx (gpxpy.gpx):
        in_gpx_name (str): used in logging
        heatmap_name (str): used in logging
    """

    minlat, minlong, maxlat, maxlong = min_max_lat_long(lat1, long1, lat2, long2)

    cut_count = 0
    for track in gpx.tracks:
        for segment in track.segments:
            cut_index = []
            for index, point in enumerate(segment.points):
                if point.latitude < minlat or point.latitude > maxlat:
                    # remove point
                    cut_index.append(index)
                    cut_count = +1
                elif point.longitude < minlong or point.longitude > maxlong:
                    # remove point
                    cut_index.append(index)
                    cut_count = +1
            # remove duplicates
            cut_index = list(set(cut_index))
            # remove points from the end of the list first
            cut_index.sort(reverse=True)
            for index in cut_index:
                segment.remove_point(index)

    logger.debug(
        "%sTrimmed from %s, %s to %s, %s (%s). %s points removed.",
        INDENT,
        minlat,
        minlong,
        maxlat,
        maxlong,
        heatmap_name,
        cut_count,
    )
    return gpx


def generate_metadata(gpx, source_file, pelican_settings):
    if TimezoneFinder:
        tz_finder = TimezoneFinder()
    else:
        tz_finder = None

    latlong_bounds = gpx.get_bounds()
    elev_bounds = gpx.get_elevation_extremes()
    time_bounds = gpx.get_time_bounds()

    track_count = len(gpx.tracks)
    segment_count = 0
    point_count = 0

    for track in gpx.tracks:
        segment_count += len(track.segments)
        for segment in track.segments:
            point_count += len(segment.points)

    travel_length_km = gpx.length_2d() / 1000

    first_point = gpx.tracks[0].segments[0].points[0]
    last_point = gpx.tracks[-1].segments[-1].points[-1]

    if tz_finder:
        tz_start = timezone(
            tz_finder.timezone_at(lng=first_point.longitude, lat=first_point.latitude)
        )
        tz_end = timezone(
            tz_finder.timezone_at(lng=last_point.longitude, lat=last_point.latitude)
        )
    elif "TIMEZONE" in pelican_settings.keys():
        tz_start = tz_end = timezone(pelican_settings["TIMEZONE"])

    if tz_start and tz_end:
        start_time = time_bounds.start_time.astimezone(tz_start)
        end_time = time_bounds.end_time.astimezone(tz_end)
    else:
        # likely UTC
        start_time = time_bounds.start_time
        end_time = time_bounds.end_time

    logger.debug(f"{INDENT}Start date is {start_time}")
    logger.debug(
        f"{INDENT}{track_count:,} track{'s' if track_count != 1 else ''}, "
        f"{segment_count:,} segment{'s' if segment_count != 1 else ''}, "
        f"and {point_count:,} point{'s' if point_count != 1 else ''}. "
        f"{travel_length_km:,.1f} km long."
    )

    metadata = {
        "title": f"GPX track for {source_file.name}",
        "category": pelican_settings["GPX_CATEGORY"],
        "date": str(start_time),
        # "tags": [
        #     "tag_a",
        #     "tag_b",
        # ],
        "author": pelican_settings["GPX_AUTHOR"],
        "slug": f"{source_file.stem}".replace(".", "-"),
        "status": pelican_settings["GPX_STATUS"],
        "gpx_start_time": start_time,
        "gpx_end_time": end_time,
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
    }

    metadata["save_as"] = pelican_settings["GPX_SAVE_AS"].format(
        heatmap="default", **metadata
    )

    for k in pelican_settings["GPX_HEATMAPS"].keys():
        image_key = f"gpx_{k}_image"
        trimmed_gpx_key = f"gpx_{k}_trimmed"
        trimmed_gpx_save_as_key = f"gpx_{k}_save_as"

        metadata[image_key] = pelican_settings["GPX_IMAGE_SAVE_AS"].format(
            heatmap=k, **metadata
        )
        metadata[trimmed_gpx_save_as_key] = pelican_settings["GPX_SAVE_AS"].format(
            heatmap=k, **metadata
        )

        if pelican_settings["GPX_HEATMAPS"][k]["extent"] is None:
            metadata[trimmed_gpx_key] = gpx.to_xml()
        else:
            metadata[trimmed_gpx_key] = clip_gpx(
                *expand_trim_zone(
                    *[
                        float(x.removesuffix(","))
                        for x in pelican_settings["GPX_HEATMAPS"][k]["extent"].split(
                            " "
                        )
                    ]
                ),
                gpx,
                k,
            ).to_xml()

    metadata["date"] = str(metadata["date"])
    return metadata


def expand_trim_zone(lat1, long1, lat2, long2):
    """
    Given the "official" trim line (as will be used for the generated heatmap),
    expands the trim zone (as used by the GPX trimmer), so that (hopefully) all
    paths the cross the zone edge are included.

    Basic math is to add a 1/2 degree or 10% to each side, whichever is larger.
    """
    minlat, minlong, maxlat, maxlong = min_max_lat_long(lat1, long1, lat2, long2)

    delta_lat = maxlat - minlat
    delta_long = maxlong - minlong

    sigma_lat = 0.5 + (delta_lat - 1.0) * 0.1
    sigma_long = 0.5 + (delta_long - 1.0) * 0.1

    return (
        minlat - sigma_lat,
        minlong - sigma_long,
        maxlat + sigma_lat,
        maxlong + sigma_long,
    )


def min_max_lat_long(lat1, long1, lat2, long2):
    minlat = min(lat1, lat2)
    maxlat = max(lat1, lat2)
    minlong = min(long1, long2)
    maxlong = max(long1, long2)

    return minlat, minlong, maxlat, maxlong
