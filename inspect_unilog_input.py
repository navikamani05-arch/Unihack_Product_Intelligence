from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

DATASET = Path("/home/ubuntu/upload/Unihack_SampleDataset-Input.csv")
PLACEHOLDERS = {
    "-- Unbranded --",
    "-- No Unilog Brand --",
    "-- No DIB Brand --",
}


def main() -> None:
    frame = pd.read_csv(DATASET, dtype="string", keep_default_na=False)
    profile = {
        "path": str(DATASET),
        "rows": len(frame),
        "columns": [
            {
                "name": column,
                "dtype": str(frame[column].dtype),
                "blank_count": int(frame[column].astype(str).str.strip().eq("").sum()),
                "placeholder_count": int(frame[column].isin(PLACEHOLDERS).sum()),
                "unique_non_blank": int(
                    frame[column].astype(str).str.strip().replace("", pd.NA).dropna().nunique()
                ),
                "examples": frame[column].astype(str).head(3).tolist(),
            }
            for column in frame.columns
        ],
    }
    print(json.dumps(profile, indent=2))


if __name__ == "__main__":
    main()
