# Signup, approval and email recovery

Signup asks for name, email, password and confirmation. Verify an email code before appearing for superuser approval. Approval grants Staff billing access, not Django admin access. Rejected, pending or disabled accounts stay blocked. New users sign in with email; existing usernames are supported. Ambiguous email identities fail closed.

Existing accounts verify their saved unique email using their current password and OTP. A superuser corrects missing/shared addresses. Email recovery changes passwords without approving or enabling accounts and revokes tokens/old sessions. Codes expire in ten minutes, are single-use and have persistent per-email/IP/global limits. Resending does not reset guess limits.

SMTP must pass a controlled test, then ACCOUNT_EMAIL_ENABLED must be enabled in private .env. Financial reminder previews are independent; their manual confirmation requirement does not apply to signup or recovery codes. Recovery sends asynchronously using a small bounded in-memory queue; restart/SMTP failure can mean no delivery. Wait a minute and request a new code. No real mail should be sent during tests.
