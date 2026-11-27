# Lists, filters and refresh

Use search/date filters, row-size controls and pagination to find allottees, bills and payments. The Allottees list can sort by last billed month and open an allottee's bills. Refresh reloads the current section; errors retain a visible retry path.

## Available controls

| Section | Search and filters |
| --- | --- |
| Allotments | Name, allotment description, UUID, contact, email or GSTIN; allottee type; active/inactive |
| Bills | Invoice/reference/tenant search; tenant, tenant type, payment status, receipt status and period. Extension fee demands use the assessment month for period filters. |
| Payments | Receipt/invoice/tenant search; tenant, billing period and actual payment-date range |
| Payment Adjustments | Selected tenant; invoice/reference/receipt search; billing year/month and payment-date range |
| Penalties | Tenant/type and billing year/month; expanded bills also have invoice/reference search and due-date range |
| Dashboard | Global summaries and paginated overdue/upcoming lists; no search or filter controls |
| Reports | Report-specific period, vendor, payment/receipt status and billing-month filters; see [Reports](REPORTS.md) |

Payment dates and billing months are separate. A payment made this month can belong to an earlier invoice. Filtering split payments in Payment Adjustments preserves their original numbering and the full bill totals. Filtering expanded penalty details does not redefine the parent penalty total.

## Pagination

Record lists start with **10 rows** per page. Choose **10, 15, 20, 25 or 30** using Rows, then use **Prev** and **Next**. The controls show the displayed range, matching record count, and current/total pages. Filters and row-size changes return to the first page; shrinking results clamp the current page to an available page.

Allotments, Bills, Payments, dashboard overdue/upcoming lists, Payment Adjustments bill groups and split-payment details, Penalties and expanded penalty bills, and report previews use these controls. Pagination changes what is visible, not the full underlying totals. Report downloads include all matching rows. Invoice printing follows the selected bill IDs; verify the selection before printing.

Django Admin record lists, including Users, Groups, Tokens and System Settings, use the same row-size choices. Native search and applicable list filters remain available. Invalid row sizes fall back to 10. Editable inline forms are not paginated, so unsaved fields stay available.

## Refreshing records

Use **Refresh** beside a section heading to reload data while retaining its filters. Loading failures show a **Retry** action. Navigation can reuse loaded records for up to 30 seconds; dashboard visits reload its current data, and successful saves invalidate cached records. This is not continuous synchronization between separate sessions.

Use **Back** and **Forward** above the sidebar links to revisit sections during the current session. A Bills link opened for a specific allottee or term restores that scope. Section filters set manually reset when the section is reopened. BillTrack asks before discarding a temporary email draft.

On Reports, Refresh regenerates the preview with current filters and retains the selected download columns. **Preview report** starts a new preview with all columns selected. Changing report filters clears the old preview and disables downloads until another preview succeeds.

If a save reports that its outcome could not be confirmed, check the records before submitting again. The form preserves entered values to help recovery; an uncertain response does not prove that the server rejected the save.

## Allottee sorting and bill shortcut

In Allotments, **Sort by** offers Name (A–Z), Last billed: oldest first and Last billed: newest first. Sorting uses the actual month/year order across all loaded API pages before list pagination. Never-billed allottees appear first in oldest-first order and last in newest-first order; matching months are ordered by name. Changing sort returns to page one, Reset restores name order, and Refresh retains the selection.

Each active allottee has a **Raise Bill** action beside Edit. It opens Bills filtered to that allottee; use the existing **+ Raise Bill** control to open the form with that allottee already selected. The shortcut does not create a bill. Inactive allottees must be activated before using Raise Bill.

Extension fee demands appear in **Bills** alongside monthly invoices. Use the row's **Print extension fee demand** to print it, **Record charge receipt** to enter payment, or **Charge details** to review receipts and assessments. **Print Selected** and the email-draft selection apply to monthly invoices.

## Distinguishing multiple allotments

In **Allotments**, choose **Add Allotment** or **Edit**, then enter the optional **Allotment description**, for example Shop 12, Market Block. The app and Admin show **Name — description** in lists and selection menus, including bills, payments and email drafts. Search can find the description. Existing records start blank; names, IDs and financial records are unchanged. The invoice/report name remains the name field; use the separate allotment-description placeholder when wanted in email templates. Description is included in private business exports and backups; older exports without it import as blank.
