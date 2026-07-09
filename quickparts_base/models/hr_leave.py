from odoo import api, fields, models


class HrLeave(models.Model):
    _inherit = 'hr.leave'

    date_from_only = fields.Date(
        string="Date de début (jour)", store=True, readonly=True,
        compute='_compute_date_from_only')
    date_to_only = fields.Date(
        string="Date de fin (jour)", store=True, readonly=True,
        compute='_compute_date_to_only')

    @api.depends('date_from')
    def _compute_date_from_only(self):
        for record in self:
            record.date_from_only = (
                record.date_from.date() if record.date_from else False)

    @api.depends('date_to')
    def _compute_date_to_only(self):
        for record in self:
            record.date_to_only = (
                record.date_to.date() if record.date_to else False)

    def _validated_leave_keys(self):
        # Only validated leaves count in the analysis; capturing them before and
        # after a write catches both validation and un-validation (refusal).
        return {(r.employee_id, r.date_from_only, r.date_to_only)
                for r in self
                if r.state == 'validate' and r.employee_id
                and r.date_from_only and r.date_to_only}

    def _refresh_analysis(self, keys):
        Analysis = self.env['attendance_analysis'].sudo()
        for employee, date_from, date_to in keys:
            Analysis._refresh_range(employee, date_from, date_to)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._refresh_analysis(records._validated_leave_keys())
        return records

    def write(self, vals):
        keys = self._validated_leave_keys()
        res = super().write(vals)
        keys |= self._validated_leave_keys()
        self._refresh_analysis(keys)
        return res

    def unlink(self):
        keys = self._validated_leave_keys()
        res = super().unlink()
        self._refresh_analysis(keys)
        return res
