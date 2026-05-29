from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError

LEAVE_TYPE_XMLID = 'quickparts_base.leave_type_timbrage'


class AttendanceAnalysis(models.Model):
    _name = 'attendance_analysis'
    _description = "Analyse quotidienne des présences"
    _order = 'date desc, employee_id'

    name = fields.Char(string='Référence', required=True)
    date = fields.Date(string='Date', required=True)
    employee_id = fields.Many2one(
        'hr.employee', string='Employé', required=True, ondelete='cascade')
    hours_theoretical = fields.Float(
        string='Heures théoriques',
        help="Heures de travail attendues ce jour-là selon le calendrier de "
             "travail de l'employé.")
    hours_attendance = fields.Float(
        string='Heures pointées',
        help="Total des heures réellement pointées (présences) sur la journée.")
    hours_leave = fields.Float(
        string='Heures de congé',
        help="Heures de congé validées comptées comme du temps de présence "
             "(demi-journées, heures…).")
    hours_public_holiday = fields.Float(
        string='Heures de jour férié chômé',
        help="Heures créditées au titre d'un jour férié chômé.")
    hours_additionnal = fields.Float(
        string='Heures non pointées',
        help="Peut correspondre à n'importe quelle activité non pointée mais à prendre en compte pour le calcul de l'allocation, ex : rendez-vous client, travail à distance, etc.")
    gap = fields.Float(
        string='Écart', compute='_compute_gap', store=True,
        help="(Présence + congés + férié chômé) − heures théoriques. "
             "Positif = heures supplémentaires ; négatif = heures manquantes. "
             "Converti ensuite en heures d'allocation.")
    allocation_ids = fields.One2many(
        'hr.leave.allocation', 'attendance_analysis_id', string='Allocations')
    attendance_ids = fields.Many2many(
        'hr.attendance', string='Présences',
        compute='_compute_attendance_ids',
        help="Timbrages de l'employé pour cette journée.")
    attendance_count = fields.Integer(
        string='Nombre de présences', compute='_compute_counts')
    allocation_count = fields.Integer(
        string="Nombre d'allocations", compute='_compute_counts')
    manual_adjustment = fields.Boolean(
        string='Ajusté manuellement',
        help="Si coché, les heures réalisées sont saisies à la main et le "
             "recalcul automatique ne les met plus à jour.")
    allocation_to_sync = fields.Boolean(
        string='Allocation à synchroniser', default=False,
        help="L'écart a changé : l'allocation sera (re)générée au prochain "
             "passage du cron, ou via le bouton « Ajuster l'allocation ».")

    _sql_constraints = [
        ('employee_date_uniq', 'unique(employee_id, date)',
         "Une analyse existe déjà pour cet employé à cette date."),
    ]

    @api.depends('employee_id', 'date')
    def _compute_attendance_ids(self):
        for analysis in self:
            if analysis.employee_id and analysis.date:
                analysis.attendance_ids = self.env['hr.attendance'].search([
                    ('employee_id', '=', analysis.employee_id.id),
                    ('date', '=', analysis.date),
                ])
            else:
                analysis.attendance_ids = False

    @api.depends('attendance_ids', 'allocation_ids')
    def _compute_counts(self):
        for analysis in self:
            analysis.attendance_count = len(analysis.attendance_ids)
            analysis.allocation_count = len(analysis.allocation_ids)

    @api.depends('hours_attendance', 'hours_leave', 'hours_public_holiday',
                 'hours_theoretical')
    def _compute_gap(self):
        for analysis in self:
            analysis.gap = (
                analysis.hours_attendance + analysis.hours_leave
                + analysis.hours_public_holiday + analysis.hours_additionnal - analysis.hours_theoretical)

    def action_view_attendances(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Présences"),
            'res_model': 'hr.attendance',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', self.attendance_ids.ids)],
        }

    def action_view_allocations(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Allocations"),
            'res_model': 'hr.leave.allocation',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', self.allocation_ids.ids)],
        }

    def _update_metrics(self):
        """Recompute and store the attendance metrics for these analyses.

        The day's attendances come from ``attendance_ids`` (computed from the
        employee + date), so that search lives in a single place. All
        accumulators are local to each record.
        """
        for analysis in self:
            employee = analysis.employee_id
            date = analysis.date
            hours_attendance = sum(
                analysis.attendance_ids.mapped('worked_hours'))

            leaves_day = self.env['hr.leave'].search([
                ('employee_id', '=', employee.id),
                ('date_from_only', '<=', date),
                ('date_to_only', '>=', date),
                ('holiday_status_id.request_unit', '!=', 'hour'),
                ('state', '=', 'validate'),
            ])
            leaves_hour = self.env['hr.leave'].search([
                ('employee_id', '=', employee.id),
                ('date_from_only', '<=', date),
                ('date_to_only', '>=', date),
                ('holiday_status_id.request_unit', '=', 'hour'),
                ('state', '=', 'validate'),
            ])
            public_lines = self.env['hr.holidays.public.line'].search([
                ('date', '=', date),
            ])

            weekday = str(date.weekday())
            calendar_lines = \
                employee.resource_calendar_id.attendance_ids.filtered(
                    lambda line: line.dayofweek == weekday)
            hours_theoretical = sum(
                line.hour_to - line.hour_from for line in calendar_lines)

            # Scalar attributes are read on the first matching leave only; hour
            # totals are aggregated over the full recordset. The branches only
            # decide how leave / public-holiday hours are counted; the gap is a
            # stored computed field derived from them (see _compute_gap), so
            # hours worked on a day off (public holiday or full leave) still
            # count as overtime.
            leave_day = leaves_day[:1]
            leave_hour = leaves_hour[:1]
            hours_leave = 0.0
            hours_public_holiday = 0.0

            if public_lines:
                hours_public_holiday = hours_theoretical
            elif leave_day.number_of_days and not leave_day.request_unit_half:
                hours_leave = hours_theoretical
            elif (leave_hour.number_of_days
                  and not leave_hour.request_unit_half
                  and not leave_hour.request_unit_hours):
                hours_leave = hours_theoretical
            elif leave_day.number_of_days and leave_hour.number_of_days:
                hours_leave = (
                    sum(leaves_day.mapped('number_of_hours_display'))
                    + sum(leaves_hour.mapped('number_of_hours_display')))
            elif leave_day.number_of_days and leave_day.request_unit_half:
                hours_leave = sum(leaves_day.mapped('number_of_hours_display'))
            elif ((leave_hour.number_of_days and leave_hour.request_unit_half)
                  or leave_hour.request_unit_hours):
                hours_leave = sum(leaves_hour.mapped('number_of_hours_display'))

            analysis.write({
                'hours_attendance': hours_attendance,
                'hours_leave': hours_leave,
                'hours_public_holiday': hours_public_holiday,
                'hours_theoretical': hours_theoretical,
            })
            analysis.name = "%s-%s-%s" % (
                round(analysis.gap, 2), employee.name, date)

    def _has_activity(self):
        self.ensure_one()
        return bool(self.hours_attendance or self.hours_theoretical
                    or self.hours_leave)

    def write(self, vals):
        res = super().write(vals)
        # Any change to the measured hours moves the gap (hence the
        # allocation): flag the records so the nightly cron re-syncs them.
        measured = {'hours_attendance', 'hours_leave', 'hours_public_holiday',
                    'hours_theoretical'}
        if measured & set(vals) and 'allocation_to_sync' not in vals:
            super(AttendanceAnalysis, self).write({'allocation_to_sync': True})
        # Leaving manual mode hands the record back to automatic computation.
        if vals.get('manual_adjustment') is False:
            self._update_metrics()
        return res

    @api.model
    def _refresh(self, employee, date):
        """Upsert and recompute the analysis of one employee for one day.

        Replaces the former daily cron: called from the source models whenever
        an attendance, leave or public holiday changes. Manually adjusted rows
        are left untouched.
        """
        if not employee or not date or not employee.allow_attendee:
            return
        analysis = self.search([
            ('employee_id', '=', employee.id),
            ('date', '=', date),
        ], limit=1)
        if analysis.manual_adjustment:
            return
        created = not analysis
        if created:
            analysis = self.create({
                'name': '/',
                'employee_id': employee.id,
                'date': date,
            })
        analysis._update_metrics()
        # A row created for an off day (no activity) is dropped; it has no
        # allocation yet, so this is safe.
        if created and not analysis._has_activity():
            analysis.unlink()

    @api.model
    def _refresh_range(self, employee, date_from, date_to):
        if not (employee and date_from and date_to):
            return
        day = date_from
        while day <= date_to:
            self._refresh(employee, day)
            day += timedelta(days=1)

    @api.model
    def _refresh_for_date(self, date):
        if not date:
            return
        employees = self.env['hr.employee'].search([
            ('allow_attendee', '=', True)])
        for employee in employees:
            self._refresh(employee, date)

    @api.model
    def _cron_create_allocations(self):
        to_sync = self.search([('allocation_to_sync', '=', True)])
        for analysis in to_sync:
            analysis._sync_allocation()
        to_sync.write({'allocation_to_sync': False})

    def _sync_allocation(self):
        """Create (or refresh) the leave allocation linked to this analysis.

        Idempotent: existing linked allocations are removed first, so the cron
        and the manual button always converge to the same result.
        """
        self.ensure_one()
        existing = self.allocation_ids
        if existing:
            existing.filtered(lambda a: a.state != 'draft').write(
                {'state': 'draft'})
            existing.unlink()

        hours_per_day = self.employee_id.resource_calendar_id.hours_per_day
        if not hours_per_day or not self.gap:
            return

        leave_type = self.env.ref(LEAVE_TYPE_XMLID, raise_if_not_found=False)
        if not leave_type:
            raise UserError(_(
                "Le type de congé « Allocation timbrage » est introuvable. "
                "Vérifiez la configuration du module quickparts_base."))

        self.env['hr.leave.allocation'].create({
            'holiday_type': 'employee',
            'employee_id': self.employee_id.id,
            'name': _("Allocation automatique timbrage"),
            'holiday_status_id': leave_type.id,
            'allocation_type': 'regular',
            'number_of_days': self.gap / hours_per_day,
            'state': 'validate',
            'attendance_analysis_id': self.id,
        })

    def action_sync_allocation(self):
        for analysis in self:
            analysis._sync_allocation()
        self.write({'allocation_to_sync': False})
