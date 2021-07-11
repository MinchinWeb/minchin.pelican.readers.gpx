import logging

from .constants import (
    ALL_GPX_SAVE_AS,
    DAY_GPX_SAVE_AS,
    GPX_AUTHOR,
    GPX_BACKGROUND,
    GPX_BACKGROUND_IMAGE,
    GPX_CATEGORY,
    GPX_DECAY,
    GPX_EXCLUDES,
    GPX_EXTENT,
    GPX_GRADIENT,
    GPX_HEATMAPS,
    GPX_HSVA_MAX,
    GPX_HSVA_MIN,
    GPX_IMAGE_SAVE_AS,
    GPX_KERNEL,
    GPX_PATHS,
    GPX_PROJECTION,
    GPX_RADIUS,
    GPX_SAVE_AS,
    GPX_SCALE,
    GPX_SIMPLIFY_DISTANCE,
    GPX_STATUS,
    LOG_PREFIX,
    MONTH_GPX_SAVE_AS,
    WEEK_GPX_SAVE_AS,
    YEAR_GPX_SAVE_AS,
)

logger = logging.getLogger(__name__)


def check_settings(pelican):
    """
    Insert defaults in Pelican settings, as needed.
    """
    logger.debug("%s massaging settings, setting defaults.", LOG_PREFIX)
    for key in [
        "ALL_GPX_SAVE_AS",
        "DAY_GPX_SAVE_AS",
        "GPX_AUTHOR",
        "GPX_CATEGORY",
        "GPX_EXCLUDES",
        "GPX_HEATMAPS",
        "GPX_IMAGE_SAVE_AS",
        "GPX_PATHS",
        "GPX_SAVE_AS",
        "GPX_SIMPLIFY_DISTANCE",
        "GPX_STATUS",
        "MONTH_GPX_SAVE_AS",
        "WEEK_GPX_SAVE_AS",
        "YEAR_GPX_SAVE_AS",

    ]:
        if key not in pelican.settings.keys():
            pelican.settings[key] = eval(key)

    # Append GPX_PATHS to ARTICLES_EXCLUDES
    for item in pelican.settings["GPX_PATHS"]:
        if item not in pelican.settings["ARTICLE_EXCLUDES"]:
            pelican.settings["ARTICLE_EXCLUDES"].append(item)
        if item not in pelican.settings["PAGE_EXCLUDES"]:
            pelican.settings["PAGE_EXCLUDES"].append(item)

    # if "compiled" in self.heatmaps.keys():
    #     logger.warn(
    #         "[GPX Reader] 'compiled' is invalid heatmap key for GPX_HEATMAPS. Ignoring..."
    #     )
    #     self.heatmaps.pop("compiled")

    # per heatmap settings
    for heatmap_name in pelican.settings["GPX_HEATMAPS"].keys():
        if pelican.settings["GPX_HEATMAPS"][heatmap_name] is None:
            pelican.settings["GPX_HEATMAPS"][heatmap_name] = dict()

        for heatmap_setting in [
            "scale",
            "background",
            "decay",
            "radius",
            "kernel",
            "projection",
            "gradient",
            "hsva_min",
            "hsva_max",
            "extent",
            "background_image",
        ]:
            if (
                not heatmap_setting
                in pelican.settings["GPX_HEATMAPS"][heatmap_name].keys()
            ):
                key_3 = f"GPX_{heatmap_setting.upper()}"
                if key_3 in pelican.settings:
                    pelican.settings["GPX_HEATMAPS"][heatmap_name][
                        heatmap_setting
                    ] = eval(f"pelican.settings['{key_3}']")
                else:
                    pelican.settings["GPX_HEATMAPS"][heatmap_name][
                        heatmap_setting
                    ] = eval(key_3)
