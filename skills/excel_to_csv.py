"""Excel to CSV skill - Convert an uploaded Excel file to CSV format."""

import logging
import os

logger = logging.getLogger(__name__)
import pandas as pd


def excel_to_csv(input_text: str) -> str:
    """Convert an Excel (.xlsx) file to CSV.

    The skill parses the file path from the last whitespace-separated token in
    *input_text*. For example:
        "convert sales_data.xlsx to csv"    → converts sales_data.xlsx
        "skill:excel_to_csv report.xlsx"    → converts report.xlsx

    Args:
        input_text: Natural-language instruction containing a .xlsx filename.

    Returns:
        A message with the output CSV path, or an error description.
    """
    parts = input_text.strip().split()
    if not parts:
        return "Error: no input provided."

    # Try to find a token ending with .xlsx
    xlsx_path = None
    for token in reversed(parts):
        if token.lower().endswith(".xlsx"):
            xlsx_path = token
            break

    if xlsx_path is None:
        # Fall back to last token
        xlsx_path = parts[-1]

    if not os.path.exists(xlsx_path):
        return f"Error: file not found: '{xlsx_path}'"

    try:
        logger.info("excel_to_csv reading %s", xlsx_path)
        df = pd.read_excel(xlsx_path)
        output_path = os.path.splitext(xlsx_path)[0] + ".csv"
        df.to_csv(output_path, index=False)
        return (
            f"Success: '{xlsx_path}' converted to '{output_path}' "
            f"({len(df)} rows, {len(df.columns)} columns)."
        )
    except Exception as e:
        return f"Error converting '{xlsx_path}': {e}"