---
name: person-information-skill
description: Search and lookup personal directory records including employee name, city, country, or job title from the company registry CSV file. Use this skill whenever the user asks about people, personnel, employees, job titles, or someone's location.
triggers:
  - who is [person]
  - where does [person] live
  - what is [person]'s job title
  - find employees in [city]
  - list staff in [country]
  - who works as [job title]
  - lookup person [name]
---

# Person Information Skill

## Description
Provides lookup and search capabilities over the personnel database `registry.csv`. Enables searching records by name, city, country, or job title with exact or partial matching.

## SOP & Tool Execution
When the user asks about an employee or personnel record:
1. Determine the search `keyword` and the optional `field` (choices: `name`, `city`, `country`, `job_title`, or search all fields if not specified).
2. Invoke `person_search.query_person_registry`:
```json
{
  "tool": "person_search.query_person_registry",
  "arguments": {
    "keyword": "Lucas Dubois",
    "field": "name"
  }
}
```
3. Format the returned records clearly showing Name, Job Title, City, and Country.
