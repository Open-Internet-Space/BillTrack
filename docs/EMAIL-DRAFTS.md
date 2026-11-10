# Email templates and manual Mail Merge

BillTrack saves **named reusable templates**, not allottee-specific emails. Like Word Mail Merge, it fills a template with the selected allottee and bill details to prepare a temporary email. It never sends mail, attaches files, confirms receipt, marks dispatch or records a sent reminder. SMTP is not required.

## Save reusable wording

Admin → Email templates allows adding, editing, disabling or deleting named templates. Three generic templates are installed once: Invoice covering letter, Payment reminder and Overdue notice. Save wording with placeholders, rather than real vendor details. Each template can be used for any allottee.

Use **Insert placeholder** above the form: choose Subject or Body, choose a labelled field with its description, and click Insert placeholder. Clicking inside Subject or Body selects that destination automatically. The field is inserted at the cursor or replaces selected text. Save the template afterward. Multiline fields are offered for the Body only.

Subject and body accept these literal placeholders:

| Placeholder | Contents |
| --- | --- |
| `{allottee_name}` | Selected allottee's name |
| `{allotment_description}` | Optional identifier for this specific allotment, for example Shop 12 |
| `{organisation_name}` | Private organisation name from System Settings |
| `{signing_authority}` | Private signing authority |
| `{preparation_date}` | Date of generation |
| `{bill_details}` | Selected references, periods, receipt/due status and remaining principal/penalty |
| `{outstanding_total}` | Outstanding total for selected bills in INR |

For example, subject `Payment reminder for {allottee_name}` and body `Dear {allottee_name},` followed by `{bill_details}`. Use `{{` and `}}` for literal braces. HTML, expressions, attribute access, formatting instructions and template code are not executed. Subjects must expand to one line; put bill details in the body. Wording never changes billing calculations.

Admin → System Settings → Manual email drafts stores default CC addresses. Templates and CC settings stay in private SQLite, outside source control. Only administrators with the appropriate model permissions can change saved templates.

## Merge, edit and copy

Use **Allottees → Email Draft**, or select bills for one allottee in **Bills → Draft Email**. The Email Drafts navigation item also opens the workspace. Allottee drafts start with outstanding bills; change the selection to include settled bills for a covering letter or no bills for a general email. Multiple allottees cannot share one email. Inactive allottees can still have correspondence prepared.

Choose a saved template and allottee. Expand **Saved template wording (before merge)** to see placeholders. Generate Draft fills in current details. Review and edit To, CC, Subject and Body. These case-specific edits are temporary and do not update the saved template. Missing vendor email is clearly warned about. Enter email addresses rather than display-name syntax; default CC addresses accept comma or semicolon separators.

Copy each field into the official mailbox, attach invoices manually if needed, check current amounts and recipients, then send there. Copy buttons report success; if clipboard access is unavailable (including some LAN HTTP browsers), the field is selected for Ctrl+C or the device Copy command. BillTrack cannot confirm that the email was sent.

Changing the allottee or leaving with temporary text prompts before discarding it. Refresh from current records also requires confirmation before replacing recipients and wording. Changing the template or bill selection requires regeneration before copying the new selection. Reload templates picks up Admin changes. Retry bills handles a temporary connection failure without leaving the workspace.

Amounts carry the generation timestamp and may change later. A notice can include bills that are not overdue; review dates and wording before sending. Bills without confirmed receipt are explicitly labelled and have no asserted payment deadline.

There is no saved merged-email list or history. Closing/reloading discards the temporary email; the browser's usual unsaved-change warning applies. Save reusable wording in Admin and retain actual sent correspondence in the official mailbox.

## Backups and development

Full SQLite backups preserve saved templates and default CC addresses. Business-data JSON exports omit templates; they include default CC as part of System Settings. No merged email needs backup because it is never persisted.

This change adds schema migration 0002_email_templates to the clean BillTrack lineage. It is not a migration from the historical EstateManagement database. Development does not alter the daily installation.

The [component map](COMPONENT-MAP.md#email-drafts) lists exact source files. `/api/email-templates/` reads active templates; `/api/email-drafts/generate/` accepts allottee_id, bill_ids and template_id and returns a temporary merged email with no-store caching. Only approved authenticated users have access. There is no API for saving allottee emails or sending mail.
