"""Unit tests for skills and procedural tools."""
import pytest
from services.skill_manager import get_skill_manager, get_tool_function

get_city_weather_and_time = get_tool_function("env_tools.get_city_weather_and_time")
query_person_registry = get_tool_function("person_search.query_person_registry")
get_stock_performers = get_tool_function("stock_search.get_stock_performers")

def test_person_registry_search_by_name():
    """Verify person search finds Lucas Dubois in registry.csv."""
    res = query_person_registry(keyword="Lucas Dubois", field="name")
    assert res["status"] == "success"
    assert res["total_matches"] >= 1
    found = res["results"][0]
    assert "Dubois" in found["name"]
    assert found["city"] == "Paris"
    assert found["country"] == "France"

def test_person_registry_search_by_job():
    """Verify searching for security engineers returns results."""
    res = query_person_registry(keyword="Security", field="job_title")
    assert res["status"] == "success"
    assert res["total_matches"] >= 1

def test_stock_performers_gainers():
    """Verify top stock gainers query."""
    res = get_stock_performers(action="gainers", limit=3)
    assert res["status"] == "success"
    assert len(res["results"]) <= 3
    # Check descending sort order
    changes = [item["change_pct"] for item in res["results"]]
    assert changes == sorted(changes, reverse=True)

def test_stock_performers_losers():
    """Verify top stock losers query."""
    res = get_stock_performers(action="losers", limit=3)
    assert res["status"] == "success"
    assert len(res["results"]) <= 3
    # Check ascending sort order
    changes = [item["change_pct"] for item in res["results"]]
    assert changes == sorted(changes)

def test_weather_skill_structure():
    """Verify Open-Meteo tool response format for a known city."""
    res = get_city_weather_and_time("Paris")
    assert res["status"] in ["success", "error", "not_found"]
    if res["status"] == "success":
        assert "temperature_c" in res
        assert "condition" in res
        assert "local_time" in res

def test_skill_manager_execution():
    """Verify dynamic tool dispatcher runs tools cleanly."""
    manager = get_skill_manager()
    res = manager.execute_tool(
        tool_name="person_search.query_person_registry",
        arguments={"keyword": "Dubois", "field": "name"},
    )
    assert res["status"] == "success"
    assert "result" in res
