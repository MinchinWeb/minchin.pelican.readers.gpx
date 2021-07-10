from functools import partial
import logging
from operator import attrgetter

from pelican.generators import ArticlesGenerator, CachingGenerator
from pelican.utils import order_content

from . import signals
from .constants import LOG_PREFIX
from .contents import GPX as GPXContent

logger = logging.getLogger(__name__)
gpx_count = 0


class GPXArticleGenerator(ArticlesGenerator):
    def generate_pages(self, writer):
        """Generate the pages on the disk"""
        logger.debug("%s Article Generator: generate pages" % LOG_PREFIX)

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

    def generate_output(self, writer):
        """
        Called by Pelican to push the resulting files to disk.
        """
        for gpx_article in self.gpxes:
            signals.gpx_generator_write_gpx.send(self, content=gpx_article.content)
            logging.debug("%s Generate output for %s" % (LOG_PREFIX, gpx_article))
            writer.write_xml(
                name=gpx_article.save_as,
                template=None,
                context=self.context,
                xml=gpx_article.content,
                gpx=gpx_article,
            )
        signals.gpx_writer_finalized.send(self, writer=writer)


def display_stats(pelican_obj):
    """
    Called when Pelican is (nearly) done to display the number of files processed.
    """
    global gpx_count
    plural = "" if gpx_count == 1 else "s"
    print("%s Processed %s GPX file%s." % (LOG_PREFIX, gpx_count, plural))
