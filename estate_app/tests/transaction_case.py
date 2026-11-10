from django.db import connection
from django.test import TransactionTestCase
from estate_app.activity.database import install, uninstall


class ActivityTransactionTestCase(TransactionTestCase):
    def _fixture_teardown(self):
        # Only disposable test databases may remove audit guards for Django flush.
        with connection.schema_editor() as editor:
            uninstall(None, editor)
        try:
            super()._fixture_teardown()
        finally:
            with connection.schema_editor() as editor:
                install(None, editor)
