# Shop and allotment workflows

## Shop identity and availability

Open **Shops** to search code, name or location and filter physical availability or active/retired status. **Add shop** records the persistent unit. Advertised area is approximate; actual measured area belongs on its allotment. Record permitted services/hours and approved exceptions from the relevant documents.

Initial availability requires a date and reference. A shop without availability/possession evidence remains **Availability unknown**. An expired contract does not make a shop vacant. Use **History** for its prior terms, then **Record allotment for this shop**. Retire a unit through Edit instead of deleting protected history.

## Allotment and renewal

Open **Allotments**, or **Shop history** beside an allottee, to review the correct person/shop/term. Record the official notice, award/letter reference and date, approved start/end, actual area and measurement reference. Do not copy an advertised area/rate as though it were an accepted measurement/bid.

**Details** shows the contractual dates and separate possession/handover evidence. **Edit term / handover** records corrections with a written reason. Initial possession requires confirmed availability or earlier handover; dates and references are paired. Recording termination preserves the original end date.

**Record renewal** creates a new term linked to the prior term, with the same shop/allottee. The suggested dates follow the preceding term; confirm them from the actual letter. Previous possession, handover and approval evidence are not copied into a false new event. Performance and approval references are mandatory; at most two extensions follow the original award. Fee-settlement controls are completed in the later charges increment, so the current screens are development-stage records rather than a complete renewal authorization workflow.

## Requirements and attention

The initial notice-based award seeds police verification, GST registration and an applicable food-licence condition. Open its Details and **Update evidence** to enter submission/reference, verification date or unresolved issue. The server records the signed-in verifier. Not-applicable conditions require a reason; a missing food licence is not presented as verified.

The Dashboard's **Allotment and estate attention** section uses the server's India-local date. It shows expired/unvacated terms first, then unknown handover, ending terms within 90 calendar days inclusive, requirements and unknown availability. Select an action to open the exact shop/term. List pagination and contained scrolling retain all actions. Approved continuation is distinguished from a mere renewal request/reference.

On phones the existing navigation becomes a horizontal scroll strip; forms use one column and record tables scroll within their labelled region. Keyboard focus and the shared modal return to the opening control when closed. Failed saves retain inputs; after an uncertain save, check refreshed records before retrying.

## Still being implemented

Saved legacy bills retain their existing policy. New notice-governed bills use the notice rules below. Review legacy assignment and policy conversion against supporting records.

## Raise a shop bill and waive holiday rent

From an allotment's Details, **View term bills** opens only that shop's term; **Show all allottee bills** removes this scope. **Raise bill for term** carries its identity into Raise Bill. The normal Bills page also offers Raise Bill. Select the allottee and month range; a sole eligible term is selected automatically, while several eligible terms require selection. A range must fit one term. Use **Other monthly charges** only for an explained non-shop charge; record a missing shop term under Allotments.

Enter **Full-month rent**, water, GST treatment and each month's electricity. To waive rent, enter the actual **Holiday start date** and **Holiday end date**. Both dates count as closed days. Select **Preview monthly amounts** to review each month's closed/calendar days, waiver, net rent, GST and total. Changing an input makes the preview stale and disables saving until previewed again. Existing months are labelled skipped; other shops' bills do not count as duplicates.

Example: June rent 3000 with closure June 10–19 gives 10/30 closed days, waiver 1000 and net rent 2000. GST is charged on 2000; utilities remain payable. A closure January 20–February 10 uses 31 days for January and 28 (or 29) for February. It does not assume 30-day months.

**Edit** starts from the original full rent rather than the discounted rent. Change both closure dates, or clear both to restore full rent, then preview before saving with a correction reason. Receipt records remain unchanged; excess receipts stay available for review. Invoice printouts identify the shop and show the applicable rent. Add any case-specific explanation to the bill Notes field for printing. Selected invoices consolidate only within the same allottee and term.

## Record rates and finalize a notice bill

Allotment Details includes **Approved rent schedule**. **Record accepted rate** stores the actual accepted bid, explicit as-of date, approval reference and reviewed basis. Do not substitute the advertised bid floor. A rate already revised as of April does not increase twice. Renewals share their original award's schedule. **Record annual revision** can preview the next 5% April increase; record the actual approval before saving. A different rate/date requires the authorized exception reference. Billed rates cannot be rewritten; later approvals become new rows.

Raise Bill identifies notice-governed terms. Leave full-month rent empty to use each month's approved rate × measured area; preview shows that basis and approval. An explicitly different amount needs a reviewed override reason. Missing annual approval blocks final issue unless its authorized exception is recorded. The dashboard flags missing rates/April approvals. These controls do not automatically increase rents or create bills on a clock schedule.

Set **Invoice raised date** from the actual finalized invoice. Leave it empty to save a draft; drafts show no final deadline, cannot receive receipts and do not add to dashboard debt. Draft printouts are marked prominently and print separately from finalized demands. Finalizing an unoverridden draft reselects the approved rate for each month; review its amount again before saving. Historical terms remain billable for valid past months. A term opened explicitly will not silently change to another current shop when the initial month is outside its dates.

## Confirm dispatch and track notice dues

Notice bills offer **Record email dispatch**. Enter the actual recipient, successful transmission's India-local date/time, message/provider reference and correction reason. Confirm the evidence checkbox and **Preview deadline**, then save. This records evidence and sends no email. The sending staff identity is recorded by the server. A draft or uncertain send is not proof of dispatch.

The notice deadline is seven days after raising. Delayed email does not move it: raised November 1 remains due November 8; dispatch November 10 starts interest on November 11. Interest is simple 12% annual on dated unpaid principal using actual days / 365, including leap years. Payments reduce principal from their dates; separately recorded interest receipts reduce interest only. An overdue undispatched invoice remains visible as deadline arrears even though interest waits for dispatch.

For amount/holiday/date corrections, preview the recalculated interest and retained receipts before saving a written reason. A paid, untaxed rent-only example with 1000 principal and 3.29 interest retained, then a 10/30-day rent waiver, shows 666.67 corrected rent, 2.19 policy interest, 333.33 excess principal and 1.10 excess interest for review. The correction does not erase receipts, fabricate a refund or reduce another shop's debt. Bill Edit and dispatch forms collect their reason in the form itself, without a native browser prompt.

Notice invoices show raised and due dates, the shop and the notice interest rule. Reviewed rates and holiday evidence remain available in the billing workflow. The invoice prints the text staff enter under Notes. Mixed-policy selections identify each monthly policy; saved legacy bills retain their older terms. Use **Reports → Estate dues and security statement** for a cutoff-based view by shop or allotment. Print selections keep each term and unassigned legacy bills separate. Manual drafts label the shop and term, and notice reminders require recorded email dispatch.

## Assess fees, fines and damage recovery

Open Allotment Details → **One-off charges and receipts**. **Assess charge** records a decided incident fine or damage recovery with description, assessment date, deadline and actual authority reference. Enter net amount and reviewed tax explicitly; enter zero tax when that is the approved treatment. The app does not infer a fine or tax treatment and does not add late interest to these charges.

**Assess extension fee** records the fee against the preceding term before the renewal letter exists. Notice terms use 1000 net, with explicit tax. Record the actual receipt or DD reference and date through **Record charge receipt**. Partial receipts leave the remaining balance open; the app blocks overpayment. **Record renewal** becomes available after the fee is settled; satisfactory performance and approval references are still mandatory. Approval links the existing fee to the new term. The preceding term and renewal lineage remain in history. For continuous possession through an approved contiguous renewal, record the actual handover on the final occupied term. Leave the renewal possession date blank when the occupant did not re-enter.

Expand an assessment to see amounts and retained receipts. **Correct receipt** needs a written reason and cannot move the receipt to another charge. A superuser can **Review waiver** or **Correct assessment** using an approval reference and reason. Waiver is the total cumulative waiver, not another amount to add. **Preview decision** shows old/new assessment, waiver and balance; **Confirm reviewed decision** applies only that reviewed version. Changing inputs requires a new preview. A changed balance or expired preview requires refresh/review again; an identical confirmed request is safe to repeat. These actions create no refund or external payment.

Dashboard totals include one-off assessments and their receipts/balances once. The separate breakdown shows approved waivers. **One-off charge overdue** opens the exact term and expanded charge; settled charges leave the overdue list. Security deposits are a separate liability; their reviewed paired application workflow follows below.

## Track security deposits

Allotment Details → **Security deposit · original award** shows the requirement, original/extended deadline, actual receipts, held amount, applications, refunds and forfeitures. The same account covers renewals. A superuser uses **Review security requirement** to enter the actual initial monthly rent and approved authority/reason. Empty required amount proposes three initial rents rounded upward to ₹100; exact hundreds stay unchanged. Record any approved additional requirement explicitly. The original due date is letter date + seven days; an approved extension keeps its own reference. Existing awards start without an invented requirement.

**Record deposit receipt** records actual money received with its date and receipt/DD evidence. It adds held security; it does not settle a bill. Receipt history is retained. If the response is uncertain, inspect the movements before resubmitting an ordinary receipt.

A superuser can **Apply security to bill** or **Apply security to charge**. Choose an actual outstanding obligation within this original award/renewal chain. The lists load current records when opened. Enter total amount and, for a bill, its explicit interest component; the rest is principal. The preview shows the target, components, remaining principal and new held amount. Security cannot pay future interest, exceed a debt or use another shop's deposit. Confirmation creates one paired movement/payment; it is labelled **Security application — no new cash receipt** in the payment register. The money was received earlier.

**Record reviewed refund** lists unresolved bills/fines, deposit shortfalls, conditions and handover. Normal approval requires clearance. If actual authority permits an exception, record its explicit reference and reason; the exception remains visible in history. The refund-review deadline is three calendar months after the final term's expiry, but expiry or a deadline never confirms a refund. **Record approved forfeiture** requires actual approval and reduces held liability without paying outstanding debt. These forms record approved decisions and actual payment evidence; they do not send money.

Every decision requires **Preview security decision**, then **Confirm reviewed security decision**. Changed inputs invalidate the preview. A new receipt, changed estate evidence or an expired preview requires a fresh review. Repeating the identical confirmed decision returns its recorded result without spending again. Current and historical held balances cannot go negative. No ordinary receipt correction can rewrite or delete a paired settlement.

The dashboard separates cash principal collections, obligation balances and security liability. It flags missing requirements, overdue unpaid deposits and overdue refund review while money remains held. Refund review remains actionable after a partial refund or exception while a held balance remains. For a complete business-data export, use version 2. See Historical invoices and recovery below.
# Historical invoices and recovery

Open the historical invoice in Django Admin and choose **Review historical bill**. Select the documented allotment, enter the file reference or other reason, compare the preview and confirm. The original deadline, rent, GST and receipts survive assignment. For a separate notice conversion, reopen the review, supply the raising date and available dispatch and rate evidence, compare the interest and retained receipts, then confirm. Keep an uncertain record on its existing policy until the office has the evidence.

In **Admin → Export / import data and settings**, export a version 2 JSON before a transfer. Merge keeps matching local records and validates all relationships together. Replace requires reviewing the current affected records, an explicit confirmation and a reason. It writes a private pre-import JSON to `backups/admin-imports/` before replacing business records. To undo a completed replacement, review and restore that pre-import export using Replace. Protected financial actors must have matching local usernames. For complete installation recovery use a database and media backup as well. Business JSON covers estate records, billing and system settings. Accounts, audit logs, reminder history and email templates belong to the installation backup.

## Find more guides in BillTrack

Open **Knowledge Base** in the sidebar to search and read the billing, reporting and administration guides. The guide library comes from the repository’s `docs` folder and is refreshed when the frontend is built.
