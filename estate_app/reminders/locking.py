"""OS-owned locks release on process exit; never keep a DB transaction open over SMTP."""
from contextlib import contextmanager
import os
from pathlib import Path
from django.conf import settings
from django.core.exceptions import ValidationError


@contextmanager
def submission_lock(submission_id):
    folder = Path(settings.BASE_DIR) / 'instance' / 'reminder-locks'
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / f'{int(submission_id)}.lock').open('a+b') as stream:
        if stream.tell() == 0:
            stream.write(b'\0'); stream.flush()
        stream.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            raise ValidationError('This submission is still active or its lock is unavailable. Wait for the sender to finish before provider review.') from error
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == 'nt':
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
