from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

path = Path('/home/ubuntu/upload/Unihack_ExpectedOutput-DeliveryFormat.csv')
df = pd.read_csv(path, dtype=object, keep_default_na=False)

profile = {
    'path': str(path),
    'file_size_bytes': path.stat().st_size,
    'row_count': int(len(df)),
    'column_count': int(len(df.columns)),
    'columns': [],
    'sample_records': df.head(5).to_dict(orient='records'),
}
for col in df.columns:
    series = df[col]
    nonempty = series[series.astype(str).str.strip() != '']
    profile['columns'].append({
        'name': str(col),
        'pandas_dtype': str(series.dtype),
        'nonempty_count': int(len(nonempty)),
        'empty_count': int(len(series) - len(nonempty)),
        'unique_count': int(series.nunique(dropna=False)),
        'sample_values': [str(x) for x in series.drop_duplicates().head(10).tolist()],
        'max_string_length': int(series.astype(str).map(len).max()) if len(series) else 0,
    })

print(json.dumps(profile, indent=2, ensure_ascii=False))
