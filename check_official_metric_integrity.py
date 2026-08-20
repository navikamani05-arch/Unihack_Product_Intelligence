import json
schema=json.load(open('/tmp/official_schema_final2.json'))
summary=json.load(open('/tmp/official_summary_final2.json'))
for name in ('Part_Manuf','MFR URL','Product Name','Mfg_Part_Num','Part_Desc'):
    print('PROFILE', name, [c for c in schema['columns'] if c['name']==name])
agg=summary.get('ground_truth') or {}
print('AGG_COUNTS', {k: agg.get(k) for k in ('comparable_fields','expected_nonempty_fields','exact_matches','normalized_matches','partial_matches','missing_values','incorrect_values','overall_match_rate')})
print('AGG_FIELD_NAMES', [m['field_name'] for m in agg.get('field_metrics',[])])
