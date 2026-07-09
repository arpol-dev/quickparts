from odoo import api, fields, models, _

PAID_LEAVE_PARAM = 'quickparts_base.paid_leave_type_id'
TIMBRAGE_XMLID = 'quickparts_base.leave_type_timbrage'


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    allow_attendee = fields.Boolean(string="Saisie sur présence")
    pto_used_display = fields.Char(
        string="Congés payés pris", compute='_compute_paid_leave_figures',
        compute_sudo=True)
    pto_allocated_display = fields.Char(
        string="Congés payés attribués", compute='_compute_paid_leave_figures',
        compute_sudo=True)
    timbrage_balance_display = fields.Char(
        string="Solde heures supplémentaires",
        compute='_compute_timbrage_balance', compute_sudo=True)

    def _paid_leave_type(self):
        param = self.env['ir.config_parameter'].sudo().get_param(
            PAID_LEAVE_PARAM)
        if not param:
            return self.env['hr.leave.type']
        return self.env['hr.leave.type'].browse(int(param)).exists()

    def _compute_paid_leave_figures(self):
        paid_type = self._paid_leave_type()
        for employee in self:
            if paid_type:
                data = paid_type.with_context(employee_id=employee.id)
                employee.pto_used_display = (
                    '%.2f' % data.leaves_taken).rstrip('0').rstrip('.')
                employee.pto_allocated_display = (
                    '%.2f' % data.max_leaves).rstrip('0').rstrip('.')
            else:
                employee.pto_used_display = '0'
                employee.pto_allocated_display = '0'

    def _compute_timbrage_balance(self):
        timbrage = self.env.ref(TIMBRAGE_XMLID, raise_if_not_found=False)
        for employee in self:
            balance = 0.0
            if timbrage:
                balance = timbrage.with_context(
                    employee_id=employee.id).virtual_remaining_leaves
            label = _("à rattraper") if balance < 0 else _("à récupérer")
            value = ('%.2f' % abs(balance)).rstrip('0').rstrip('.')
            employee.timbrage_balance_display = '%s %s' % (value, label)

    def _leave_analysis_action(self, leave_type):
        action = self.env['hr.leave.report'].with_context(
            active_ids=self.ids).action_time_off_analysis()
        if leave_type:
            action['domain'] = action.get('domain', []) + [
                ('holiday_status_id', '=', leave_type.id)]
        return action

    def action_view_paid_leave_analysis(self):
        self.ensure_one()
        action = self._leave_analysis_action(self._paid_leave_type())
        action['name'] = _("Analyse des congés payés")
        return action

    def action_view_timbrage_analysis(self):
        self.ensure_one()
        timbrage = self.env.ref(TIMBRAGE_XMLID, raise_if_not_found=False)
        action = self._leave_analysis_action(timbrage)
        action['name'] = _("Analyse des heures supplémentaires")
        return action
