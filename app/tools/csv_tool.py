from __future__ import annotations

import pandas as pd


def profile_csv(path: str) -> dict:
    df = pd.read_csv(path)
    return {
        "rows": int(len(df)),
        "columns": [str(c) for c in df.columns],
        "dtypes": {str(k): str(v) for k, v in df.dtypes.items()},
        "missing": {str(k): int(v) for k, v in df.isna().sum().items()},
        "describe": df.describe(include="all").fillna("").to_dict(),
    }
