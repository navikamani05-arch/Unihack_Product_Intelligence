import json
from collections import Counter

schema = json.load(open('/tmp/official_eval_schema_final.json', encoding='utf-8'))
summary = json.load(open('/tmp/official_eval_summary_final.json', encoding='utf-8'))
run = json.load(open('/tmp/official_eval_run_final.json', encoding='utf-8'))

print('FILE', schema.get('file_name'))
print('ROWS', schema.get('row_count'))
print('COLUMNS', schema.get('column_count'))
print('IDENTIFIER', schema.get('identifier_column'))
counts = Counter(item.get('comparison_status') for item in schema.get('columns', []))
print('STATUS_COUNTS', dict(counts))
for status in ('SUPPORTED', 'PARTIALLY_SUPPORTED', 'UNSUPPORTED', 'UNKNOWN'):
    names = [item['name'] for item in schema.get('columns', []) if item.get('comparison_status') == status]
    print(status, len(names), names)
agg = summary.get('ground_truth') or {}
print('SUMMARY_STATUS', summary.get('status'))
print('PRODUCTS_PROCESSED', summary.get('products_processed'))
print('PRODUCTS_WITH_GENERATED_OUTPUT', summary.get('products_with_generated_output'))
for key in ('total_expected_products','products_matched','products_missing_from_output','unexpected_products','expected_nonempty_fields','comparable_fields','exact_matches','normalized_matches','partial_matches','missing_values','incorrect_values','overall_evaluation_rate','overall_match_rate','overall_missing_value_rate','lov_comparison_available','uom_comparison_available','character_limits_available'):
    print(key.upper(), agg.get(key))
print('GROUND_TRUTH_ACCURACY', summary.get('ground_truth_accuracy'))
print('FIELD_METRICS')
for item in agg.get('field_metrics', []):
    print(item['field_name'], item.get('mapped_field'), item.get('expected_nonempty'), item.get('exact_matches'), item.get('normalized_matches'), item.get('partial_matches'), item.get('missing'), item.get('incorrect'), item.get('exact_match_rate'), item.get('match_rate'), item.get('missing_value_rate'))
print('MISMATCH_COUNT', len(agg.get('mismatches', [])))
for item in agg.get('mismatches', [])[:30]:
    print('MISMATCH', item)
print('RUN_ID', run.get('run_id'))
