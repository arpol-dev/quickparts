from odoo import api, models


class HrLeaveType(models.Model):
    _inherit = 'hr.leave.type'

    @api.model
    def get_days_all_request(self):
        res = super().get_days_all_request()
        timbrage = self.env.ref(
            'quickparts_base.leave_type_timbrage', raise_if_not_found=False)
        if timbrage:
            for entry in res:
                # entry = (name, infos_dict, allocation_type, validity_stop)
                if entry[0] == timbrage.name:
                    entry[1]['is_timbrage'] = True
                    # Display the magnitude only; the sign drives the label.
                    value = entry[1].get('virtual_remaining_leaves') or '0'
                    entry[1]['timbrage_abs'] = value.lstrip('-')
        return res
