import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from oam_eoapi_stats.cache import cache
from oam_eoapi_stats.config import settings

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()


def start() -> None:
    scheduler.add_job(
        cache.refresh,
        trigger=CronTrigger.from_crontab(settings.cron_schedule),
        id="refresh-stats-cache",
        replace_existing=True,
        # A refresh can take minutes; never run two at once.
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    logger.info("Scheduler started with cron schedule '%s'", settings.cron_schedule)


def stop() -> None:
    scheduler.shutdown(wait=False)
