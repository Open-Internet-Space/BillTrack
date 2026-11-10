from contextlib import contextmanager
from contextvars import ContextVar
from uuid import uuid4

current_operation = ContextVar('billtrack_operation', default=None)


@contextmanager
def operation(*, actor=None, source='background', reason):
    reason = str(reason).strip()
    if not reason:
        raise ValueError('A written reason is required.')
    value = {'actor_id': actor.pk if actor and actor.is_authenticated else None,
             'actor_name': actor.get_username() if actor and actor.is_authenticated else '',
             'source': source, 'reason': reason, 'operation_id': uuid4().hex}
    token = current_operation.set(value)
    try:
        yield value
    finally:
        current_operation.reset(token)
