# Email templates and manual Mail Merge

BillTrack saves **named reusable templates**, not allottee-specific emails. Like Word Mail Merge, it fills a template with the selected allottee and bill details to prepare a temporary email. It never sends mail, attaches files, confirms receipt, marks dispatch or records a sent reminder. SMTP is not required.

## Save reusable wording

**Admin → Email templates** lets administrators manage reusable wording. BillTrack includes **Invoice covering letter**, **Payment reminder** and **Overdue notice**. A template can specify its own CC addresses. Mark attachment-dependent templates, such as **Demand of dues**, **Manual only** to keep them out of the reminder sender.

Use **Insert placeholder** above the form: choose Subject or Body, choose a labelled field with its description, and click Insert placeholder. Clicking inside Subject or Body selects that destination automatically. The field is inserted at the cursor or replaces selected text. Save the template afterward. Multiline fields are offered for the Body only.

Subject and body accept these literal placeholders:

| Placeholder | Contents |
| --- | --- |
| `{allottee_name}` | Selected allottee's name |
| `{allotment_description}` | Optional identifier for this specific allotment, for example Shop 12 |
| `{organisation_name}` | Private organisation name from System Settings |
| `{signing_authority}` | Private signing authority |
| `{preparation_date}` | Date of generation |
| `{billing_start_month}` | Earliest month and year among the selected bills |
| `{billing_end_month}` | Latest month and year among the selected bills |
| `{bill_details}` | Selected references, periods, receipt/due status and remaining principal/penalty |
| `{outstanding_total}` | Outstanding total for selected bills in INR |

For example, subject `Payment reminder for {allottee_name}` and body `Dear {allottee_name},` followed by `{bill_details}`. Use `{{` and `}}` for literal braces. HTML, expressions, attribute access, formatting instructions and template code are not executed. Subjects must expand to one line; put bill details in the body. Wording never changes billing calculations.

**Admin → System Settings → Manual email drafts** stores default CC and BCC addresses. Templates and recipient settings stay in private SQLite, outside source control. Only administrators with the appropriate model permissions can change saved templates.

## Merge, edit and copy

You can also select bills for one allottee in **Bills → Draft Email**. Allottee drafts start with outstanding bills. Change the selection to include settled bills for a covering letter, or clear it for a general email. Inactive allottees can still have correspondence prepared.

Choose **Prepare Gmail** in the allottee’s Actions, or open **Email Drafts** from the sidebar. Choose the bills and a saved template, then choose **Generate Draft**. **Demand of dues** uses the selected billing months and the saved allotment description. Review and edit To, CC, BCC, Subject and Body. BillTrack takes To from the allottee’s saved email. It uses template CC addresses when provided and otherwise uses the System Settings default. BCC comes from System Settings. Case-specific edits are temporary.

Choose **Open in Gmail** to open a compose window in a new tab. Verify the sender and recipients, attach the signed bill, and send from Gmail. For a long message, use **Copy Body** and paste it into Gmail before attaching the bill.

Copy each field into the official mailbox, attach invoices manually if needed, check current amounts and recipients, then send there. Copy buttons report success; if clipboard access is unavailable (including some LAN HTTP browsers), the field is selected for Ctrl+C or the device Copy command. BillTrack cannot confirm that the email was sent.

Changing the allottee or leaving with temporary text prompts before discarding it. Refresh from current records also requires confirmation before replacing recipients and wording. Changing the template or bill selection requires regeneration before copying the new selection. Reload templates picks up Admin changes. Retry bills handles a temporary connection failure without leaving the workspace.

Amounts carry the generation timestamp and may change later. A notice can include bills that are not overdue; review dates and wording before sending. Bills without confirmed receipt are explicitly labelled and have no asserted payment deadline.

There is no saved merged-email list or history. Closing/reloading discards the temporary email; the browser's usual unsaved-change warning applies. Save reusable wording in Admin and retain actual sent correspondence in the official mailbox.

## Backups and development

Full SQLite backups preserve saved templates and default CC and BCC addresses. Business-data JSON exports include the recipient settings as part of System Settings and omit templates. Generated drafts in BillTrack are temporary.

This change adds schema migration 0002_email_templates to the clean BillTrack lineage. It is not a migration from the historical EstateManagement database. Development does not alter the daily installation.

The [component map](COMPONENT-MAP.md#email-drafts) lists exact source files. `/api/email-templates/` reads active templates; `/api/email-drafts/generate/` accepts allottee_id, bill_ids and template_id and returns a temporary merged email with no-store caching. Only approved authenticated users have access. There is no API for saving allottee emails or sending mail.

The same saved templates can be selected in [Admin SMTP reminders](EMAIL-REMINDERS.md), which has a separate editable preview and Confirm and send action. The Email Drafts workspace itself remains manual copying only.
