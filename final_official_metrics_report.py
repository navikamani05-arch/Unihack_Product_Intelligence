import json
from collections import Counter
schema = json.load(open('/tmp/official_schema_final3.json'))
summary = json.load(open('/tmp/official_summary_final3.json'))
agg = summary.get('ground_truth') or {}
columns = schema.get('columns', [])
result = {
    'file_name': schema.get('file_name'),
    'row_count': schema.get('row_count'),
    'column_count': schema.get('column_count'),
    'identifier_column': schema.get('identifier_column'),
    'comparison_status_counts': dict(Counter(c.get('comparison_status') for c in columns)),
    'nonempty_columns': sum(1 for c in columns if c.get('nonempty_count', 0) > 0),
    'empty_columns': sum(1 for c in columns if c.get('nonempty_count', 0) == 0),
    'summary': {k: summary.get(k) for k in ('run_id','status','products_processed','products_with_generated_output','fields_evaluated','ground_truth_accuracy')},
    'aggregate': {k: agg.get(k) for k in ('total_expected_products','products_matched','products_missing_from_output','unexpected_products','expected_nonempty_fields','comparable_fields','exact_matches','normalized_matches','partial_matches','missing_values','incorrect_values','overall_evaluation_rate','overall_match_rate','overall_missing_value_rate','lov_comparison_available','uom_comparison_available','character_limits_available')},
    'field_metrics': [{k:m.get(k) for k in ('field_name','mapped_field','expected_nonempty','exact_matches','normalized_matches','partial_matches','missing','incorrect','exact_match_rate','match_rate','missing_value_rate')} for m in agg.get('field_metrics',[])],
    'mismatch_count': len(agg.get('mismatches', [])),
    'unsupported_nonempty_count': sum(1 for c in columns if c.get('comparison_status') == 'UNSUPPORTED' and c.get('nonempty_count', 0)),
    'unknown_nonempty_count': sum(1 for c in columns if c.get('comparison_status') == 'UNKNOWN' and c.get('nonempty_count', 0)),
}
print(json.dumps(result, indent=2))
