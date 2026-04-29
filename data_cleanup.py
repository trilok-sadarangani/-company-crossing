import json
from pathlib import Path

import pandas as pd
from rapidfuzz import fuzz
from rapidfuzz.process import cdist

MAPPINGS_FILE = Path(__file__).parent / "name_mappings.json"
ENTITY_TYPES = ["clients", "suppliers", "destinations"]


def load_mappings() -> dict:
    """Return {entity_type: {variant: canonical}} from disk, creating defaults if missing."""
    if MAPPINGS_FILE.exists():
        try:
            data = json.loads(MAPPINGS_FILE.read_text())
            for key in ENTITY_TYPES:
                data.setdefault(key, {})
            return data
        except (json.JSONDecodeError, OSError):
            pass
    return {e: {} for e in ENTITY_TYPES}


def save_mappings(mappings: dict) -> None:
    MAPPINGS_FILE.write_text(json.dumps(mappings, indent=2, sort_keys=True))


def apply_mapping(series: pd.Series, mapping: dict) -> pd.Series:
    """Replace variant names with their canonical equivalents in a Series."""
    if not mapping:
        return series
    return series.map(lambda x: mapping.get(x, x) if isinstance(x, str) else x)


def find_similar_names(names: list, threshold: int = 85) -> list[dict]:
    """
    Return list of {name_a, name_b, score} for pairs that are similar but not identical.
    Uses pairwise token-sort-ratio comparison across all unique names.
    """
    unique = sorted({n for n in names if isinstance(n, str) and n.strip()})
    if len(unique) < 2:
        return []

    matrix = cdist(unique, unique, scorer=fuzz.token_sort_ratio)

    pairs = []
    n = len(unique)
    for i in range(n):
        for j in range(i + 1, n):
            score = int(matrix[i][j])
            if score >= threshold:
                pairs.append({"name_a": unique[i], "name_b": unique[j], "score": score})

    return sorted(pairs, key=lambda x: -x["score"])
