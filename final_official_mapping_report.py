import json
schema=json.load(open('/tmp/official_schema_final3.json'))
for status in ('SUPPORTED','PARTIALLY_SUPPORTED','UNSUPPORTED','UNKNOWN'):
    items=[c for c in schema.get('columns',[]) if c.get('comparison_status')==status]
    print(status, len(items))
    print('  ' + ', '.join(c['name'] for c in items))
print('sample_types')
for c in schema.get('columns',[])[:12]:
    print(c['name'], c['pandas_dtype'], c['nonempty_count'], c['unique_count'], c['sample_values'][:3])
