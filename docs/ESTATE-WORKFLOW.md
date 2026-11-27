# Allotment register and estate workflows

The [extensions and security deposits tutorial](EXTENSIONS-AND-SECURITY-DEPOSITS.md) covers extension fees, renewal linkage, deposit review and carry-forward, and approved date exceptions.

Open **Allotments** to find existing records by allottee name, allotment description or contact. **Add Allotment** and **Edit** maintain the record used for contacts and billing. Use **Allotment description** to identify what was allotted, for example Shop 12, Market Block. Use **View term history** for past terms, renewals and term dues. Create separate register entries with distinct descriptions when the same person or business has separate allotments.

In the Allotments register, choose **Activate** or **Deactivate** in the row’s **Actions** and enter a reason. Use the **Status** filter to find inactive records. Deactivation closes the record to new bills while keeping its contracts, bills and receipts available for review and collection. Reactivate the record to raise bills again.

**Actions → Delete** previews the effect and asks for confirmation and a written reason. BillTrack removes an unused record. A record with bills or contract terms is marked **Inactive**, with its history available for review.

See the [changelog](../CHANGELOG.md) for release details and upgrade notes.

## Communication switches

Under **Admin → System Settings → Estate features**, use **New signups** to control requests for new accounts, **Bills email communication** to control sending bill reminders from Admin, and **Bills email format for copying** to control **Email Drafts**. Save with a change reason and reload BillTrack. The switches work independently. Existing account verification and recovery, dispatch evidence, and reminder delivery history remain accessible.

## Correct a payment receipt

On **Bills**, choose **Payment receipts** below the invoice number, then choose **Edit receipt**. On the **Payment Register** or **Payment Adjustments**, choose **Edit receipt** below the payment date. Enter the correction and a written reason. BillTrack recalculates the invoice balance from the updated receipt. Security applications use their own reviewed workflow.

## Optional premises register

To enable premises management, open **Admin → System Settings → Estate features**, tick **Enable Premises**, and save with a change reason. Reload BillTrack. **Allotments → Find premises** lets staff manage records and check physical availability. The **Premises (optional)** selector is available when creating or editing a term. Terms can be recorded without a premises link. Renewals inherit the preceding term’s link.

Clear **Enable Premises** and save to hide its controls and availability alerts. Premises records and existing links are preserved for when the feature is enabled again.

## Allotment and renewal

In **Add Allotment** or **Edit**, use **Contract details**. Tick **Include contract details** when adding the first term or recording a term for a register entry with no current or upcoming term. **View term history** opens existing terms, renewals and supporting records. Choose **Record term** there to add a term. For an erroneous term, use **Delete** in its Actions column and review the effect before entering the reason. BillTrack blocks deletion when the term has protected linked records.

**Admin → System Settings → Estate features → Show additional allotment details** is off by default. Enable it and reload BillTrack to show the source notice, measurement reference, charge approval reference and effective date, and the paired dates and references for possession, termination, handover and alternative vacation deadlines. When an allotment or renewal starts before its letter date or exceeds the allowed duration, **Record date exception** opens on save. Enter the approved reference and reason, or cancel the prompt to edit the dates. The prompt works with additional details off.

### Missing contract details

When adding a contract in **Add Allotment** or **Edit Allotment**, tick **Not Available** beside any missing essential. If all essentials are missing, use **Mark all essential fields Not Available**. A blank required field without a tick prompts for an entry.

| When it applies | Essential details |
| --- | --- |
| All contracts | Award or extension letter reference, letter issue date, term start date, term end date and monthly charge basis |
| **Area × accepted rate** | Actual allotted area and accepted monthly rate per square foot |
| **Flat monthly charge** | Approved monthly amount |
| Notice-based initial charge | Accepted charge approval reference and, for area-based rent, measurement reference |

The register displays **Contract incomplete**. To update the draft, open **Edit**, clear the tick beside each detail you have found, enter the available values, and save. When all essentials are recorded, saving creates the contract term.

BillTrack uses saved terms to check eligible billing months and run expiry alerts. An incomplete draft stays outside both workflows, even if only a reference is missing. Bills already on record can still be viewed and paid.

### Agreed monthly charge

In **Contract details**, choose **Area × accepted rate** and enter the measured area and accepted monthly rate per square foot, or choose **Flat monthly charge** and enter the agreed monthly amount. Rate entry uses the term start date unless an effective date is supplied. The amount is available in **Raise Bill**.

Open **Rent rates** from the allotment row or the allottee profile. If the record has no term, choose **Record term**. If several award schedules exist, select the relevant original award. Choose **Record accepted rate** for the first amount and **Add rent revision** for each later change. Enter a specific date or choose **Start of a month** to use that month’s first day. **Use approved rate schedule** in **Raise Bill** selects the applicable rate for each billing month. BillTrack uses the rate in effect at month-end. Enter a reviewed monthly amount manually if the award calls for prorating a mid-month change.

**Accepted charge approval reference** identifies the document that approves the amount or rate, such as the allotment letter, a signed agreement or an office order. If the allotment letter states the charge, enter the same letter reference in both **Award / extension letter reference** and **Accepted charge approval reference**. For example, if letter `PD/ALLOT/042/2026` approves a flat monthly charge of ₹1,500, enter `PD/ALLOT/042/2026` in both reference fields. Use the separate document reference when the charge was approved separately.

**Details** shows the contractual dates and separate possession/handover evidence. **Edit term / handover** records corrections with a written reason. Record the possession or handover date together with its supporting reference. Recording termination preserves the original end date.

**Record renewal** creates a new term linked to the prior term, under the same register entry. The suggested dates follow the preceding term; confirm them from the actual letter. Previous possession, handover and approval evidence are not copied into a false new event. Performance and approval references are mandatory; at most two extensions follow the original award. Settle the assessed extension fee before recording the renewal.

## Requirements and attention

The initial notice-based award seeds police verification, GST registration and an applicable food-licence condition. Open its Details and **Update evidence** to enter submission/reference, verification date or unresolved issue. The server records the signed-in verifier. Not-applicable conditions require a reason; a missing food licence is not presented as verified.

The Dashboard's **Allotment and estate attention** section uses the server's India-local date. It shows expired/unvacated terms first, then unknown handover, ending terms within 90 calendar days inclusive, and outstanding requirements. Select an action to open the exact term or bill. List pagination and contained scrolling retain all actions. Approved continuation is distinguished from a mere renewal request/reference.

On phones the existing navigation becomes a horizontal scroll strip; forms use one column and record tables scroll within their labelled region. Keyboard focus and the shared modal return to the opening control when closed. Failed saves retain inputs; after an uncertain save, check refreshed records before retrying.

## Raise an allotment bill and waive holiday rent

From an allotment's Details, **View term bills** opens only the selected term; **Show all allottee bills** removes this scope. **Raise bill for term** carries its identity into Raise Bill. The normal Bills page also offers Raise Bill. Select the allottee and month range; a sole eligible term is selected automatically, while several eligible terms require selection. A range must fit one term. Use **Other monthly charges** for a charge outside an allotment. Its required reason is kept in the bill record for internal reference and omitted from individual and consolidated invoices. Record a missing term under Allotments.

Under **Monthly rent entry**, choose **Enter monthly rent directly** or **Calculate from area × rate**. For the calculation, enter the allotted area in square feet and the monthly rate per square foot. For example, 150 sq ft × ₹20 gives ₹3,000. BillTrack rounds the result to paise before applying waivers. The bill saves the full-month amount from the calculation. Then enter water, GST treatment and each month's electricity. To waive rent, enter the actual **Holiday start date** and **Holiday end date**. Both dates count as closed days. Select **Preview monthly amounts** to review each month's closed/calendar days, waiver, net rent, GST and total. Changing an input makes the preview stale and disables saving until previewed again. Existing months are labelled skipped; bills for other terms do not count as duplicates.

Example: June rent 3000 with closure June 10–19 gives 10/30 closed days, waiver 1000 and net rent 2000. GST is charged on 2000; utilities remain payable. A closure January 20–February 10 uses 31 days for January and 28 (or 29) for February. It does not assume 30-day months.

**Edit** starts from the original full rent rather than the discounted rent. Change both closure dates, or clear both to restore full rent, then preview before saving with a correction reason. Receipt records remain unchanged; excess receipts stay available for review. Invoice printouts show the allotment description under **Billed To** and show the applicable rent. Add any case-specific explanation to the bill Notes field for printing. Print Selected combines selected finalized bills for one allottee into one invoice, including historical and term-linked bills. Drafts print separately from finalized bills. Balances and credits are still calculated within each allotment term.

## Record rates and finalize a notice bill

Allotment Details also shows the **Rent schedule**. Record the actual accepted bid and its approval for notice-based awards. Renewals share the original award’s schedule. **Add rent revision** can preview the next 5% April increase for those awards. A different date or rate requires the authorized exception reference. For other awards, enter the agreed rate and effective date. New rates are saved as separate entries. Existing invoices keep their saved amounts.

Raise Bill identifies notice-governed terms. Choose **Use approved rate schedule** to use each month's approved full-month charge. The preview shows the basis and approval. An explicitly different amount needs a reviewed override reason. Missing annual approval blocks final issue unless its authorized exception is recorded. The dashboard flags missing rates/April approvals. These controls do not automatically increase rents or create bills on a clock schedule.

Set **Invoice raised date** from the actual finalized invoice. Leave it empty to save a draft; drafts show no final deadline, cannot receive receipts and do not add to dashboard debt. Draft printouts are marked prominently and print separately from finalized demands. Finalizing an unoverridden draft reselects the approved rate for each month; review its amount again before saving. Historical terms remain billable for valid past months. A term opened explicitly will not silently change to a different current term when the initial month is outside its dates.

## Confirm dispatch and track notice dues

Notice bills offer **Record email dispatch**. Enter the actual recipient, successful transmission's India-local date/time, message/provider reference and correction reason. Confirm the evidence checkbox and **Preview deadline**, then save. This records evidence and sends no email. The sending staff identity is recorded by the server. A draft or uncertain send is not proof of dispatch.

The notice deadline is seven days after raising. Delayed email does not move it: raised November 1 remains due November 8; dispatch November 10 starts interest on November 11. Interest is simple 12% annual on dated unpaid principal using actual days / 365, including leap years. Payments reduce principal from their dates; separately recorded interest receipts reduce interest only. An overdue undispatched invoice remains visible as deadline arrears even though interest waits for dispatch.

For amount/holiday/date corrections, preview the recalculated interest and retained receipts before saving a written reason. A paid, untaxed rent-only example with 1000 principal and 3.29 interest retained, then a 10/30-day rent waiver, shows 666.67 corrected rent, 2.19 policy interest, 333.33 excess principal and 1.10 excess interest for review. The correction does not erase receipts, fabricate a refund or reduce debt on other allotments. Bill Edit and dispatch forms collect their reason in the form itself, without a native browser prompt.

Notice invoices show raised and due dates and the notice interest rule. The award reference is available in the internal allotment record. Reviewed rates and holiday evidence remain available in the billing workflow. The invoice prints the text staff enter under Notes. When billing rules differ, the invoice shows the payment deadline for each month. Internal rule names and notice references are omitted. Use **Reports → Estate dues and security statement** for a cutoff-based view by allotment term. Manual drafts identify the allotment and term, and notice reminders require recorded email dispatch.

## Assess fees, fines and damage recovery

Open Allotment Details → **One-off charges and receipts**. **Assess charge** records a decided incident fine or damage recovery with description, assessment date, deadline and actual authority reference. Enter net amount and reviewed tax explicitly; enter zero tax when that is the approved treatment. The app does not infer a fine or tax treatment and does not add late interest to these charges.

**Assess extension fee** records the fee against the preceding term before the renewal letter exists. Notice terms use 1000 net, with explicit tax. Expand the saved extension fee under **One-off charges and receipts** and choose **Print extension fee demand**, then **Print / Save PDF**. The demand uses Invoice Format 2 and shows the assessment, receipts, waivers and exact current balance from that charge. Record the actual receipt or DD reference and date through **Record charge receipt**. Partial receipts leave the remaining balance open. **Record renewal** becomes available after the fee is settled. Satisfactory performance and approval references are still mandatory. Approval links the existing fee to the new term. The preceding term and renewal lineage remain in history. For continuous possession through an approved contiguous renewal, record the actual handover on the final occupied term. Leave the renewal possession date blank when the occupant did not re-enter.

The staff member who recorded a charge, or an administrator, can choose **Delete charge** on an assessment entered in error. Review the affected record and enter a written reason. The deletion is recorded in Activity History. Charges with receipts, reviewed financial decisions or linked renewals are handled through the correction workflow.

Expand an assessment to see amounts and retained receipts. **Correct receipt** needs a written reason and cannot move the receipt to another charge. A superuser can **Review waiver** or **Correct assessment** using an approval reference and reason. Waiver is the total cumulative waiver, not another amount to add. **Preview decision** shows old/new assessment, waiver and balance; **Confirm reviewed decision** applies only that reviewed version. Changing inputs requires a new preview. A changed balance or expired preview requires refresh/review again; an identical confirmed request is safe to repeat. These actions create no refund or external payment.

Dashboard totals include one-off assessments and their receipts/balances once. The separate breakdown shows approved waivers. **One-off charge overdue** opens the exact term and expanded charge; settled charges leave the overdue list. Security deposits are a separate liability; their reviewed paired application workflow follows below.

## Track security deposits

If a renewal was entered as a separate original award, a superuser can open **Allotments → View term history** and choose **Link as extension** on the later term. Select the preceding term, enter the renewal approval and performance references, and record the reason for the correction. If the later term already holds the fee assessed for this extension, select **Use the existing fee on this term for this extension**. Existing invoices and receipts retain their identities and amounts. The later term’s approved rent rates join the original award’s schedule. Independent deposits, conflicting rent schedules and different notice rules need review before the terms can be linked.

Allotment Details → **Security deposit · original award** shows the requirement, original/extended deadline, actual receipts, held amount, applications, refunds and forfeitures. The same account covers renewals. A superuser uses **Review security requirement** to enter the actual initial monthly rent and approved authority/reason. Empty required amount proposes three initial rents rounded upward to ₹100; exact hundreds stay unchanged. Record any approved additional requirement explicitly. An approved deadline extension keeps its own reference. Existing awards start without an invented requirement.

In **Review security requirement**, choose **Before allotment order** for the usual sequence of offer, deposit, and then final allotment order. Enter the offer date and deadline if known. When the deadline is blank, BillTrack uses the order date as the cutoff. Choose **After allotment order** to use the order date plus seven days. Previously reviewed awards keep their saved timing and deadline until reviewed. Enter the actual receipt date through **Record deposit receipt** and keep the receipt or DD reference. If a save is uncertain, inspect the movements before resubmitting the receipt.

For a renewal, select **Carry forward existing security deposit** in **Record renewal** or **Edit term** when the allottee chooses to retain the amount already held. BillTrack records the choice on the extension and continues to show the balance on the original award. If an earlier receipt is missing from BillTrack, enter its original date, amount and receipt reference once under the original award before recording the choice. A term entered as a separate original award must be reconciled with its preceding term before it can use this renewal option.

A superuser can **Apply security to bill** or **Apply security to charge**. Choose an actual outstanding obligation within this original award/renewal chain. The lists load current records when opened. Enter total amount and, for a bill, its explicit interest component; the rest is principal. The preview shows the target, components, remaining principal and new held amount. Security cannot pay future interest, exceed a debt or use a deposit from a different award. Confirmation creates one paired movement/payment; it is labelled **Security application — no new cash receipt** in the payment register. The money was received earlier.

**Record reviewed refund** lists unresolved bills/fines, deposit shortfalls and conditions. Physical handover is checked for refund clearance and estate alerts when **Show additional allotment details** is enabled in Admin. Record the handover in the final term under **More details** when enabled. Normal approval requires clearance. If actual authority permits an exception, record its explicit reference and reason; the exception remains visible in history. The refund-review deadline is three calendar months after the final term's expiry, but expiry or a deadline never confirms a refund. **Record approved forfeiture** requires actual approval and reduces held liability without paying outstanding debt. These forms record approved decisions and actual payment evidence; they do not send money.

Every decision requires **Preview security decision**, then **Confirm reviewed security decision**. Changed inputs invalidate the preview. A new receipt, changed estate evidence or an expired preview requires a fresh review. Repeating the identical confirmed decision returns its recorded result without spending again. Current and historical held balances cannot go negative. No ordinary receipt correction can rewrite or delete a paired settlement.

The dashboard separates cash principal collections, obligation balances and security liability. It flags missing requirements, overdue unpaid deposits and overdue refund review while money remains held. Refund review remains actionable after a partial refund or exception while a held balance remains. For a complete business-data export, use version 2. See Historical invoices and recovery below.
# Historical invoices and recovery

Open the historical invoice in Django Admin and choose **Review historical bill**. Select the documented allotment, enter the file reference or other reason, compare the preview and confirm. The original deadline, rent, GST and receipts survive assignment. For a separate notice conversion, reopen the review, supply the raising date and available dispatch and rate evidence, compare the interest and retained receipts, then confirm. Keep an uncertain record on its existing policy until the office has the evidence.

In **Admin → Export / import data and settings**, export a version 2 JSON before a transfer. Merge keeps matching local records and validates all relationships together. Replace requires reviewing the current affected records, an explicit confirmation and a reason. It writes a private pre-import JSON to `backups/admin-imports/` before replacing business records. To undo a completed replacement, review and restore that pre-import export using Replace. Protected financial actors must have matching local usernames. For complete installation recovery use a database and media backup as well. Business JSON covers estate records, billing and system settings. Accounts, audit logs, reminder history and email templates belong to the installation backup.

## Find more guides in BillTrack

Open **Knowledge Base** in the sidebar to search and read the billing, reporting and administration guides. The guide library comes from the repository’s `docs` folder and is refreshed when the frontend is built.
