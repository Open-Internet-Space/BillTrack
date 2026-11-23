# Estate records API — development reference

See the [staff workflow](ESTATE-WORKFLOW.md) and [changelog](../CHANGELOG.md) for operator guidance and migration scope.

## Records

Authenticated existing approved accounts can use paginated CRUD endpoints:

- `/api/shops/`: persistent code/name/location/category and space type, advertised area, authorized services, operating hours, retirement and initial availability evidence. Codes are canonical uppercase; approximate area is not the actual billing area.
- `/api/allotments/`: shop/allottee links, source notice, award/letter dates, actual measured area/reference, contractual dates, renewal/approval/performance references, possession/handover/termination evidence. Response includes shop code, allottee name, effective end, contractual status, original award and extension number.
- `/api/allotment-requirements/`: applicable conditions, deadlines, submitted evidence, verification and unresolved issues. The server records the verifying user; supplying another `verified_by` ID does not impersonate that user.

Search uses `?search=...`. Shops filter by `category`, `space_type`, `active`; allotments by `shop`, `tenant`, `renewal_of`; requirements by `allotment`, `kind`, `applicable`. Lists use existing REST page pagination. Changes use the existing written `change_reason` or `X-Change-Reason` header. Deletion requires the existing preview/confirmation workflow and cannot erase protected history. Allottees with bill or allotment history deactivate instead.

Example original award request to `/api/allotments/` (synthetic values, not instructions to create real records):

```json
{
  "shop": 1,
  "tenant": 7,
  "source_notice": "368/2025",
  "award_reference": "Award reference from the official letter",
  "letter_issued_on": "2026-07-01",
  "start_date": "2026-07-01",
  "end_date": "2027-06-30",
  "actual_area": "150.0000",
  "measurement_reference": "Official measurement file reference"
}
```

Creating an original award under notice 368/369 seeds police verification (letter + 30 calendar days), GST submission (letter + 90 unless already recorded), and a food-licence condition for food/night categories. The same domain path is used by API and Admin; ordinary subsequent saves do not create duplicate conditions. Renewal terms retain initial-award requirements on the original term. Marking an item not applicable requires a reason; verification requires submitted evidence and the actual verifying user.

To record first possession, confirm initial shop availability or prior handover, then PATCH the term with `possession_date`, `possession_reference`, and a correction reason. Both dates/reference pairs are validated. Contract expiry does not record physical handover. Renewal is a new term with `renewal_of`, valid non-overlapping dates and approval/performance references; fee settlement is integrated in the later finance increment, so these development endpoints are not a substitute for that complete workflow.

## Attention

`GET /api/estate/attention/` returns a paginated action list. Filter with `?kind=ending`, `expired_unvacated`, `handover_unknown`, `requirement`, or `availability_unknown`. Each row has the server's India-local `as_of` date and shop identity; term/requirement rows include their record IDs and dates for navigation.

The ending window includes today through 90 calendar days ahead. Expired terms with no physical handover remain actionable; approved current continuation is recognized. Missing food licences remain pending action even without a calendar due date. Unknown availability is not labelled vacant. Financial attention for deposits, annual revisions, charges and refund review is added with those sequential tasks.

## Remaining integration

React shop/allotment screens, linked bills, holiday preview/net rent, reviewed rent schedules, notice deadlines/interest, evidence forms and dashboard navigation are implemented; see [staff workflow](ESTATE-WORKFLOW.md). The development release also includes deposit and charge actions, reviewed historical assignment and conversion, version 2 transfer, and estate reports and reminders. Apply these migrations to the daily-work database only during the reviewed rollout. Tests and browser checks use disposable/synthetic databases.

## Linked billing and holiday waivers

New bills require `allotment` (an existing term belonging to `tenant`) or explicit `billing_category: "other"` with explanatory notes. New `legacy` bills are rejected by the API. Existing bills retain legacy/unassigned identity; ordinary edits cannot change tenant/term/category. Filter bills by `allotment`, `allotment__shop` or `billing_category`; searches include shop code. `tenant_display_name` on linked bills includes that code. Payment responses include `bill_allotment` and `bill_shop_code`.

`full_month_rent` records original rent; `rent` is server-calculated net rent. Optional `holiday_start_date` and `holiday_end_date` must both be present, ordered and overlap the billing month/range. Dates are inclusive and clipped to each month; net = full rent × (calendar days − closed days) ÷ calendar days, rounded HALF_UP to two decimals. `holiday_closed_days` and `holiday_waiver` are read-only. GST uses net rent; water/electricity are unchanged. Clearing both dates restores full rent without deleting receipts; an excess receipt remains available for review.

`POST /api/bills/preview/` accepts the same payload as `/api/bills/bulk-create/`. It validates every month, returns `months` with calendar/closed days, original/net rent, waiver, GST splits, utilities, total and `already_exists`, and writes no records/settings. Example:

```json
{"tenant": 1, "allotment": 11, "billing_category": "allotment",
 "from_month": 1, "from_year": 2026, "to_month": 2, "to_year": 2026,
 "full_month_rent": "3100.00", "rent_override_reason": "Reviewed full-month amount for this documented example",
 "raised_date": null, "holiday_start_date": "2026-01-20",
 "holiday_end_date": "2026-02-10", "water": "50.00",
 "month_items": [{"year": 2026, "month": 1, "electric": "100.00"},
                 {"year": 2026, "month": 2, "electric": "200.00"}]}
```

This returns January rent 1900.00 and February rent 1992.86. Ranges are ordered, within 2000–2100 and at most 36 months; electricity rows must be unique months within the range. Bulk validates all rows before atomic creation and reports existing months in `skipped`, scoped to the selected term. Single creation uses month/year instead of from/to fields. `POST /api/bills/{id}/preview/` validates a proposed partial edit without saving it; apply a reviewed edit with PATCH and the normal correction reason.

Migration 0008 adds empty evidence fields to old bills; 0009 marks them legacy/unassigned without altering amounts, dates, receipt allocations or tax snapshots. Version 1 import accepts missing holiday evidence and rejects inconsistent supplied evidence. Version 2 exports cover the full estate graph.

## Reviewed rent schedule and notice policy

`/api/rent-revisions/` provides authenticated audited CRUD, filtered by `original_award`. Required fields: original award ID (not renewal ID), `effective_date`, positive `rate` with four decimal places, `approval_reference` and `reason`. The first entry's date explicitly records which past increases are already included. Later ordinary entries must be the next 5% April increase, no earlier than April 2026; an authorized `exception_reference` is needed for a different date/rate. Award/effective date is unique. Billed rates cannot be moved or rewritten. `GET /api/rent-revisions/{id}/annual-preview/?through=2027-04-01` returns proposed dates/rates after the latest approved entry through that date, without posting them. Preview years are 2000–2100.

Allotment responses expose `notice_governed`. New bills on these terms automatically use `billing_policy: "notices_368_369"`; other new bills use `legacy_receipt`. Clients cannot override this choice or change an existing bill's policy through ordinary PATCH. Existing bills remain explicitly legacy until the separate reviewed conversion workflow.

For notice bills, omit `full_month_rent` to derive that month's approved rate × actual term area, HALF_UP to two places. An explicitly different full-month amount requires `rent_override_reason`. A missing April approval blocks final issue unless `rate_exception_reference` records authorized authority; a draft can still be prepared. Bill responses preserve `rent_revision`, `rate_snapshot`, `area_snapshot` and `rent_revision_reference`. Changes to schedules/measurements do not rewrite saved bills. Finalizing an unoverridden draft or correcting its billing month reselects that month's approved basis before holiday proration.

`raised_date: null` is a draft: no finalized due date/debt, no receipts, and no inclusion in dashboard debt. A final notice invoice requires a nonfuture raised date; its deadline is raised date + seven calendar days, excluding the raised day. `due_date` is server-calculated. Legacy `issue_date` keeps its confirmed-receipt meaning and stays empty on notice bills.

Record confirmed dispatch using timezone-aware `email_dispatched_at`, `dispatch_recipient` and `dispatch_message_reference`. The server owns `dispatch_sender`; supplied user IDs are ignored. The timestamp must be no later than now, and its India-local date must not precede raising. This API records evidence only and sends no email. Draft generation, SMTP attempts and unsigned invoice preparation do not confirm dispatch.

Notice interest is fixed 12% annual simple interest on unpaid billed principal (net rent + GST + utilities), with actual elapsed days / 365. It starts only after the later of the deadline and confirmed dispatch's India-local date. Dated principal payments reduce later segments; interest payments reduce interest only. Only the final accrued total rounds HALF_UP to two places. Thus raised November 1 -> due November 8; confirmed dispatch November 10 -> first chargeable day November 11. 1000 principal for 10 days -> 3.29; paying 400 after five days, then five more days -> 2.63.

Preview responses include full rent, rate/area/reference, missing-revision warnings, due/status and retained receipts. Edit previews additionally show old versus recalculated interest and excess principal/interest for review. A written correction reason is mandatory; saving recalculates under the saved policy and preserves all receipt records. It creates no refund or cash movement. `days_overdue` remains chargeable interest days; `payment_days_overdue` separately exposes deadline arrears even while dispatch is pending. `deadline_established` and `is_draft` drive staff controls. Attention adds `kind=revision_due` for active terms needing an accepted rate or April approval.

Migrations 0010–0013 add schedules, policy/date evidence, rate snapshots and database guards. Existing amounts/dates/payments remain unchanged and old bills get `legacy_receipt`. Import validation binds payment checks to the staged graph rather than potentially colliding live IDs. The complete estate graph can be exported and restored through version 2 transfer.

## One-off assessed charges

Authenticated `/api/estate-charges/` lists/creates assessments; filter by `allotment` or `kind`. Required fields are `allotment`, `kind` (`extension_fee`, `incident_fine`, `damage_recovery`), `description`, `assessed_on`, `authority_reference`, `net_amount`, explicit `tax_amount` (including zero) and `due_date`. Assessment cannot be future-dated; deadline cannot precede it. Notice extension fees require 1000 net, with separately reviewed tax. Only one fee belongs to a preceding term, and it is linked to the following approved renewal after settlement. No automatic interest is added to charges.

Responses include gross, paid, waived, balance, status, overdue, server-owned creator and nested receipts. Ordinary corrections require the normal written reason, cannot change ownership/kind or assessed amounts, and cannot edit waiver fields. Assessments have no DELETE path. `/api/estate-charge-payments/` records an actual positive amount, receipt date, `receipt_reference`, optional notes and charge ID. Date must be between assessment and today; payments plus waiver cannot exceed gross. Server owns recorder/source. Cash-receipt corrections retain charge identity; administrator deletion uses the existing affected-record preview/reason. Security settlements cannot be fabricated or deleted as ordinary receipts.

Only a superuser may POST `/api/estate-charges/{id}/decision-preview/` with either `action: "waiver"` and cumulative `waiver_amount`, or `action: "assessment"` and revised `net_amount`/`tax_amount`. Both require approval `reference` and written `reason`. Preview writes no financial or activity record. It returns `before`, `after` and a signed `confirmation`, bound to the charge UUID, reviewer, full current assessment/receipt fingerprint and unique operation. POST that confirmation to `apply-decision/` within 600 seconds. Changed balances/evidence reject; repeating the same applied operation returns `already_applied: true` without another write. Refresh and preview again if stale. Receipts remain intact.

Allotment responses add `renewal_fee_settled` and `renewal_fee_charge_id`. Notice renewal approval requires settlement plus performance/approval evidence. Recorded renewal lineage cannot be detached or reassigned. Dashboard totals include charge gross/receipts/balance once, with separate `charge_summary` assessed/paid/waived/outstanding and open/overdue counts. Attention `kind=charge_due` includes exact charge ID for direct detail navigation.

Migration 0014 is additive and refreshes audit guards. Existing data is unchanged. Use version 2 for a complete estate export.

## Security liability and reviewed decisions

`GET /api/estate-security/{original_award_id}/` returns the original award's approved requirement/basis/deadlines, received/refunded/applied/forfeited/held totals, outstanding initial requirement, refund-review deadline/state, immutable movements and `clearance_issues`. A renewal uses the same original account. Required amount is the approved three-initial-rent basis rounded upward to a hundred (exact hundreds stay unchanged); a referenced additional requirement is explicit. Original deadline is letter date + seven days; an approved extension is separate. Refund review is three calendar months after the final approved term's effective end. A paid initial requirement is measured against cumulative receipts, not remaining held money after legitimate debits; there is no automatic replenishment demand.

Authenticated `POST /api/security-movements/` records only actual receipts: original award ID, positive `amount`, `effective_date`, actual payment/DD `reference` and `reason`. Server owns kind/actor/identity. GET lists/filtering by original award or kind are supported; no update/delete path exists. Admin can record receipts and view immutable history. Dates must fall between the original letter and today. Check the movement list before retrying an uncertain ordinary receipt submission.

Only a superuser can POST `/api/estate-security/{id}/decision-preview/` with approval/payment `reference`, written `reason` and one action:

- `requirement`: `initial_monthly_rent`, optional approved `required_amount` (omitting proposes the rounded basis), optional `extended_due_date`/`extension_reference` pair. Original due date is retained; re-review resets refund clearance to pending.
- `apply_bill`: total `amount`, explicit `interest_amount` (default zero), `effective_date`, and `bill`. Principal is total minus interest. Neither component may exceed its unpaid balance; interest must have accrued by the actual application date.
- `apply_charge`: `amount`, `effective_date`, and `charge`.
- `refund`: `amount`, actual `effective_date`, and optional explicit `exception_reference`. First record the requirement. Normal refund requires term end, actual handover, received security requirement, no unresolved bills/charges across the person and no outstanding applicable conditions. An explicit authorized exception and reason are necessary to override unresolved matters. These issues are shown before confirmation.
- `forfeit`: `amount` and `effective_date`, with actual approval reference/reason. It reduces held liability and does not pay a bill or fine.

Preview returns `before`, `after`, applicable clearance issues, authoritative principal/interest/target settlement details, signed `confirmation` and 600-second validity. It writes no money or activity. POST the token to `apply-decision/`. Confirmation binds reviewer, original-award UUID, business date, requirement/term/document graph, actual bills/charges/receipts, deposit movements and relevant policy settings. Stale, expired, wrong-reviewer, malformed or different-account requests reject. Successful retries return `already_applied: true` without another debit. The writer is reserved before checking the fresh graph, and an application inserts its movement and payment in one transaction with the same unique operation ID. Failure of either side rolls back both and their audit records.

Targets must be in the same original award/renewal chain and allottee; another shop under the same person is not eligible. Current and historical held balances cannot become negative, including backdated decisions. Payment responses expose read-only `source` and `operation_id`. Paired settlements cannot be forged, converted or deleted as ordinary receipts. Existing payment rows migrate as receipts without changing their amounts/dates. No action transfers money externally or sends mail.

Dashboard `total_collected` is cash principal receipts (including one-off cash receipts); `total_settled` includes principal settled from security. Remaining obligation balances include both settlement sources once. `security_summary` separately shows received/held/refunded/applied/forfeited; `charge_summary.paid` means cash, with security in `applied`. Interest collections remain separate from principal. Attention adds `deposit_due`, `refund_review` (held money still requiring action after the review deadline) and `security_review` (missing reviewed requirement). Full estate cash/settlement statements and transfer graph remain Tasks 8–9.

Existing `payments` reports contain actual cash receipts only. Existing bill/payment `statement` reports retain combined settled principal/interest, split `received` cash from `security_applied` noncash settlement, and reconcile closing dues using both. Reviewed exports use these same columns and notes. The cutoff-based estate statement (report=estate) includes monthly bills, one-off charges and deposit movements. See Reports for filters and historical reconstruction limits.
# Reviewed correction of historical bills

Superusers can POST to `/api/bills/{id}/legacy-preview/` using action `link`, an explicit `allotment` ID and a written `reason`. After assignment a separate `convert` review accepts `raised_date`, the applicable `rent_revision` ID or documented rent override and authority. Confirmed dispatch requires `email_dispatched_at`, `dispatch_sender` (the actual staff account), `dispatch_recipient` and `dispatch_message_reference` together. Dates must be compatible with every retained receipt.

The preview returns before/after amounts, dates, receipt allocations and a signed confirmation valid for ten minutes. POST that confirmation to `/api/bills/{id}/legacy-confirm/`. A retry of a completed operation returns `already_applied`. After a stale or expired review, read the current bill and preview again.
