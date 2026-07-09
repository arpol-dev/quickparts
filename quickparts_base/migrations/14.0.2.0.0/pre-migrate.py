import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        # Fresh install: nothing to migrate.
        return

    # 1. Drop unusable legacy rows that would break the new NOT NULL columns
    #    (date / employee_id were not required before).
    cr.execute("""
        DELETE FROM attendance_analysis
        WHERE date IS NULL OR employee_id IS NULL
    """)

    # 2. Deduplicate (employee_id, date) before the new unique constraint is
    #    created during module load. The legacy cron was not idempotent and
    #    could leave several rows per employee/day; keep the lowest id.
    cr.execute("""
        DELETE FROM attendance_analysis a
        USING attendance_analysis b
        WHERE a.employee_id = b.employee_id
          AND a.date = b.date
          AND a.id > b.id
    """)

    # 3. Bind the module xmlid `leave_type_timbrage` to the leave type already
    #    used by the legacy timbrage allocations (replaces the hardcoded
    #    holiday_status_id=6). The noupdate data record will then reuse it
    #    instead of creating a duplicate leave type.
    #    Detection uses the module's own marker column `name_timbrage` (set only
    #    on timbrage allocations). NB: hr.leave.allocation.name is a computed
    #    field (stored in private_name), so there is no `name` column to query.
    cr.execute("""
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'hr_leave_allocation'
          AND column_name = 'name_timbrage'
    """)
    if not cr.fetchone():
        _logger.warning(
            "quickparts_base: legacy column name_timbrage not found; a new "
            "'Allocation timbrage' leave type will be created on load.")
        return

    cr.execute("""
        SELECT holiday_status_id, count(*) AS n
        FROM hr_leave_allocation
        WHERE name_timbrage IS NOT NULL
          AND holiday_status_id IS NOT NULL
        GROUP BY holiday_status_id
        ORDER BY n DESC
        LIMIT 1
    """)
    row = cr.fetchone()
    if not row:
        _logger.warning(
            "quickparts_base: no legacy timbrage allocation found; a new "
            "'Allocation timbrage' leave type will be created on load.")
        return

    leave_type_id = row[0]
    cr.execute("""
        SELECT id FROM ir_model_data
        WHERE module = 'quickparts_base' AND name = 'leave_type_timbrage'
    """)
    if cr.fetchone():
        cr.execute("""
            UPDATE ir_model_data
            SET model = 'hr.leave.type', res_id = %s, noupdate = true
            WHERE module = 'quickparts_base' AND name = 'leave_type_timbrage'
        """, (leave_type_id,))
    else:
        cr.execute("""
            INSERT INTO ir_model_data (module, name, model, res_id, noupdate)
            VALUES ('quickparts_base', 'leave_type_timbrage',
                    'hr.leave.type', %s, true)
        """, (leave_type_id,))
    _logger.info(
        "quickparts_base: leave_type_timbrage bound to hr.leave.type id %s",
        leave_type_id)
