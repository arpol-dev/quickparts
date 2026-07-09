from odoo import api, fields, models


class HrAttendance(models.Model):
    _inherit = 'hr.attendance'

    date = fields.Date(
        string='Date', store=True, readonly=True,
        compute='_compute_date_attendance')

    @api.depends('check_in')
    def _compute_date_attendance(self):
        for record in self:
            record.date = record.check_in.date() if record.check_in else False

    def _completed_attendance_keys(self):
        # Only a checked-out attendance has meaningful worked hours; an open
        # check-in is ignored until the employee checks out.
        return {(r.employee_id, r.date)
                for r in self if r.employee_id and r.date and r.check_out}

    def _refresh_analysis(self, keys):
        # Employees declare their own attendances and have no write access to
        # attendance_analysis, so the recompute must run with sudo.
        Analysis = self.env['attendance_analysis'].sudo()
        for employee, date in keys:
            Analysis._refresh(employee, date)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._refresh_analysis(records._completed_attendance_keys())
        return records

    def write(self, vals):
        keys = self._completed_attendance_keys()
        res = super().write(vals)
        keys |= self._completed_attendance_keys()
        self._refresh_analysis(keys)
        return res

    def unlink(self):
        keys = self._completed_attendance_keys()
        res = super().unlink()
        self._refresh_analysis(keys)
        return res
