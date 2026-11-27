# Reports

The Reports screen previews reviewed rows and selected columns, then exports DOCX, XLSX or PDF. Historical reports are reconstructed from current records, not an immutable edit log. Recheck the preview before sharing.

The estate statement separates cash receipts, applied deposits and held security by shop and term. Unlinked historical bills appear as unassigned. Report cutoffs use recorded dates and current records.

Bill references use the manually entered **Reference / dispatch no.** field. Missing references stay blank; system-generated invoice numbers are not substituted. Generate a new preview after changing a reference.

**Bill date** is the confirmed receipt date for legacy bills and the recorded raising date for notice bills. It stays blank if that date was not recorded by the cutoff. It is separate from billing month and payment date. Vendor statements aggregate multiple bills and therefore do not have a single bill date.

Downloads use the reviewed snapshot for up to one hour, even if another user records a payment afterward. Generate another preview to include newer records. Changing filters clears the preview and disables downloads until it is regenerated.

Use **Refresh** beside the section heading to reload current data. Every BillTrack section has this action. On Reports it regenerates the preview with the current filters and keeps your column selection; **Preview report** starts a new preview with all columns selected.

## Available reports

- **Payments received:** receipts within the payment-date range, including receipts against older invoices. Principal and penalty receipts are separate. Security applications are excluded from cash receipts.
- **Pending bills:** outstanding principal or penalties through the cutoff, including older bills. A bill awaiting receipt confirmation is labelled and does not accrue penalty.
- **Penalties:** accrued, collected and outstanding penalties through cutoff, including settled bills. Overdue days stop at principal settlement. Penalty payments credit dues after the confirmed deadline, consistent with bill calculations.
- **Bills register:** bills in the selected accounting-month range, with rent, GST, electricity, water, total and principal payment position through cutoff.
- **Bills and payments statement:** opening net dues by vendor and allotment, billed amounts, penalty accrual during the period, receipts and closing net dues. Opening + billed + penalty accrual − cash receipts − security applied = closing. Negative net dues represent credit; advance receipts count even before their invoice's billing month.

**Estate dues and security statement:** choose a cutoff, then optionally filter by allottee, vendor type or allotment term. It shows unpaid bill principal and interest, holiday waivers and one-off charges. Unlinked bills appear as **Unassigned**. Cash received, deposits applied to dues and security still held have separate columns. A term selection includes the deposit account for its original award.

Vendor, vendor type, payment status at cutoff, receipt status at cutoff and optional billing-month filters narrow the selected bill population. Statement movements reconcile within that population. Billing months and payment dates are separate. Bills enter the accounts on the first day of their accounting month.

## Historical limits

Past-date reports reconstruct payment timing using **current** bill amounts, vendor information, recorded billing dates and penalty configuration. The estate statement uses the current assessment and latest waiver decision for each charge, with dated payments and security movements through the cutoff. The application does not retain every past edit, deletion or setting. These reports are not immutable accounting audit records; their limitation is stated in previews and exports. Keep submitted exports when a permanent record is needed.

Amounts are calculated on the backend using decimal arithmetic. Principal and penalties remain separate; invoice carry-forward dues are not counted a second time. Pending reports show nonnegative bill-level dues; statements preserve credits.

## Deployment and API

Install the updated `requirements.txt` (adds `openpyxl` and `python-docx`), build the React frontend with the existing deployment workflow, and restart Django. Reports itself adds no migration; a whole-application upgrade still requires all pending migrations, including later reminder tables. PDF uses the existing WeasyPrint setup.

Follow the [setup and updates guide](SETUP.md) for your installation. WeasyPrint and pydyf must match the versions pinned in `requirements.txt`.

Authenticated `GET /api/reports/` returns a preview and signed user-bound snapshot. Parameters: `report` (`pending`, `payments`, `penalties`, `bills`, `statement`, `estate`), `from`, `to` (inclusive ISO dates), `tenant`, `type`, `status`, `receipt_status` (`pending`/`confirmed`), `billing_from`, `billing_to` (`YYYY-MM`). Future cutoffs and reversed ranges are rejected. Pending and penalty reports use the cutoff and ignore `from`. Bills use the months containing `from` and `to`.

Authenticated `POST /api/reports/` with JSON `{"snapshot":"…","output":"docx"}` exports the preview; `xlsx` and `pdf` also work. Optional `columns` is a nonempty list of column keys from the preview (for example `["dispatch_ref_no", "balance"]`); omission includes all columns. Unknown keys and invalid selections are rejected. Invalid, expired or another user's snapshot is rejected. The API also retains direct GET exports via `output=csv|docx|xlsx|pdf`; these reflect data at request time. Financial responses use `Cache-Control: no-store`. The estate statement accepts only the cutoff and optional `tenant`, `type` and `allotment` filters.
