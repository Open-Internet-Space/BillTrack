# Private organisation configuration

Organisation name, department, address, signing authority, supplier GSTIN, place of supply, bank/payee details, reference format, invoice wording and copy recipients are edited in Admin → System Settings. They are saved in the local ignored SQLite database. Uploaded logos are stored in ignored media/invoice-branding. They are not written into tracked code, environment templates or GitHub settings.

The organisation profile starts blank. Configure the organisation name before printing; requests without it show a setup message. Configure tax and payment details for your own operation. Calculation rules and numeric rate defaults are unchanged; saved local rates control billing. Names, addresses and institution marks are never supplied by a real-organisation fallback. Missing logos use a generic BillTrack image.

.env holds runtime keys, SMTP credentials and optional local network addresses. It is not a second source for organisation settings. Keep it private. .env.example contains empty/placeholder installation values only.

Exports and full backups intentionally include private organisation/configuration data and logos. Keep them outside Git, share only with authorised recipients, and test restoration. Ignore rules and release checks reduce accidental uploads; they cannot prevent someone deliberately publishing private files or forcing them into Git.

The database and backups are not encrypted by these changes. Use operating-system access controls and an appropriate private backup destination.
