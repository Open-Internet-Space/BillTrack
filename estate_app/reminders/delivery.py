"""Preserve partial-recipient SMTP outcomes instead of treating them as full acceptance."""
import smtplib
from django.conf import settings
from django.core.mail.backends.smtp import EmailBackend
from django.core.mail.message import sanitize_address


class PartialRecipientAcceptance(smtplib.SMTPException):
    pass


def send_message(message, connection):
    if not isinstance(connection, EmailBackend):
        return message.send()
    encoding = message.encoding or settings.DEFAULT_CHARSET
    sender = sanitize_address(message.from_email, encoding)
    recipients = [sanitize_address(address, encoding) for address in message.recipients()]
    # Django's SMTP backend discards sendmail's partial-refusal dictionary.
    refused = connection.connection.sendmail(sender, recipients, message.message().as_bytes(linesep="\r\n"))
    if refused:
        raise PartialRecipientAcceptance('Some recipients were refused after others may have been accepted.')
    return 1
