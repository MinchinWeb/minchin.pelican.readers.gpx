import calendar
from functools import partial
from itertools import groupby
import logging
from operator import attrgetter

from pelican.generators import ArticlesGenerator, CachingGenerator
from pelican.utils import order_content

from . import signals
from .constants import LOG_PREFIX
from .contents import GPX as GPXContent
from .gpx import combine_gpx

logger = logging.getLogger(__name__)
gpx_count = 0

period_date_key = {
    "all": None,
    "year": attrgetter("date.year"),
    "month": attrgetter("date.year", "date.month"),
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

    def generate_gpxes(self, writer):
        for gpx_article in self.gpxes:
            signals.gpx_generator_write_gpx.send(self, content=gpx_article.content)
            logging.debug("%s Generate output for %s", LOG_PREFIX, gpx_article)
            writer.write_xml(
                name=gpx_article.save_as,
                template=None,
                context=self.context.copy(),
                xml=gpx_article.content,
                gpx=gpx_article,
            )

    def generate_one_period(self, dates, period_key, save_as_setting, writer):
        """
        Generate combined GPX for a single grouping.

        Combined GPXes are taken from dates (which is already sorted by date),
        grouped by "period_key", and written to "save_as".
        """
        # add a signal somewhere here?

        if period_key == period_date_key["all"] and dates:
            save_as = save_as_setting.format(date=dates[0].date)
            combined_gpx = combine_gpx([x.content for x in dates], "all")
            context = self.context.copy()
            context["period"] = "all"
            context["period_num"] = (0,)

            if combined_gpx:
                writer.write_xml(
                    name=save_as,
                    template=None,
                    context=context,
                    xml=combined_gpx.to_xml(),
                )
        else:
            for _period, group in groupby(dates, key=period_key):
                archive = list(group)
                gpxes = [g for g in self.gpxes if g in archive]
                date = archive[0].date
                save_as = save_as_setting.format(date=date)
                context = self.context.copy()

                gpx_log_name = None
                if period_key == period_date_key["all"]:
                    context["period"] = "all"
                    context["period_num"] = (0,)
                    gpx_log_name = "all"
                elif period_key == period_date_key["year"]:
                    context["period"] = (_period,)
                    context["period_num"] = (_period,)
                else:
                    month_name = calendar.month_name[_period[1]]
                    if period_key == period_date_key["month"]:
                        context["period"] = (_period[0], month_name)
                    else:
                        context["period"] = (_period[0], month_name, _period[2])
                    context["period_num"] = tuple(_period)

                if gpx_log_name is None:
                    gpx_log_name = " ".join([str(x) for x in context["period"]])

                combined_gpx = combine_gpx([x.content for x in gpxes], gpx_log_name)

                if combined_gpx:
                    writer.write_xml(
                        name=save_as,
                        template=None,
                        context=context,
                        xml=combined_gpx.to_xml(),
                    )

    def generate_period_gpxes(self, writer):
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
            # "week": self.settings["WEEK_GPX_SAVE_AS"],
            "day": self.settings["DAY_GPX_SAVE_AS"],
        }

        for period in period_save_as.keys():
            save_as = period_save_as[period]
            if save_as:
                key = period_date_key[period]
                self.generate_one_period(self.dates, key, save_as, writer)

    def generate_output(self, writer):
        """
        Called by Pelican to push the resulting files to disk.
        """
        self.generate_gpxes(writer=writer)
        self.generate_period_gpxes(writer=writer)

        signals.gpx_writer_finalized.send(self, writer=writer)


def display_stats(pelican_obj):
    """
    Called when Pelican is (nearly) done to display the number of files processed.
    """
    global gpx_count
    plural = "" if gpx_count == 1 else "s"
    print("%s Processed %s GPX file%s." % (LOG_PREFIX, gpx_count, plural))
