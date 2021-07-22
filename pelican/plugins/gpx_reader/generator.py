import calendar
from datetime import datetime
from functools import partial
from itertools import groupby
import logging
from operator import attrgetter
from pathlib import Path

from pelican.generators import ArticlesGenerator, CachingGenerator
from pelican.utils import order_content

from . import signals
from .constants import LOG_PREFIX
from .contents import GPX as GPXContent
from .gpx import combine_gpx
from .hasher import gpx_hash
from .heatmap import generate_heatmap

logger = logging.getLogger(__name__)
gpx_count = 0

period_date_key = {
    "all": None,
    "year": attrgetter("date.year"),
    "month": attrgetter("date.year", "date.month"),
    "week": lambda gpx_content: (
        gpx_content.date.isocalendar().year,
        gpx_content.date.isocalendar().week,
    ),
    "day": attrgetter("date.year", "date.month", "date.day"),
}


class GPXArticleGenerator(ArticlesGenerator):
    def generate_pages(self, writer):
        """Generate the pages on the disk"""
        logger.debug("%s Article Generator: generate pages", LOG_PREFIX)

        write = partial(writer.write_file, relative_urls=self.settings["RELATIVE_URLS"])

        # # to minimize the number of relative path stuff modification
        # # in writer, articles pass first
        # self.generate_articles(write)
        # self.generate_period_archives(write)
        # self.generate_direct_templates(write)

        # # and subfolders after that
        # self.generate_tags(write)
        # self.generate_categories(write)
        # self.generate_authors(write)
        # self.generate_drafts(write)


class GPXGenerator(CachingGenerator):
    def __init__(self, *args, **kwargs):
        """initialize properties"""
        self.gpxes = []
        self.dates = {}

        super().__init__(*args, **kwargs)
        signals.gpx_generator_init.send(self)

    def generate_context(self):
        """
        Called by Pelican to fill context.

        Context is the metadata about all the pages/articles/etc that is
        offered up to the templating engine.
        """
        all_gpxes = []

        for fn in self.get_files(
            self.settings["GPX_PATHS"], exclude=self.settings["GPX_EXCLUDES"]
        ):
            gpx = self.get_cached_data(fn, None)
            if gpx is None:
                try:
                    gpx = self.readers.read_file(
                        base_path=self.path,
                        path=fn,
                        content_class=GPXContent,
                        fmt="gpx",
                        context=self.context,
                        preread_signal=signals.gpx_generator_preread,
                        preread_sender=self,
                        context_signal=signals.gpx_generator_context,
                        context_sender=self,
                    )
                except Exception as e:
                    logger.error(
                        "Could not process %s\n%s",
                        fn,
                        e,
                        exc_info=self.settings.get("DEBUG", False),
                    )
                    self._add_failed_source_path(fn)
                    continue

                if not gpx.is_valid():
                    self._add_failed_source_path(fn)
                    continue

                self.cache_data(fn, gpx)

            all_gpxes.append(gpx)
            self.add_source_path(gpx)

        self.gpxes = order_content(all_gpxes)

        self.dates = list(self.gpxes)
        self.dates.sort(
            key=attrgetter("date"), reverse=self.context["NEWEST_FIRST_ARCHIVES"]
        )

        self._update_context(("gpxes", "dates"))
        self.save_cache()
        self.readers.save_cache()

        global gpx_count
        gpx_count = len(self.gpxes)
        signals.gpx_generator_finalized.send(self)

    def generate_gpxes(self, heatmap, writer):
        for gpx_article in self.gpxes:
            signals.gpx_generator_write_gpx.send(
                self, content=gpx_article.content, heatmap=heatmap
            )
            logging.debug(
                "%s Generate output for %s (%s)", LOG_PREFIX, gpx_article, heatmap
            )

            xml_save_as = getattr(gpx_article, f"gpx_{heatmap}_save_as")
            heatmap_save_as = getattr(gpx_article, f"gpx_{heatmap}_image")
            xml = getattr(gpx_article, f"gpx_{heatmap}_trimmed")

            if xml:
                writer.write_xml(
                    name=xml_save_as,
                    template=None,
                    context=self.context.copy(),
                    xml=xml,
                    gpx=gpx_article,
                    heatmap=heatmap,
                )

                writer.write_image(
                    name=heatmap_save_as,
                    template=None,
                    context=self.context.copy(),
                    image=generate_heatmap(
                        Path(self.output_path).resolve() / xml_save_as,
                        self.settings["GPX_HEATMAPS"][heatmap],
                    ),
                )

    def geneate_one_period_inner(
        self,
        gpxes,
        xml_save_as_setting,
        heatmap_save_as_setting,
        date,
        gpx_log_name,
        heatmap_key,
        context,
        context_period,
        context_period_number,
        writer,
    ):
        """
        Common generation for all types of grouped periods.

        Args:
        ----
            gpxes (pelican.contents.Content): the gpxes (think articles) that
                need to be combined
            save_as_setting (str): the setting that is used to determine where
                to save the combined file
            date (datetime.datetime): applied to `save_as_setting` to get final
                filename
            gpx_log_name (str): used in logging to refer to this run
            context: context that would normally be passed to the Jinja
                templates
            context_period (tuple): added to context at "period"
            context_period_number (tuple): added to context at "period_num"
            writer (pelican.writers.Writer): class that does the actual write
                to disk
        """
        combined_gpx = combine_gpx(
            [getattr(x, f"gpx_{heatmap_key}_trimmed") for x in gpxes],
            f"{gpx_log_name} ({heatmap_key})",
        )
        my_hash = gpx_hash(combined_gpx.to_xml())
        xml_save_as = xml_save_as_setting.format(
            # date=date,  # fixed in https://github.com/getpelican/pelican/pull/2902
            date=datetime(date.year, date.month, date.day),
            heatmap=heatmap_key,
            hash=my_hash,
        )
        heatmap_save_as = heatmap_save_as_setting.format(
            # date=date,  # fixed in https://github.com/getpelican/pelican/pull/2902
            date=datetime(date.year, date.month, date.day),
            heatmap=heatmap_key,
            hash=my_hash,
        )
        local_context = context.copy()
        local_context["period"] = context_period
        local_context["period_num"] = context_period_number

        if combined_gpx:
            writer.write_xml(
                name=xml_save_as,
                template=None,
                context=local_context,
                xml=combined_gpx.to_xml(),
            )

            if Path(heatmap_save_as).exists():
                logger("%s Image already exists: %s (for %s)", LOG_PREFIX, heatmap_save_as, xml_save_as)
            else:
                writer.write_image(
                    name=heatmap_save_as,
                    template=None,
                    context=local_context,
                    image=generate_heatmap(
                        Path(self.output_path).resolve() / xml_save_as,
                        self.settings["GPX_HEATMAPS"][heatmap_key],
                    ),
                )

    def generate_one_period(
        self,
        dates,
        period_key,
        heatmap_key,
        xml_save_as_setting,
        heatmap_save_as_setting,
        writer,
    ):
        """
        Generate combined GPX for a single grouping.

        Combined GPXes are taken from dates (which is already sorted by date),
        grouped by "period_key", and written to "save_as".
        """
        # add a signal somewhere here?

        if period_key == period_date_key["all"] and dates:
            self.geneate_one_period_inner(
                gpxes=dates,
                xml_save_as_setting=xml_save_as_setting,
                heatmap_save_as_setting=heatmap_save_as_setting,
                date=dates[0].date,
                gpx_log_name="all",
                heatmap_key=heatmap_key,
                context=self.context,
                context_period=("all",),
                context_period_number=(0,),
                writer=writer,
            )

        else:
            for _period, group in groupby(dates, key=period_key):
                archive = list(group)
                gpxes = [g for g in self.gpxes if g in archive]

                if period_key == period_date_key["year"]:
                    context_period = (_period,)
                    context_period_number = (_period,)
                elif period_key == period_date_key["week"]:
                    context_period = (_period[0], "week", _period[1])
                    context_period_number = (_period[0], 0, _period[1])
                else:
                    month_name = calendar.month_name[_period[1]]
                    if period_key == period_date_key["month"]:
                        context_period = (_period[0], month_name)
                    else:
                        context_period = (_period[0], month_name, _period[2])
                    context_period_number = tuple(_period)

                gpx_log_name = " ".join([str(x) for x in context_period])

                self.geneate_one_period_inner(
                    gpxes=gpxes,
                    xml_save_as_setting=xml_save_as_setting,
                    heatmap_save_as_setting=heatmap_save_as_setting,
                    date=archive[0].date,
                    gpx_log_name=gpx_log_name,
                    heatmap_key=heatmap_key,
                    context=self.context,
                    context_period=context_period,
                    context_period_number=context_period_number,
                    writer=writer,
                )

    def generate_period_gpxes(self, heatmap, writer):
        """
        Generate combined GPX files.

        Generate per-year, (per-quarter), per-month, (per-week) and per-day
        combined GPX files.
        """
        period_save_as = {
            "all": self.settings["ALL_GPX_SAVE_AS"],
            "year": self.settings["YEAR_GPX_SAVE_AS"],
            # "quarter": self.settings["QUARTER_GPX_SAVE_AS"],
            "month": self.settings["MONTH_GPX_SAVE_AS"],
            "week": self.settings["WEEK_GPX_SAVE_AS"],
            "day": self.settings["DAY_GPX_SAVE_AS"],
        }
        period_heatmap_save_as = {
            "all": self.settings["ALL_GPX_IMAGE_SAVE_AS"],
            "year": self.settings["YEAR_GPX_IMAGE_SAVE_AS"],
            # "quarter": self.settings["QUARTER_GPX_IMAGE_SAVE_AS"],
            "month": self.settings["MONTH_GPX_IMAGE_SAVE_AS"],
            "week": self.settings["WEEK_GPX_IMAGE_SAVE_AS"],
            "day": self.settings["DAY_GPX_IMAGE_SAVE_AS"],
        }

        for period in period_save_as.keys():
            xml_save_as = period_save_as[period]
            heatmap_save_as = period_heatmap_save_as[period]
            if xml_save_as:
                key = period_date_key[period]
                self.generate_one_period(
                    self.dates, key, heatmap, xml_save_as, heatmap_save_as, writer
                )

    def generate_output(self, writer):
        """
        Called by Pelican to push the resulting files to disk.
        """
        for heatmap in self.settings["GPX_HEATMAPS"].keys():
            self.generate_gpxes(heatmap=heatmap, writer=writer)
            self.generate_period_gpxes(heatmap=heatmap, writer=writer)

        signals.gpx_writer_finalized.send(self, writer=writer)


def display_stats(pelican_obj):
    """
    Called when Pelican is (nearly) done to display the number of files processed.
    """
    global gpx_count
    plural = "" if gpx_count == 1 else "s"
    print("%s Processed %s GPX file%s." % (LOG_PREFIX, gpx_count, plural))
