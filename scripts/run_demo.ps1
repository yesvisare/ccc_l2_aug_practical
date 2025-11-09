# Windows PowerShell script to run a quick PII redaction demo
# Demonstrates the core functionality without starting the full API

$env:PYTHONPATH = $PWD
Write-Host "PII Detection & Redaction Demo"
Write-Host "==============================="
Write-Host ""

python -c @"
import sys
sys.path.insert(0, '.')

from m6_pii_detection_redaction import PIIDetector, RedactionStrategy, PRESIDIO_AVAILABLE

if not PRESIDIO_AVAILABLE:
    print('ERROR: Presidio not available. Install dependencies:')
    print('  pip install -r requirements.txt')
    print('  python -m spacy download en_core_web_lg')
    sys.exit(1)

print('Initializing PII detector...')
detector = PIIDetector(confidence_threshold=0.5)

test_text = '''
Employee: John Smith
SSN: 123-45-6789
Email: john.smith@company.com
Phone: (555) 123-4567
'''

print('\nOriginal text:')
print(test_text)

print('\n--- Replacement Strategy ---')
result = detector.redact(test_text, strategy=RedactionStrategy.REPLACEMENT)
print(result.redacted_text)
print(f'Entities found: {len(result.entities_found)}, Time: {result.processing_time_ms:.1f}ms')

print('\nDemo complete!')
"@
