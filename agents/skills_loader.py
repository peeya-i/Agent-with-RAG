import os
import re
import requests

def parse_skill_md(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    name = os.path.basename(os.path.dirname(file_path))
    description = ""
    vector_text = ""

    # Parse YAML frontmatter
    fm_match = re.search(r"^---\s*\n(.*?)\n---\s*\n(.*)$", content, re.DOTALL)
    if fm_match:
        frontmatter = fm_match.group(1)
        body = fm_match.group(2)
        
        name_m = re.search(r"^name:\s*(.+)$", frontmatter, re.MULTILINE)
        if name_m:
            name = name_m.group(1).strip()
            
        desc_m = re.search(r"^description:\s*(.+)$", frontmatter, re.MULTILINE)
        if desc_m:
            description = desc_m.group(1).strip()

        vector_text = f"{name}: {description}"
    else:
        vector_text = content[:500]

    return {
        "name": name,
        "description": description or name,
        "vector_text": vector_text,
        "complete_text": content
    }

def scan_and_load_skills(skills_dir, doc_rag_url="http://doc_rag:8003", jwt_token=None):
    if not os.path.exists(skills_dir):
        return []

    if not os.environ.get("RUNNING_IN_DOCKER") and "doc_rag:8003" in doc_rag_url:
        doc_rag_url = doc_rag_url.replace("doc_rag:8003", "127.0.0.1:8003")

    loaded = []
    headers = {"Content-Type": "application/json"}
    if jwt_token:
        headers["Authorization"] = f"Bearer {jwt_token}"

    for entry in os.scandir(skills_dir):
        if entry.is_dir():
            skill_md = os.path.join(entry.path, "SKILL.md")
            if os.path.exists(skill_md):
                try:
                    data = parse_skill_md(skill_md)
                    if jwt_token:
                        data["jwt_token"] = jwt_token
                    # Upload to doc_RAG
                    resp = requests.post(f"{doc_rag_url}/api/rag/skills/add", json=data, headers=headers, timeout=5)
                    if resp.status_code == 200:
                        loaded.append(data["name"])
                except Exception as e:
                    print(f"Error loading skill {entry.name}: {e}")
    return loaded
