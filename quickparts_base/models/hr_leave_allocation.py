from odoo import _, fields, models


class HrLeaveAllocation(models.Model):
    _inherit = 'hr.leave.allocation'

    attendance_analysis_id = fields.Many2one(
        'attendance_analysis', string="Analyse de présence",
        ondelete='cascade', index=True)

    def action_view_attendance_analysis(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Analyse de présence"),
            'res_model': 'attendance_analysis',
            'res_id': self.attendance_analysis_id.id,
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'current',
        }
