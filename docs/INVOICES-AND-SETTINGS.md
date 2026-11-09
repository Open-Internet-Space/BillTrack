# Invoices and private settings

Use Admin → System Settings for organisation identity, logo, signing authority, GST registration, bank/payee details, reference format and printed wording. These values live only in the local database/private media. See [storage](PRIVATE-CONFIGURATION.md).

Single-month selections use the individual format; multiple months for one allottee use a consolidated layout; mixed selections group per allottee. Configured text is escaped and applied to all print routes, including admin bulk printing. The organisation name must be configured first. Optional address/payment fields may be blank; no real institution/address is substituted. A generic application image is used if no logo is available.

GST/penalty settings affect calculations; invoice text changes wording only. Reprints use current settings, not an immutable historical brand snapshot. Bank numbers remain text so leading zeroes survive. Changing profile details does not update source files or require a restart.
