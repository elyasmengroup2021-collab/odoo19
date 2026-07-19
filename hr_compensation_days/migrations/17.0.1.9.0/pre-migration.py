# -*- coding: utf-8 -*-


def migrate(cr, version):
    """Allow zero-value mission amounts when upgrading the module.

    Odoo does not replace an existing SQL constraint when the Python
    constraint keeps the same name. Drop the old strictly-positive check so
    the updated non-negative constraint can be created during registry setup.
    """
    cr.execute(
        "ALTER TABLE hr_compensation_days "
        "DROP CONSTRAINT IF EXISTS hr_compensation_days_positive_amount"
    )
