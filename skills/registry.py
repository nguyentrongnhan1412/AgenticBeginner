from skills.excel_to_csv import excel_to_csv
from skills.csv_profile import csv_profile

SKILLS = {
    "excel_to_csv": excel_to_csv,
    "csv_profile": csv_profile,
}


def list_skill_names() -> list[str]:
    return sorted(SKILLS.keys())


def load_skill(name: str):
    if name not in SKILLS:
        raise ValueError(f"Skill not found: {name}")
    return SKILLS[name]