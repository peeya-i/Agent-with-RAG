"""Tool to query person registry flat-file CSV."""
import csv
from pathlib import Path
from typing import Dict, Any, List, Optional

REGISTRY_PATH = Path(__file__).resolve().parent.parent / "data" / "registry.csv"

def query_person_registry(keyword: str, field: Optional[str] = None) -> Dict[str, Any]:
    """Search person information in the CSV registry.
    
    Args:
        keyword: Search term (e.g. 'Lucas Dubois', 'Paris', 'Security Engineer')
        field: Optional specific field ('name', 'city', 'country', 'job_title').
               If None or 'all', searches across all fields.
               
    Returns:
        Dictionary with count, results list, and status.
    """
    if not REGISTRY_PATH.exists():
        return {"error": f"Registry file not found at {REGISTRY_PATH}", "status": "error"}
    
    clean_keyword = str(keyword).strip().lower()
    clean_field = str(field).strip().lower() if field else "all"
    valid_fields = ["name", "city", "country", "job_title"]
    
    matches: List[Dict[str, str]] = []
    try:
        with open(REGISTRY_PATH, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if clean_field in valid_fields:
                    val = row.get(clean_field, "").lower()
                    if clean_keyword in val:
                        matches.append(row)
                else:
                    # Search all columns
                    if any(clean_keyword in val.lower() for val in row.values()):
                        matches.append(row)
                        
        return {
            "query": keyword,
            "field": clean_field,
            "total_matches": len(matches),
            "results": matches,
            "status": "success"
        }
    except Exception as e:
        return {"error": str(e), "status": "error"}

# Direct alias
search_person = query_person_registry
