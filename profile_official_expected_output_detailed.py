from __future__ import annotations
import json
from pathlib import Path
import pandas as pd

path = Path('/home/ubuntu/upload/Unihack_ExpectedOutput-DeliveryFormat.csv')
df = pd.read_csv(path, dtype='string', keep_default_na=False)
columns = []
for i, col in enumerate(df.columns):
    s = df[col].fillna('').astype(str)
    vals = [v for v in s.tolist() if v.strip()]
    columns.append({
        'index': i,
        'name': str(col),
        'nonempty_count': len(vals),
        'unique_nonempty_count': len(set(vals)),
        'unique_nonempty_values': list(dict.fromkeys(vals))[:20],
        'max_length': max([len(v) for v in vals], default=0),
    })
report = {
    'file': str(path),
    'rows': int(len(df)),
    'columns': int(len(df.columns)),
    'columns_detail': columns,
    'records': df.to_dict(orient='records'),
}
Path('/tmp/official_expected_output_detailed.json').write_text(json.dumps(report, indent=2, ensure_ascii=False))
print(f"rows={len(df)} columns={len(df.columns)}")
for c in columns:
    print(f"{c['index']:03d}\t{c['name']}\tnonempty={c['nonempty_count']}\tunique={c['unique_nonempty_count']}\tvalues={c['unique_nonempty_values'][:3]}")
