# Payment reminders

Superusers preview and manually send combined reminders per allottee. Automatic sending starts off and requires tested private SMTP configuration. Receipt-based offsets are due-1, due, due+1, due+7, due+14, due+26, due+41 and every fifteen days afterward, stopping three calendar months from confirmed receipt. Existing calculations/deadlines are unchanged.

No message is sent by previewing. Settled/inactive/missing-email/unconfirmed/expired records are skipped. One accepted message per allottee per day, stable milestone claims and explicit review of uncertain outcomes reduce duplicates. SMTP acceptance is not proof of inbox delivery.

Configure EMAIL_* and DEFAULT_FROM_EMAIL only in .env, restart and test to a designated mailbox. Enabling account email recovery or reminder automation is a separate decision. Optional daily scheduling must use the chosen installation account/task; no task is installed during this preparation. History and financial exports remain private.
