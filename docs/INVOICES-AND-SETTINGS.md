# Invoices and private settings

Use Admin → System Settings for organisation identity, logo, signing authority, GST registration, bank/payee details, reference format and printed wording. These values live only in the local database/private media. See [storage](PRIVATE-CONFIGURATION.md).

Print selections group by allottee and allotment term. A single month uses the individual format, while multiple months in one group use the consolidated layout. Unassigned bills have their own group. Case-specific wording comes from the bill's **Notes** field. The organisation name must be configured before printing. Optional address and payment fields can be blank. A generic image is used if no logo is available.

GST/penalty settings affect calculations; invoice text changes wording only. Reprints use current settings, not an immutable historical brand snapshot. Bank numbers remain text so leading zeroes survive. Changing profile details does not update source files or require a restart.
