# Windows PowerShell script to emit a demo audit event
# Demonstrates creating and storing an audit event without Elasticsearch

$env:PYTHONPATH = "$PWD"
Write-Host "Emitting demo audit event..."

python -c @"
import sys
sys.path.insert(0, '.')
from m6_4_compliance_audit.core import AuditEvent, AuditOutcome, AuditEventType, AuditStorage

# Create storage (no ES client - uses fallback)
st = AuditStorage(es_client=None)

# Create demo event
ev = AuditEvent(
    event_type=AuditEventType.DOCUMENT_ACCESS,
    user_id='demo',
    user_role='analyst',
    resource_type='document',
    resource_id='doc_1',
    action='read',
    outcome=AuditOutcome.SUCCESS
)

# Store event
st.store_event(ev)
print('✓ Demo audit event emitted to fallback storage')
print(f'  Event ID: {ev.event_id}')
print(f'  Type: {ev.event_type.value}')
"@
