# Copyright <YEAR(S)> <AUTHOR(S)>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    'name': 'Example Module',
    'version': '19.0.1.0.0',
    'summary': 'Example Module',
    'author': 'Afxadev Technologies',
    'website': 'https://afxadev.com/',
    'license': 'AGPL-3',
    'category': 'Uncategorized',
    'depends': [
        'base'
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/module_security.xml',
        'data/model_name_data.xml',
        'views/model_name_views.xml',
    ],
    'demo': [
        'demo/model_name_demo.xml',
    ],
    'auto_install': False,
    'application': False,
    "development_status": "Alpha", # options: Alpha|Beta|Production/Stable|Mature
    'assets': {
        
    }
}