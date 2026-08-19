# Deployment Fix — Reset to Draft Action

The Odoo error `action_reset_to_draft is not a valid action on customer.batch` occurs when the XML view containing the new button is loaded while the running Odoo worker still has the previous Python model registry in memory.

The local source contains both:

```python
def action_reset_to_draft(self):
```

and:

```python
from . import customer_batch
```

The fix is therefore deployment order, not a change to the XML button: replace the addon directory, restart all Odoo workers so `models/customer_batch.py` is imported again, then update/upgrade the module.

## Required order

1. Stop all Odoo workers/processes serving the database.
2. Replace `/opt/odoo/odoo19/addons/customer_batch_discount` with the directory from this archive.
3. Ensure ownership and permissions match the other Odoo addons.
4. Start Odoo again.
5. Update the Apps list.
6. Upgrade `Customer Batch Discount`.

Do not upgrade the XML view first and restart later. A view button with `type="object"` is validated against the model methods already registered in the running Odoo process.

The archive version is `19.0.1.0.3`.
