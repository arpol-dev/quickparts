from odoo import api, models


class HrHolidaysPublicLine(models.Model):
    _inherit = 'hr.holidays.public.line'

    def _refresh_analysis(self, dates):
        Analysis = self.env['attendance_analysis'].sudo()
        for date in dates:
            Analysis._refresh_for_date(date)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._refresh_analysis(set(records.mapped('date')))
        return records

    def write(self, vals):
        dates = set(self.mapped('date'))
        res = super().write(vals)
        dates |= set(self.mapped('date'))
        self._refresh_analysis(dates)
        return res

    def unlink(self):
        dates = set(self.mapped('date'))
        res = super().unlink()
        self._refresh_analysis(dates)
        return res
