# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    'name': 'Quickparts Base',
    'version': '14.0.6.0.0',
    'category': 'Human Resources/Attendances',
    'license': 'AGPL-3',
    'summary': "Analyse des présences et allocations automatiques de timbrage",
    'description': """
Quickparts Base
===============

Analyse quotidiennement les présences (timbrages) des employés concernés et
les compare à leur horaire théorique issu du calendrier de travail. L'écart
(« gap ») obtenu est converti en allocation de congés afin de créditer ou
débiter les heures supplémentaires.

Deux actions planifiées :

* analyse quotidienne des présences (par employé / par jour) ;
* création des allocations de congés à partir des écarts calculés.
    """,
    'author': 'Quickparts',
    'depends': [
        'base',
        'hr',
        'hr_attendance',
        'hr_holidays',
        'hr_holidays_public',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/hr_leave_type.xml',
        'data/ir_cron.xml',
        'views/attendance_analysis_views.xml',
        'views/hr_employee_views.xml',
        'views/hr_leave_allocation_views.xml',
    ],
    'qweb': [
        'static/src/xml/time_off_dashboard.xml',
    ],
    'installable': True,
}
