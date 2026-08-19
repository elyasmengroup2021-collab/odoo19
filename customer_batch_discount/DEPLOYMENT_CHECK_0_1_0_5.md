# Deployment Check — Accounting Fields

The traceback means the server loaded the updated XML view but its registered `customer.batch` model does not contain the Python field `configured_discount_account_id`. The release in this archive is `19.0.1.0.5` and contains both related fields in `models/customer_batch.py` and the import in `models/__init__.py`.

After copying the full addon directory, verify:

```bash
grep -n "version" /opt/odoo/odoo19/addons/customer_batch_discount/__manifest__.py
grep -n "configured_discount_account_id" /opt/odoo/odoo19/addons/customer_batch_discount/models/customer_batch.py
grep -n "configured_discount_journal_id" /opt/odoo/odoo19/addons/customer_batch_discount/models/customer_batch.py
grep -n "from . import customer_batch" /opt/odoo/odoo19/addons/customer_batch_discount/models/__init__.py
```

The first command must show `19.0.1.0.5`; the next two must return field definitions; the last must return the import. Then restart every Odoo worker and upgrade the module. Do not load the XML view from one addon copy while Python is loaded from another `addons_path` copy.
