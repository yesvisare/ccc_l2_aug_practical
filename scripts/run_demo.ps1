# Windows PowerShell script to run a quick PII redaction demo
# Demonstrates the simple API without starting the full service

$env:PYTHONPATH = "$PWD;$PWD\src"
Write-Host "PII Detection & Redaction Demo"
Write-Host "==============================="
Write-Host ""

python -c @"
from m6_pii_detection_redaction.core import redact_text

test_text = 'Email alice@example.com and phone +91-98765-43210'

print('Testing PII redaction...')
print(f'Original: {test_text}')

result = redact_text(test_text, mode='replace')

if 'warning' in result or 'error' in result:
    print('\nNote: Running in demo mode (Presidio not available)')
    print('Install dependencies for full functionality:')
    print('  pip install -r requirements.txt')
    print('  python -m spacy download en_core_web_lg')
else:
    print(f'\nRedacted: {result[\"redacted_text\"]}')
    print(f'Entities found: {len(result[\"entities_found\"])}')

print('\nDemo complete!')
"@
