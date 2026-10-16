import os
import json
import logging
import requests
from typing import List, Dict, Any, Tuple, Optional

logger = logging.getLogger("custom_agent.skill_selector")


def build_skill_selection_prompt(skills_summary: List[Dict[str, str]], message: str) -> str:
    """Creates the structured prompt for LLMs to select relevant skills for a user message."""
    return (
        "You are an expert AI skill selector. Given the user's message and a list of available specialized skills, "
        "determine which skill or skills (if any) are directly relevant to answering the user's query.\n"
        "If no skill is relevant (e.g. general chit-chat), return an empty list.\n\n"
        f"Available Skills:\n{json.dumps(skills_summary, indent=2)}\n\n"
        f"User Message:\n\"{message}\"\n\n"
        "Respond ONLY with a JSON object in this exact format:\n"
        "{\n"
        '  "selected_skills": ["<skill_name_1>", ...],\n'
        '  "reasoning": "<short explanation why these skills were selected>"\n'
        "}"
    )


def select_skills_with_ollama(
    message: str,
    local_model: str,
    available_skills: List[Dict[str, Any]],
    ollama_url: Optional[str] = None,
    timeout: int = 30
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Optional[str]]:
    """Uses a local Ollama LLM to select appropriate skills from available skills."""
    skills_summary = []
    for s in available_skills:
        skills_summary.append({
            "skill_name": s.get("name") or s.get("skill_name"),
            "description": s.get("description", "")
        })

    prompt_for_ollama = build_skill_selection_prompt(skills_summary, message)

    ollama_base = ollama_url or os.environ.get("OLLAMA_URL", "http://ollama:11434")
    if not os.environ.get("RUNNING_IN_DOCKER") and "ollama:11434" in ollama_base:
        ollama_base = ollama_base.replace("ollama:11434", "localhost:11434")

    matched_skills = []
    evidence_skills = []
    error = None

    try:
        resp = requests.post(
            f"{ollama_base}/api/generate",
            json={
                "model": local_model,
                "prompt": prompt_for_ollama,
                "stream": False,
                "format": "json"
            },
            timeout=timeout
        )
        if resp.status_code == 200:
            raw_resp = resp.json().get("response", "").strip()
            if raw_resp.startswith("```json"):
                raw_resp = raw_resp[7:]
            if raw_resp.startswith("```"):
                raw_resp = raw_resp[3:]
            if raw_resp.endswith("```"):
                raw_resp = raw_resp[:-3]
            parsed_res = json.loads(raw_resp.strip())
            selected_names = parsed_res.get("selected_skills", [])
            if isinstance(selected_names, str):
                selected_names = [selected_names]

            for s_name in selected_names:
                matched_obj = next(
                    (s for s in available_skills if s.get("name") == s_name or s.get("skill_name") == s_name),
                    None
                )
                skill_text = (
                    matched_obj.get("complete_text")
                    or matched_obj.get("vector_text")
                    or matched_obj.get("description", "")
                    if matched_obj else ""
                )
                matched_skills.append({
                    "skill_name": s_name,
                    "text": skill_text or f"Selected by Local LLM ({local_model})"
                })
                evidence_skills.append({
                    "name": s_name,
                    "similarity": 1.0,
                    "description": matched_obj.get("description", "") if matched_obj else ""
                })
        else:
            error = f"Ollama HTTP {resp.status_code}: {resp.text}"
    except Exception as e:
        logger.warning(f"Local LLM skill selection failed: {e}")
        error = str(e)

    return matched_skills, evidence_skills, error


def select_skills_with_gemini(
    message: str,
    available_skills: List[Dict[str, Any]],
    model_name: str = "gemini-3.5-flash-lite",
    api_key: Optional[str] = None
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Optional[str]]:
    """Uses Google GenAI / Gemini to select appropriate skills from available skills."""
    skills_summary = []
    for s in available_skills:
        skills_summary.append({
            "skill_name": s.get("name") or s.get("skill_name"),
            "description": s.get("description", "")
        })

    prompt_content = build_skill_selection_prompt(skills_summary, message)
    matched_skills = []
    evidence_skills = []
    error = None

    gemini_key = api_key or os.environ.get("GEMINI_API_KEY", "")
    if not gemini_key:
        return matched_skills, evidence_skills, "No Gemini API key available"

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=gemini_key)
        resp = client.models.generate_content(
            model=model_name,
            contents=prompt_content,
            config=types.GenerateContentConfig(
                temperature=0.1,
                response_mime_type="application/json"
            )
        )
        if resp and resp.text:
            parsed_res = json.loads(resp.text.strip())
            selected_names = parsed_res.get("selected_skills", [])
            if isinstance(selected_names, str):
                selected_names = [selected_names]

            for s_name in selected_names:
                matched_obj = next(
                    (s for s in available_skills if s.get("name") == s_name or s.get("skill_name") == s_name),
                    None
                )
                skill_text = (
                    matched_obj.get("complete_text")
                    or matched_obj.get("vector_text")
                    or matched_obj.get("description", "")
                    if matched_obj else ""
                )
                matched_skills.append({
                    "skill_name": s_name,
                    "text": skill_text or f"Selected by Gemini ({model_name})"
                })
                evidence_skills.append({
                    "name": s_name,
                    "similarity": 1.0,
                    "description": matched_obj.get("description", "") if matched_obj else ""
                })
    except Exception as e:
        logger.warning(f"Gemini skill selection failed: {e}")
        error = str(e)

    return matched_skills, evidence_skills, error
