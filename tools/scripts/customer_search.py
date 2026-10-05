import os
import csv
from typing import Dict, Any, List, Optional, Union, Iterable

DATA_DIR = os.environ.get("DATA_DIR", os.path.join(os.path.dirname(os.path.dirname(__file__)), "data"))
CSV_PATH = os.path.join(DATA_DIR, "customer_database.csv")
VALID_FIELDS = ["name", "address", "city", "country", "products_purchased"]

SAMPLE_CUSTOMERS = [
    {"name": "Liam Gallagher", "address": "42 Grafton Street", "city": "Dublin", "country": "Ireland", "products_purchased": "Gaming Laptop, Mechanical Keyboard, Ergonomic Chair, 4K Monitor"},
    {"name": "Amara Okafor", "address": "14 Victoria Island Way", "city": "Lagos", "country": "Nigeria", "products_purchased": "Smartphone, Wireless Earbuds, Phone Case"},
    {"name": "Sofia Hernandez", "address": "78 Avenida Reforma", "city": "Mexico City", "country": "Mexico", "products_purchased": "Smart Watch, Screen Protector, Wireless Charger"},
    {"name": "Takeshi Yamada", "address": "3-12 Ginza Chuo-ku", "city": "Tokyo", "country": "Japan", "products_purchased": "Digital Camera, Prime Lens, Camera Bag, Tripod, Memory Card"},
    {"name": "Emma Watson", "address": "25 Baker Street", "city": "London", "country": "United Kingdom", "products_purchased": "Tablet, Stylus Pen, Bluetooth Speaker"},
    {"name": "Jean Dupont", "address": "18 Rue de la Paix", "city": "Paris", "country": "France", "products_purchased": "Noise-Canceling Headphones, Portable Power Bank, USB-C Cable"},
    {"name": "Mateo Rossi", "address": "12 Via Montenapoleone", "city": "Milan", "country": "Italy", "products_purchased": "Smart Thermostat, Video Doorbell, Smart Light Bulb"},
    {"name": "Hanna Lindqvist", "address": "8 Kungsgatan", "city": "Stockholm", "country": "Sweden", "products_purchased": "Ultralight Laptop, Laptop Sleeve, USB Docking Station, Wireless Mouse"},
    {"name": "Lucas Silva", "address": "105 Avenida Paulista", "city": "Sao Paulo", "country": "Brazil", "products_purchased": "Action Camera, Waterproof Case, Chest Mount, Extra Battery"},
    {"name": "Ananya Sengupta", "address": "54 Park Street", "city": "Kolkata", "country": "India", "products_purchased": "E-Reader, Flip Cover, Reading Light"},
    {"name": "David Mueller", "address": "33 Friedrichstrasse", "city": "Berlin", "country": "Germany", "products_purchased": "Desktop PC, Mechanical Keyboard, Mouse Pad, Soundbar"},
    {"name": "Fatima Al-Zahra", "address": "22 Corniche Road", "city": "Abu Dhabi", "country": "United Arab Emirates", "products_purchased": "VR Headset, Controller Grips, Link Cable"},
    {"name": "Min-Jun Park", "address": "88 Teheran-ro Gangnam-gu", "city": "Seoul", "country": "South Korea", "products_purchased": "Smartwatch, Running Earbuds, Fitness Tracker, Extra Band"},
    {"name": "Camila Torres", "address": "19 Avenida Corrientes", "city": "Buenos Aires", "country": "Argentina", "products_purchased": "Smart Display, Wi-Fi Extender, Smart Plug"},
    {"name": "Oliver Hansen", "address": "17 Stroget", "city": "Copenhagen", "country": "Denmark", "products_purchased": "Wireless Headset, Gaming Mouse, USB Microphone, Pop Filter"},
    {"name": "Zoe Tan", "address": "50 Orchard Road", "city": "Singapore", "country": "Singapore", "products_purchased": "4K Webcam, Ring Light, USB-C Adapter"},
    {"name": "Tariq Mansoor", "address": "9 Tahrir Square", "city": "Cairo", "country": "Egypt", "products_purchased": "Portable SSD 1TB, External HDD 2TB, USB Flash Drive"},
    {"name": "Isabella Campbell", "address": "120 George Street", "city": "Sydney", "country": "Australia", "products_purchased": "Bluetooth Speaker, Waterproof Pouch, Solar Charger, Camping Lantern"},
    {"name": "Noah De Smet", "address": "7 Meir", "city": "Antwerp", "country": "Belgium", "products_purchased": "Smart TV Box, HDMI 2.1 Cable, Universal Remote Control"},
    {"name": "Elena Petrova", "address": "15 Nevsky Prospect", "city": "Saint Petersburg", "country": "Russia", "products_purchased": "Graphics Tablet, Drawing Glove, Replacement Nibs, Drawing Tablet Stand"}
]

def seed_customer_data(csv_path: str = CSV_PATH, overwrite: bool = False) -> int:
    """Seed 20 customer records in customer_database.csv if not exists."""
    os.makedirs(os.path.dirname(csv_path), exist_ok=True)
    if os.path.exists(csv_path) and not overwrite:
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            rows = list(reader)
            if len(rows) >= 21:  # header + 20 records
                return len(rows) - 1

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=VALID_FIELDS)
        writer.writeheader()
        for cust in SAMPLE_CUSTOMERS[:20]:
            writer.writerow(cust)
    return len(SAMPLE_CUSTOMERS[:20])

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

def filter_records(records: Iterable[Dict[str, str]], search_terms: List[str], field: str = "") -> List[Dict[str, str]]:
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

def search_customers(
    keywords: Optional[Union[str, List[str]]] = None,
    field: str = "",
    csv_path: str = CSV_PATH,
    keyword: Optional[Union[str, List[str]]] = None
) -> List[Dict[str, str]]:
    if not os.path.exists(csv_path):
        seed_customer_data(csv_path)

    query_input = keywords if keywords is not None else keyword
    terms = normalize_search_terms(query_input)

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return filter_records(reader, terms, field=field)

def load_customer_database(csv_path: str = CSV_PATH) -> List[Dict[str, str]]:
    if not os.path.exists(csv_path):
        seed_customer_data(csv_path)
    with open(csv_path, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))

def query_customers(
    keywords: Optional[Union[str, List[str]]] = None,
    field: str = "",
    csv_path: str = CSV_PATH,
    keyword: Optional[Union[str, List[str]]] = None
) -> Dict[str, Any]:
    results = search_customers(keywords=keywords, field=field, csv_path=csv_path, keyword=keyword)
    query_input = keywords if keywords is not None else keyword
    return {
        "query": query_input,
        "field": (field or "all").strip().lower(),
        "count": len(results),
        "total_matches": len(results),
        "results": results,
        "status": "success"
    }
