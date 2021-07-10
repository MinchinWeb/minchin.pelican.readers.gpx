import logging

from ._vendor.heatmap import heatmap

logger = logging.getLogger(__name__)

__title__ = "pelican.plugins.gpx_reader"
__version__ = "0.1.0+dev.1"
__description__ = "GPX Reader for Pelican"
__author__ = "William Minchin"
__email__ = "w_minchin@hotmail.com"
__url__ = "https://github.com/MinchinWeb/gpx_reader"
__license__ = "MIT License"


INDENT = " " * 4
LOG_PREFIX = "[GPX Reader]"
GPX_PATHS = [
    "gpx",
]  # source paths
GPX_EXCLUDES = list()
GPX_AUTHOR = "GPX Reader"
GPX_CATEGORY = "GPX"
GPX_STATUS = "published"
GPX_SIMPLIFY_DISTANCE = 5  # in meters
GPX_HEATMAPS = {"default": dict()}
GPX_SAVE_AS = "gpx/{slug}.gpx"
# YEAR_GPX_SAVE_AS = "gpx/combined/{date:%Y}.gpx"
# QUARTER_GPX_SAVE_AS = "gpx/combined/{date:%Y}-Q{quarter}.gpx"  # https://github.com/BetaS/datetime-quarter
# MONTH_GPX_SAVE_AS = "gpx/combined/{date:%Y}-{date:%m}.gpx"
# WEEK_GPX_SAVE_AS = "gpx/combined/{date:%G}-W{date:%V}.gpx"
# DAY_GPX_SAVE_AS = "gpx/combined/{date:%Y}-{date:%m}-{date:%d}.gpx"
GPX_IMAGE_SAVE_AS = "images/gpx/{heatmap}/{slug}.png"
# YEAR_GPX_IMAGE_SAVE_AS = "images/gpx/combined/{heatmap}/{date:%Y}.png"
# QUARTER_IMAGE_GPX_SAVE_AS = "images/gpx/combined/{heatmap}/{date:%Y}-Q{quarter}.png"
# MONTH_IMAGE_GPX_SAVE_AS = "images/gpx/combined/{heatmap}/{date:%Y}-{date:%m}.png"
# WEEK_IMAGE_GPX_SAVE_AS = "images/gpx/combined/{heatmap}/{date:%G}-W{date:%V}.png"
# DAY_IMAGE_GPX_SAVE_AS = "images/gpx/combined/{heatmap}/{date:%Y}-{date:%m}-{date:%d}.png"

# per heatmap
GPX_SCALE = 250  # meters per pixel (approx.)
GPX_BACKGROUND = "black"  # output image background
GPX_DECAY = 0.81  # between [0..1]
GPX_RADIUS = 3  # point radius, default is 5
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


def test_enabled(log=True):
    if heatmap:
        if log:
            logger.info(
                "%s enabled, version %s, heatmap version %s",
                LOG_PREFIX, __version__, heatmap.__version__
            )
        return True
    else:
        if log:
            logger.warn("%s disabled, version %s", LOG_PREFIX, __version__)
        return False
