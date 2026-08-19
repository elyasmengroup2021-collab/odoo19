# Patch Notes — Odoo 19 Installation Fix

## Error fixed

The original installation failed while loading `security/security.xml` because Odoo 19 no longer exposes `category_id` on the `res.groups` model. The failing records were `group_customer_batch_user` and `group_customer_batch_manager`.

## Change made

Removed the obsolete `category_id` fields and the unused `ir.module.category` record from `security/security.xml`. The two groups now use only Odoo 19-supported fields, including `name` and `implied_ids`.

The module version was increased from `19.0.1.0.0` to `19.0.1.0.1`.

## Validation

Python syntax, XML parsing, manifest references, and ZIP integrity all passed after the patch.

## Upgrade procedure

1. Replace the old `customer_batch_discount` directory in the Odoo addons path with the directory from the patched archive.
2. Restart the Odoo server.
3. Enable developer mode if needed.
4. Go to Apps and click **Update Apps List**.
5. Open the module and click **Upgrade**. If it was not installed successfully, click **Install** again.
6. If Odoo reports a module operation left in an intermediate state, restart Odoo and retry the operation.

Do not manually delete database records unless Odoo still reports a previous partially-created group after the upgrade; the XML IDs are unchanged, so the corrected data file should update the existing records safely.
