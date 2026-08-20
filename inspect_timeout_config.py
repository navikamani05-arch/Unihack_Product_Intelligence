import os
import os
import sys

keys = [
    'LLM_TIMEOUT_SECONDS',
    'LLM_MAX_RETRIES',
    'LLM_BATCH_SIZE',
    'LLM_MAX_CONCURRENCY',
    'REQUEST_TIMEOUT_SECONDS',
    'VITE_API_TIMEOUT_MS',
    'VITE_DEV_PROXY_TIMEOUT_MS',
]
for key in keys:
    print(f'{key}={os.getenv(key, "<unset>")}')

sys.path.insert(0, 'backend')
from app.config import settings
print('--- backend settings ---')
for key in ['llm_timeout_seconds', 'llm_max_retries', 'request_timeout_seconds']:
    print(f'{key}={getattr(settings, key)}')
print('--- available batch settings ---')
for name in dir(settings):
    if 'batch' in name.lower() or 'concurr' in name.lower():
        print(f'{name}={getattr(settings, name)}')
