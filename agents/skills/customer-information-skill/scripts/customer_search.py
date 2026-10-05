"""Tool to query customer database flat-file CSV."""
import os
import csv
from pathlib import Path
from typing import Dict, Any, List, Optional, Union, Iterable

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CUSTOMER_CSV_PATH = DATA_DIR / "customer_database.csv"
if not CUSTOMER_CSV_PATH.exists():
    CUSTOMER_CSV_PATH = Path(__file__).resolve().parents[4] / "tools" / "data" / "customer_database.csv"

VALID_FIELDS = ["name", "address", "city", "country", "products_purchased"]

def normalize_search_terms(keywords: Optional[Union[str, List[str], Iterable[str]]]) -> List[str]:
    if keywords is None:
        return []
    if isinstance(keywords, str):
        term = keywords.strip().lower()
        return [term] if term else []

    terms = []
    for item in keywords:
        if item is not None:
            clean = str(item).strip().lower()
            if clean and clean not in terms:
                terms.append(clean)
    return terms

def record_matches_term(row: Dict[str, str], term: str, field: str = "") -> bool:
    if not term:
        return True
    clean_field = (field or "").strip().lower()
    if clean_field in VALID_FIELDS:
        val = (row.get(clean_field) or "").lower()
        return term in val
    return any(term in (v or "").lower() for v in row.values())

def filter_customer_records(
    records: Iterable[Dict[str, str]],
    search_terms: List[str],
    field: str = ""
) -> List[Dict[str, str]]:
    record_list = list(records)
    if not search_terms:
        return record_list

    matched_records: List[Dict[str, str]] = []
    seen = set()

    for term in search_terms:
        for row in record_list:
            ident = (row.get("name", "").strip().lower(), row.get("address", "").strip().lower())
            if ident not in seen and record_matches_term(row, term, field):
                seen.add(ident)
                matched_records.append(row)

    return matched_records

def query_customer_registry(
    keywords: Optional[Union[str, List[str]]] = None,
    field: str = "",
    csv_path: Optional[str] = None
) -> Dict[str, Any]:
    path = Path(csv_path) if csv_path else CUSTOMER_CSV_PATH
    if not path.exists():
        return {
            "query": keywords,
            "field": field or "all",
            "count": 0,
            "total_matches": 0,
            "results": [],
            "status": "error",
            "error": f"Customer database not found at {path}"
        }

    terms = normalize_search_terms(keywords)
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        matches = filter_customer_records(reader, terms, field=field)

    return {
        "query": keywords,
        "field": (field or "all").strip().lower(),
        "count": len(matches),
        "total_matches": len(matches),
        "results": matches,
        "status": "success"
    }

def load_customer_database(csv_path: Optional[Path] = None) -> List[Dict[str, str]]:
    path = csv_path or get_database_path()
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))
