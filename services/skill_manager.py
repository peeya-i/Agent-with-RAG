"""Skill manager scanning, parsing SKILL.md files, and dynamically executing procedural tools."""
import importlib.util
import os
import re
import sys
import time
from pathlib import Path
from typing import Dict, Any, List, Optional
import config
from services.vector_store import get_vector_store
from services.log_service import get_log_service

class SkillManager:
    def __init__(self, skills_dir: Optional[Path] = None):
        self.skills_dir = skills_dir or config.SKILLS_DIR
        self.vector_store = get_vector_store()
        self.logger = get_log_service()

    def parse_skill_md(self, skill_md_path: Path) -> Dict[str, Any]:
        """Parse YAML frontmatter and content from SKILL.md."""
        content = skill_md_path.read_text(encoding="utf-8")
        
        # Parse frontmatter
        name = skill_md_path.parent.name
        description = ""
        triggers = []
        
        fm_match = re.search(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
        if fm_match:
            fm_text = fm_match.group(1)
            name_m = re.search(r"^name:\s*(.+)$", fm_text, re.MULTILINE)
            if name_m:
                name = name_m.group(1).strip()
            
            desc_m = re.search(r"^description:\s*(.+?)(?=\n[a-zA-Z0-9_-]+:|\Z)", fm_text, re.DOTALL | re.MULTILINE)
            if desc_m:
                description = " ".join(desc_m.group(1).split()).strip()

            triggers_m = re.search(r"triggers:\s*\n((?:\s*-\s*.+\n?)+)", fm_text)
            if triggers_m:
                for line in triggers_m.group(1).splitlines():
                    clean_line = re.sub(r"^\s*-\s*", "", line).strip()
                    if clean_line:
                        triggers.append(clean_line)

        return {
            "name": name,
            "folder": skill_md_path.parent.name,
            "description": description or f"Procedural skill for {name}",
            "triggers": triggers,
            "full_content": content,
            "file_path": str(skill_md_path),
        }

    def scan_and_sync_skills(self, force_all: bool = False) -> Dict[str, Any]:
        """Scan skills/ folder and load new skills not currently in skill vector database."""
        scanned = 0
        added = 0
        skipped = 0
        loaded_skills: List[str] = []

        if not self.skills_dir.exists():
            return {"scanned": 0, "added": 0, "skipped": 0, "skills": []}

        for item in self.skills_dir.iterdir():
            if not item.is_dir():
                continue
            skill_md = item / "SKILL.md"
            if not skill_md.exists():
                continue

            scanned += 1
            skill_info = self.parse_skill_md(skill_md)
            skill_name = skill_info["name"]

            # Check if skill exists
            if not force_all and self.vector_store.skill_exists(skill_name):
                skipped += 1
                loaded_skills.append(skill_name)
                continue

            # Add to vector store
            try:
                self.vector_store.add_skill(
                    skill_name=skill_name,
                    description=skill_info["description"],
                    full_content=skill_info["full_content"],
                    metadata={
                        "folder": skill_info["folder"],
                        "triggers": ", ".join(skill_info["triggers"]),
                        "file_path": skill_info["file_path"],
                    }
                )
                added += 1
                loaded_skills.append(skill_name)
            except Exception as e:
                print(f"[SkillManager] Failed to embed skill {skill_name}: {e}")

        return {
            "scanned": scanned,
            "added": added,
            "skipped": skipped,
            "skills": loaded_skills,
        }

    def list_available_skills(self) -> List[Dict[str, Any]]:
        """Return list of all skills found in the skills directory."""
        skills = []
        if not self.skills_dir.exists():
            return []

        for item in sorted(self.skills_dir.iterdir()):
            if not item.is_dir():
                continue
            skill_md = item / "SKILL.md"
            if skill_md.exists():
                info = self.parse_skill_md(skill_md)
                skills.append({
                    "name": info["name"],
                    "folder": info["folder"],
                    "description": info["description"],
                    "triggers": info["triggers"],
                })
        return skills

    def execute_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        conversation_id: str = "system",
        invoker: str = "Custom Agent",
    ) -> Dict[str, Any]:
        """Dynamically find, import, and execute procedural tool function with full logging."""
        start_time = time.time()
        
        # Log tool invocation request
        self.logger.log_event(
            conversation_id=conversation_id,
            event_type="tool",
            invoker=invoker,
            target=f"Tool: {tool_name}",
            short_description=f"Tool invocation: {tool_name}",
            payload={"tool": tool_name, "arguments": arguments},
        )

        try:
            # Parse module and function names
            # Handles 'person_search.query_person_registry' or 'env_tools.get_city_weather_and_time'
            parts = tool_name.split(".")
            if len(parts) >= 2:
                module_str = parts[-2]
                func_str = parts[-1]
            else:
                module_str = parts[0]
                func_str = parts[0]

            # Search for script in all skill folders under scripts/
            target_py_path: Optional[Path] = None
            for skill_folder in self.skills_dir.iterdir():
                if not skill_folder.is_dir():
                    continue
                cand = skill_folder / "scripts" / f"{module_str}.py"
                if cand.exists():
                    target_py_path = cand
                    break

            if not target_py_path:
                raise ImportError(f"Could not locate module '{module_str}.py' in skills directory.")

            # Dynamically import module
            spec = importlib.util.spec_from_file_location(f"dynamic_{module_str}", str(target_py_path))
            if not spec or not spec.loader:
                raise ImportError(f"Unable to load spec for {target_py_path}")
            
            mod = importlib.util.module_from_spec(spec)
            sys.modules[f"dynamic_{module_str}"] = mod
            spec.loader.exec_module(mod)

            # Locate function
            func = getattr(mod, func_str, None)
            if not func or not callable(func):
                # Try fallback names or default function in module
                for cand_name in [func_str, "run", "execute", "query"]:
                    cand_func = getattr(mod, cand_name, None)
                    if cand_func and callable(cand_func):
                        func = cand_func
                        break

            if not func:
                raise AttributeError(f"Function '{func_str}' not found in {target_py_path}")

            # Call function
            result = func(**arguments)
            elapsed_ms = (time.time() - start_time) * 1000

            # Log tool response with full unredacted payload
            self.logger.log_event(
                conversation_id=conversation_id,
                event_type="tool",
                invoker=f"Tool: {tool_name}",
                target=invoker,
                short_description=f"Tool {tool_name} returned result",
                payload={"result": result, "status": "success"},
                elapsed_ms=elapsed_ms,
            )

            return {
                "tool": tool_name,
                "result": result,
                "elapsed_ms": elapsed_ms,
                "status": "success",
            }

        except Exception as e:
            elapsed_ms = (time.time() - start_time) * 1000
            err_payload = {"error": str(e), "tool": tool_name, "arguments": arguments}
            self.logger.log_event(
                conversation_id=conversation_id,
                event_type="tool",
                invoker=f"Tool: {tool_name}",
                target=invoker,
                short_description=f"Tool execution failed: {str(e)}",
                payload=err_payload,
                elapsed_ms=elapsed_ms,
                is_error=True,
            )
            return {
                "tool": tool_name,
                "error": str(e),
                "elapsed_ms": elapsed_ms,
                "status": "error",
            }

    def get_tool_function(self, tool_name: str) -> Callable:
        """Resolve and return callable Python function for a tool name."""
        parts = tool_name.split(".")
        if len(parts) >= 2:
            module_str = parts[-2]
            func_str = parts[-1]
        else:
            module_str = parts[0]
            func_str = parts[0]

        target_py_path: Optional[Path] = None
        for skill_folder in self.skills_dir.iterdir():
            if not skill_folder.is_dir():
                continue
            cand = skill_folder / "scripts" / f"{module_str}.py"
            if cand.exists():
                target_py_path = cand
                break

        if not target_py_path:
            raise ImportError(f"Could not locate module '{module_str}.py' in skills directory.")

        spec = importlib.util.spec_from_file_location(f"dynamic_{module_str}", str(target_py_path))
        if not spec or not spec.loader:
            raise ImportError(f"Unable to load spec for {target_py_path}")

        mod = importlib.util.module_from_spec(spec)
        sys.modules[f"dynamic_{module_str}"] = mod
        spec.loader.exec_module(mod)

        func = getattr(mod, func_str, None)
        if not func or not callable(func):
            for cand_name in [func_str, "run", "execute", "query"]:
                cand_func = getattr(mod, cand_name, None)
                if cand_func and callable(cand_func):
                    func = cand_func
                    break

        if not func:
            raise AttributeError(f"Function '{func_str}' not found in {target_py_path}")

        return func

# Singleton instance
_SKILL_MANAGER: Optional[SkillManager] = None

def get_skill_manager() -> SkillManager:
    global _SKILL_MANAGER
    if _SKILL_MANAGER is None:
        _SKILL_MANAGER = SkillManager()
    return _SKILL_MANAGER

def get_tool_function(tool_name: str):
    return get_skill_manager().get_tool_function(tool_name)
