import logging

from services.alert_service import run_alert_scan

logger = logging.getLogger(__name__)
_scheduler = None


def init_scheduler(app):
    global _scheduler
    if _scheduler is not None:
        return _scheduler
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
    except Exception:
        logger.warning("APScheduler not installed, skip startup.")
        return None
    scheduler = BackgroundScheduler(timezone="Asia/Shanghai")

    def _job():
        with app.app_context():
            try:
                run_alert_scan()
            except Exception as ex:
                logger.exception("alert scan job failed: %s", ex)

    scheduler.add_job(_job, trigger="interval", minutes=1, id="alert_scan_every_minute", replace_existing=True)
    scheduler.start()
    _scheduler = scheduler
    return scheduler
