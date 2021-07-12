import logging
from pathlib import Path

from ._vendor.heatmap import heatmap
from .constants import INDENT

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


def generate_heatmap(gpx_file_in, heatmap_raw_settings):
    # hide heatmap logging calls
    old_logging_level = logging.getLogger().getEffectiveLevel()
    logging.getLogger().setLevel(logging.WARNING)

    heatmap_config = heatmap.Configuration()
    heatmap_options = heatmap_options_base(heatmap_raw_settings)
    heatmap_options.files = [
        str(Path(gpx_file_in).resolve()),
    ]
    heatmap_config.set_from_options(options=heatmap_options)
    heatmap_config.fill_missing()
    heatmap_matrix = heatmap.process_shapes(heatmap_config)
    heatmap_matrix = heatmap_matrix.finalized()
    heatmap_image = heatmap.ImageMaker(heatmap_config).make_image(heatmap_matrix)
    # reset logging level
    logging.getLogger().setLevel(old_logging_level)
    # logger.debug(f"{INDENT}Heatmap file at {heatmap_image_out}")

    return heatmap_image

    # heatmap_image.save(heatmap_image_out, format="png")

    # heatmap_image_buffer = BytesIO()
    # heatmap_image.save(heatmap_image_buffer, format="png")
    # heatmap_image_b64 = bytes(
    #     "data:image/png;base64,", encoding="utf-8"
    # ) + base64.b64encode(heatmap_image_buffer.getvalue())
    # return heatmap_image_b64
