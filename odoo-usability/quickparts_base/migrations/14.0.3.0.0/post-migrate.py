import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    # The daily analysis cron is replaced by event-driven recomputation in the
    # source models. Its record is noupdate, so removing it from the XML does
    # not delete it on load — drop it explicitly here.
    env = api.Environment(cr, SUPERUSER_ID, {})
    cron = env.ref('quickparts_base.cron_attendance_analysis_daily',
                   raise_if_not_found=False)
    if cron:
        cron.unlink()
        _logger.info("quickparts_base: removed obsolete daily analysis cron.")
