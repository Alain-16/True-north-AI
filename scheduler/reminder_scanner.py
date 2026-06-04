import logging
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from core.config import get_settings
from features.reminders.service import scan_and_send

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


def start_scheduler() -> None:
      global _scheduler
      settings = get_settings()
      _scheduler = AsyncIOScheduler()
      _scheduler.add_job(
          scan_and_send,
          trigger="interval",
          seconds=settings.reminder_scan_interval_seconds,
          id="reminder_scan",
          max_instances=1,            # never overlap scans
          coalesce=True,              # collapse missed runs into one
          next_run_time=datetime.now(),   # run one scan immediately on startup
      )
      _scheduler.start()
      logger.info("Reminder scheduler started (every %ss)",
                  settings.reminder_scan_interval_seconds)


def stop_scheduler() -> None:
      global _scheduler
      if _scheduler is not None:
          _scheduler.shutdown(wait=False)
          _scheduler = None
