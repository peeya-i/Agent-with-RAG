---
name: customer-information-skill
description: Search and lookup customer directory records including customer name, address, city, country, or products purchased from the company customer database CSV file (customer_database.csv). Use this skill whenever the user asks about customers, client purchases, addresses, products bought, or client locations.
triggers:
  - who is customer [name]
  - what did [customer] purchase
  - find customers in [city/country]
  - list products purchased by [customer]
  - lookup customer [name]
---

# Customer Information Skill

## Description
Provides lookup and search capabilities over the customer database `customer_database.csv`. Enables searching records by name, address, city, country, or products purchased with exact or partial matching across a list of search texts (or a single search term). Searches for all queried items and returns a combined, deduplicated list of matching entries.

## SOP & Tool Execution
When the user asks about a customer, client, or purchased products:
1. Determine the search `keywords` (a list of texts/strings e.g. names, addresses, cities, countries, or products) and the optional `field` (choices: `name`, `address`, `city`, `country`, `products_purchased`, or `all` to search across all fields).
2. Invoke `customer_search.query_customer_registry`:
```json
{
  "tool": "customer_search.query_customer_registry",
  "arguments": {
    "keywords": ["Liam Gallagher", "Dublin"],
    "field": "all"
  }
}
```
3. Format the returned records clearly showing Name, Address, City, Country, and Products Purchased for all matched entries.
