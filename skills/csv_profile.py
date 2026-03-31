"""CSV profile skill - quick summary of a local CSV file."""

import os

import pandas as pd


def csv_profile(input_text: str) -> str:
    """Summarize a CSV file (shape, columns, missing values, preview).

    The skill tries to extract a `.csv` path from the input text (best-effort).

    Args:
        input_text: Natural-language instruction containing a .csv filename.

    Returns:
        A human-readable summary, or an error message.
    """
    parts = input_text.strip().split()
    if not parts:
        return "Error: no input provided."

    csv_path = None
    for token in reversed(parts):
        if token.lower().endswith(".csv"):
            csv_path = token.strip("\"'")
            break
    if csv_path is None:
        csv_path = parts[-1].strip("\"'")

    if not os.path.exists(csv_path):
        return f"Error: file not found: '{csv_path}'"
    if not csv_path.lower().endswith(".csv"):
        return "Error: please provide a .csv file path."

    try:
        df = pd.read_csv(csv_path)
    except UnicodeDecodeError:
        try:
            df = pd.read_csv(csv_path, encoding="utf-8-sig")
        except Exception as e:
            return f"Error reading '{csv_path}': {e}"
    except Exception as e:
        return f"Error reading '{csv_path}': {e}"

    rows, cols = df.shape
    missing = df.isna().sum().sort_values(ascending=False)
    missing_top = missing[missing > 0].head(10)

    dtype_lines = [f"- {c}: {str(t)}" for c, t in df.dtypes.items()]

    preview = df.head(5).to_string(index=False)

    out = []
    out.append(f"CSV: {csv_path}")
    out.append(f"Shape: {rows} rows × {cols} columns")
    out.append("")
    out.append("Columns (dtype):")
    out.extend(dtype_lines if dtype_lines else ["(none)"])
    out.append("")
    if not missing_top.empty:
        out.append("Top missing-value columns:")
        out.extend([f"- {idx}: {int(val)}" for idx, val in missing_top.items()])
        out.append("")
    out.append("Preview (first 5 rows):")
    out.append(preview if preview.strip() else "(empty)")
    return "\n".join(out)

