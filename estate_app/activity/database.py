"""SQLite audit installation. Field lists are frozen for migration compatibility."""
import json
from django.db.backends.signals import connection_created
from django.dispatch import receiver
from .context import current_operation

# Explicit allowlists: new model fields are never silently added to audit storage.
FIELDS = {
    'estate_app.tenant': 'id uuid name allotment_description type contact contact_not_provided email email_not_provided gstin gstin_not_provided address address_not_provided active due_days gst_applicable custom_gst_rate penalty_type custom_penalty_rate custom_penalty_lumpsum custom_penalty_frequency created_at updated_at',
    'estate_app.bill': 'id invoice_no tenant_id month year rent electric electric_reading water gst_treatment gst_on_rent cgst_on_rent sgst_on_rent igst_on_rent due_date issue_date dispatch_ref_no status penalty_accrued penalty_accrued_on notes created_by_id created_at updated_at',
    'estate_app.payment': 'id uuid bill_id amount payment_date penalty_paid receipt_no notes recorded_by_id created_at',
    'estate_app.systemsettings': 'id penalty_type penalty_rate_pa penalty_lumpsum penalty_frequency gst_applicable gst_rate cgst_rate sgst_rate letterhead_logo letterhead_name letterhead_department letterhead_address signing_authority billed_from supplier_gstin place_of_supply invoice_note copy_to reference_number_format bank_details invoice_remarks email_draft_cc updated_at updated_by_id',
    'estate_app.remindersettings': 'id automatic_enabled',
    'estate_app.reminderdelivery': 'id allottee_id allottee_uuid allottee_name send_date recipient items status attempts error reviewed_by created_at updated_at',
    'estate_app.remindersubmission': 'id delivery_id message allottee_uuid allottee_name send_date recipient items status attempts error reviewed_by created_at updated_at',
    'estate_app.emailtemplate': 'id name subject body active',
    'estate_app.userprofile': 'id user_id role',
    'estate_app.accountaccess': 'id user_id status verified_email verified_at signup_email signup_created decided_by_id decided_at',
    'auth.user': 'id username first_name last_name email is_staff is_superuser is_active date_joined',
    'auth.group': 'id name',
    'auth.user_groups': 'id user_id group_id',
    'auth.user_user_permissions': 'id user_id permission_id',
    'auth.group_permissions': 'id group_id permission_id',
}
ITEM_FIELDS = {'key', 'bill_id', 'reference', 'period', 'receipt_date', 'due_date', 'offset', 'scheduled_date', 'principal', 'penalty', 'total'}


def snapshot(label, raw):
    value = json.loads(raw)
    if 'items' in value:
        items = json.loads(value['items']) if isinstance(value['items'], str) else value['items']
        value['items'] = [{key: item[key] for key in ITEM_FIELDS & item.keys()}
                          for item in items if isinstance(item, dict)] if isinstance(items, list) else []
    if 'message' in value:
        message = json.loads(value['message']) if isinstance(value['message'], str) else value['message']
        value['message'] = {key: message[key] for key in {'to', 'cc', 'subject', 'body'} & message.keys()} if isinstance(message, dict) else {}
    return json.dumps(value, ensure_ascii=False)


@receiver(connection_created)
def configure_connection(sender, connection, **kwargs):
    if connection.vendor != 'sqlite':
        return
    def context_value(key):
        context = current_operation.get()
        # Unmanaged maintenance writes remain visible rather than silently escaping history.
        return context.get(key) if context else {
            'source': 'unmanaged', 'reason': 'Unmanaged database operation; inspect maintenance/job records',
            'actor_id': None, 'actor_name': '', 'operation_id': '',
        }.get(key)
    connection.connection.create_function('bt_context', 1, context_value)
    connection.connection.create_function('bt_snapshot', 2, snapshot)


def install(apps, schema_editor):
    connection = schema_editor.connection
    if connection.vendor != 'sqlite':
        raise RuntimeError('BillTrack activity history currently requires SQLite.')
    tables = set(connection.introspection.table_names())
    for label, fields in FIELDS.items():
        table = label.replace('.', '_')
        if table not in tables:
            continue
        def values(prefix):
            pairs = ','.join(f"'{field}',{prefix}.\"{field}\"" for field in fields.split())
            return f"bt_snapshot('{label}',json_object({pairs}))"
        for event, action in [('INSERT', 'create'), ('UPDATE', 'update'), ('DELETE', 'delete')]:
            ref = 'OLD' if event == 'DELETE' else 'NEW'
            before = 'NULL' if event == 'INSERT' else values('OLD')
            after = 'NULL' if event == 'DELETE' else values('NEW')
            condition = f'WHEN {before} IS NOT {after}' if event == 'UPDATE' else ''
            identity = (f"{ref}.uuid" if 'uuid' in fields.split() else
                        "lower(hex(randomblob(16)))" if event == 'INSERT' else
                        f"COALESCE((SELECT record_identity FROM estate_app_activityentry WHERE record_type='{label}' AND record_id=CAST({ref}.id AS TEXT) ORDER BY id DESC LIMIT 1),'legacy:{label}:' || {ref}.id)")
            schema_editor.execute(f'''CREATE TRIGGER bt_audit_{table}_{action} AFTER {event} ON "{table}" {condition}
                BEGIN INSERT INTO estate_app_activityentry
                (timestamp,actor_id,actor_name,source,operation_id,action,reason,record_type,record_id,record_identity,before,after)
                VALUES (strftime('%Y-%m-%d %H:%M:%f','now'),bt_context('actor_id'),bt_context('actor_name'),
                bt_context('source'),bt_context('operation_id'),'{action}',bt_context('reason'),'{label}',CAST({ref}.id AS TEXT),{identity},{before},{after}); END''')
    for event in ('UPDATE', 'DELETE'):
        schema_editor.execute(f'''CREATE TRIGGER bt_activity_no_{event.lower()} BEFORE {event} ON estate_app_activityentry
            BEGIN SELECT RAISE(ABORT, 'Activity history is read-only'); END''')
    schema_editor.execute('''CREATE TRIGGER bt_original_submission AFTER INSERT ON estate_app_reminderdelivery
        BEGIN INSERT INTO estate_app_remindersubmission
        (delivery_id,message,allottee_uuid,allottee_name,send_date,recipient,items,status,attempts,error,reviewed_by,created_at,updated_at)
        VALUES (NEW.id,'{}',NEW.allottee_uuid,NEW.allottee_name,NEW.send_date,NEW.recipient,NEW.items,NEW.status,NEW.attempts,NEW.error,NEW.reviewed_by,NEW.created_at,NEW.updated_at)
        ON CONFLICT(allottee_uuid,send_date) DO NOTHING; END''')
    schema_editor.execute('''CREATE TRIGGER bt_submission_no_delete BEFORE DELETE ON estate_app_remindersubmission
        BEGIN SELECT RAISE(ABORT, 'Original reminder submissions cannot be deleted'); END''')


def uninstall(apps, schema_editor):
    schema_editor.execute('DROP TRIGGER IF EXISTS bt_original_submission')
    schema_editor.execute('DROP TRIGGER IF EXISTS bt_submission_no_delete')
    for label in FIELDS:
        for action in ('create', 'update', 'delete'):
            schema_editor.execute(f'DROP TRIGGER IF EXISTS bt_audit_{label.replace(".", "_")}_{action}')
    for event in ('update', 'delete'):
        schema_editor.execute(f'DROP TRIGGER IF EXISTS bt_activity_no_{event}')
