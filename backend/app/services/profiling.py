import csv
from collections import Counter
from pathlib import Path

from app.models.schemas import FieldProfile


MAX_PROFILE_ROWS = 500
MAX_SAMPLE_VALUES = 5


def infer_type(values: list[str]) -> str:
    non_empty = [value.strip() for value in values if value.strip()]
    if not non_empty:
        return "empty"

    numeric_count = 0
    for value in non_empty:
        try:
            float(value)
            numeric_count += 1
        except ValueError:
            continue

    if numeric_count == len(non_empty):
        return "number"
    return "text"


def profile_csv(file_path: Path) -> tuple[int, list[FieldProfile]]:
    with file_path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        if not reader.fieldnames:
            return 0, []

        field_values: dict[str, list[str]] = {field: [] for field in reader.fieldnames}
        row_count = 0
        for row in reader:
            row_count += 1
            if row_count <= MAX_PROFILE_ROWS:
                for field in reader.fieldnames:
                    field_values[field].append(str(row.get(field) or ""))

    profiles: list[FieldProfile] = []
    for field, values in field_values.items():
        normalized = [value.strip() for value in values]
        non_empty = [value for value in normalized if value]
        counts = Counter(non_empty)
        duplicate_count = sum(count - 1 for count in counts.values() if count > 1)
        samples = list(dict.fromkeys(non_empty[:MAX_SAMPLE_VALUES]))
        profiles.append(
            FieldProfile(
                name=field,
                inferred_type=infer_type(values),
                empty_count=len(values) - len(non_empty),
                non_empty_count=len(non_empty),
                duplicate_count=duplicate_count,
                samples=samples,
            )
        )

    return row_count, profiles
