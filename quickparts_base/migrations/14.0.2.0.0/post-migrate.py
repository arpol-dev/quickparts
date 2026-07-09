import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    # The legacy text key `name_timbrage` matched attendance_analysis.name.
    # Backfill the new Many2one relation from it. Odoo does not drop the column
    # of a removed field, so the legacy data is still readable here.
    cr.execute("""
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'hr_leave_allocation'
          AND column_name = 'name_timbrage'
    """)
    if not cr.fetchone():
        return

    cr.execute("""
        UPDATE hr_leave_allocation alloc
        SET attendance_analysis_id = aa.id
        FROM attendance_analysis aa
        WHERE alloc.attendance_analysis_id IS NULL
          AND alloc.name_timbrage IS NOT NULL
          AND alloc.name_timbrage = aa.name
    """)
    _logger.info(
        "quickparts_base: backfilled attendance_analysis_id on %s allocation(s)",
        cr.rowcount)
