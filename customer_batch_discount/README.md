# Customer Batch Discount

This independent Odoo 19 Community addon manages customer business cycles, consumption from posted customer invoices, customer discounts, and a single balanced journal entry per completed batch.

## Lifecycle

A batch moves through `Draft -> Open -> Closed -> Discount Applied`. A manager may cancel a batch before a discount entry exists. A customer/company may have only one open batch. Batch dates use an inclusive convention: `end_date = start_date + duration_days - 1`.

## Consumption

The first release uses posted customer invoices and credit notes linked to the batch. Only `out_invoice` and `out_refund` documents dated inside the batch interval are considered. Draft and cancelled documents are excluded by the `state = posted` filter. Refunds are subtracted. Quantities are converted through Odoo's standard `uom.uom._compute_quantity` method into the configured company target UoM, or the product's inventory UoM when no target UoM is configured.

## Discount and accounting

The discount wizard supports a common rate for all products and an independent rate per product. Each line amount is `quantity * discount_per_unit`; negative rates are rejected. Applying a discount creates exactly one posted `account.move` in the configured general journal. The entry debits the customer's company receivable account and credits the configured customer-batch discount account for the same total. Original invoices are never changed. The resulting move is stored on the batch and the batch is frozen in `Discount Applied`.

## Payment terms

For a customer invoice linked to a batch, the payment-term computation uses the batch end date as `date_ref`. The standard Odoo 19 term engine remains responsible for installments, multiple term lines, early-payment discounts, taxes, and due-date generation; the override is limited to batched invoices and mirrors the Odoo 19 computation contract so standard invoices continue through `super()`.

## Configuration

In Accounting settings, configure the company-specific discount account and general journal. The optional target UoM is useful for normalizing kilograms to tons without hard-coded arithmetic. Consumption source is currently `Posted Customer Invoices`; the field is intentionally isolated so a stock-move or sales-order provider can be added later.

## Validation scope

The source is written for Odoo 19 APIs. This workspace does not include an Odoo server/runtime or database, so Python/XML/static checks can be run here, but ORM behavior, view installation, posting, access rules, and integration tests require a real Odoo 19 Community instance with Accounting, Mail, and UoM modules installed.

## Exact Batch End Date payment term

Payment Term lines now include `Batch End Date`. Select this option on a Due Terms line when the invoice is linked to a customer batch. For such invoices, Odoo computes the maturity date as the batch's `end_date` exactly; no payment-term days are added. The module passes the batch end date through context to Odoo's standard payment-term engine, so the regular engine still handles the term amounts and other lines. A payment term containing this option requires a linked batch on customer invoices.

## Reset cancelled batch to draft

The new `Reset Customer Batch to Draft` group controls the operation. The `Customer Batch Manager` group implies it, while an administrator can assign the reset group independently to selected users. The permission is enforced both by the form button visibility and by a server-side `has_group` check. Only a cancelled batch without a posted discount journal entry can be reset, and the reset is logged in the batch chatter.

## Consumption and Accounting tab correction

Odoo 19 stores regular invoice product lines with `display_type = 'product'`. Consumption now explicitly selects product lines using `line.display_type == 'product'`; filtering on an empty display type would incorrectly remove all regular invoice lines. Invoice selection also matches the commercial customer, so invoices issued to a child contact are included in the parent customer's batch.

The batch Accounting tab now shows two sections. `Configured Settings` displays the company-level discount account and journal immediately, before a discount is posted. `Applied Discount Entry` displays the account, journal, date, and journal entry actually used after applying the discount.

## Direct discount entry and applied-entry details

The discount wizard is no longer required for the normal workflow. After calculating consumption and closing the batch, enter `Discount / UoM` directly in the Consumption list. `Discount Amount` is a stored computed field equal to `Quantity × Discount / UoM`, rounded in the batch currency. The Apply Discount button uses the rates currently saved on the persistent consumption lines.

Consumption is normalized to a compatible company target UoM when configured; otherwise, or when the configured UoM belongs to another category, it falls back to the product's base UoM. Each invoice line is converted into that target before product quantities are aggregated.

The Accounting tab includes `Discount Label / Note`, which is copied to the posted journal entry reference and line labels. After application, `Discount Date`, `Applied Entry Reference`, and the applied account/journal are displayed in the Applied Discount Entry section.

## One active batch per customer

A customer may have multiple historical batches, but only one batch may be in `Open` state for the same company. The server-side check compares the commercial customer, not only the selected contact, so two contacts belonging to the same parent customer cannot open parallel batches. A second batch may be created in Draft, but opening it is blocked until the existing Open batch is closed or cancelled. After the prior batch is closed, the new Draft batch can be opened normally.

## Odoo 19 UoM compatibility patch

Odoo 19 does not expose `category_id` on `uom.uom`. The consumption normalizer now uses Odoo 19's `_has_common_reference()` method to determine whether the configured target UoM and invoice-line UoM belong to a compatible conversion family. If they do not, the product's base UoM is used instead.

## Odoo 19 account-company compatibility patch

Odoo 19 represents account availability through `account.account.company_ids`, while journals continue to use `account.journal.company_id`. Apply Discount now checks the account with `company in discount_account.company_ids` and the journal with its `company_id`; the settings domain and regression test use the same Odoo 19 account relation.

## Uniform discount over all consumption

The supported discount flow now uses one batch-level `Discount / UoM` rate. Enter the rate once on the closed batch, review the computed `Total Discount`, and press `Apply Discount`. The rate is applied to every normalized consumption quantity and creates one balanced journal entry. Per-product rates are no longer editable through the batch form.

## Release 19.0.1.0.10 deployment check

The current source must contain `company not in discount_account.company_ids`; it must not contain `discount_account.company_id`. After copying the release, verify the manifest shows `19.0.1.0.10` and restart all Odoo workers before upgrading. If the traceback still shows `discount_account.company_id`, the server is executing an older addon copy or an older Python registry.
