import os
import json
import time
import logging
import requests
from datetime import datetime, timezone
from typing import List, Dict, Any, Tuple, Optional

logger = logging.getLogger("custom_agent.skill_selector")


def send_llm_invocation_log(
    logging_url: Optional[str],
    input_payload: Any,
    output_response: Any,
    conv_id: Optional[str] = None,
    model: Optional[str] = None,
    duration_ms: int = 0,
    desc: str = "LLM skill selection decision",
    status: str = "success"
):
    """Sends an llm_invocation log event with input request payload and output response."""
    try:
        url = logging_url or os.environ.get("LOGGING_SERVICE_URL") or os.environ.get("LOGGING_URL", "http://logging:8006")
        if not os.environ.get("RUNNING_IN_DOCKER") and "logging:8006" in url:
            url = url.replace("logging:8006", "127.0.0.1:8006")
        log_body = {
            "invoker": "agents_router",
            "recipient": "llm_selector",
            "target": "llm_selector",
            "conversation_id": conv_id,
            "type": "llm_invocation",
            "short_description": desc,
            "payload": {
                "input": input_payload,
                "output": output_response
            },
            "status": status,
            "duration_ms": duration_ms,
            "model": model,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        requests.post(f"{url}/api/logs", json=log_body, timeout=2)
    except Exception as e:
        logger.debug(f"Failed to post llm_invocation log in skill selector: {e}")


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
    timeout: int = 30,
    conv_id: Optional[str] = None,
    logging_url: Optional[str] = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Optional[str]]:
    """Uses a local Ollama LLM (Nimble-V3 choice routing or DeepSeek JSON routing) to select appropriate skills."""
    ollama_base = ollama_url or os.environ.get("OLLAMA_URL", "http://ollama:11434")
    if not os.environ.get("RUNNING_IN_DOCKER") and "ollama:11434" in ollama_base:
        ollama_base = ollama_base.replace("ollama:11434", "localhost:11434")

    matched_skills = []
    evidence_skills = []
    error = None

    is_nimble = "nimble" in local_model.lower()

    if is_nimble:
        # Nimble-V3 choice router using /v1/systemone endpoint
        criteria = {}
        for s in available_skills:
            s_name = s.get("name") or s.get("skill_name")
            desc = s.get("description", "").strip()
            criteria[s_name] = f"{s_name}. {desc}".strip() if desc else s_name
        criteria["GENERAL_FALLBACK"] = "General chit-chat or questions not fitting other skills"

        req_payload = {
            "model": "nimble-v3",
            "state": message,
            "questions": {
                "route_intent": {
                    "type": "choice",
                    "instructions": "Which specialized tool or category fits the user's intent?",
                    "criteria": criteria
                }
            }
        }
        try:
            t_start = time.time()
            resp = requests.post(f"{ollama_base}/v1/systemone", json=req_payload, timeout=timeout)
            dur_ms = int((time.time() - t_start) * 1000)
            if resp.status_code == 200:
                data = resp.json()
                if "error" in data:
                    raise RuntimeError(f"Nimble error: {data['error']}")
                chosen = data.get("answers", {}).get("route_intent", {}).get("choice")
                if chosen and chosen != "GENERAL_FALLBACK":
                    matched_obj = next(
                        (s for s in available_skills if s.get("name") == chosen or s.get("skill_name") == chosen),
                        None
                    )
                    criteria_text = criteria.get(chosen) or (f"{chosen}. {matched_obj.get('description', '')}".strip() if matched_obj else chosen)
                    skill_text = (
                        matched_obj.get("complete_text")
                        or matched_obj.get("vector_text")
                        or criteria_text
                        if matched_obj else criteria_text
                    )
                    matched_skills.append({
                        "skill_name": chosen,
                        "text": skill_text or f"Selected by Nimble ({local_model})"
                    })
                    evidence_skills.append({
                        "name": chosen,
                        "similarity": 1.0,
                        "description": criteria_text,
                        "selection_method": f"LLM Selection ({local_model})"
                    })

                # Log LLM invocation event
                send_llm_invocation_log(
                    logging_url=logging_url,
                    input_payload=req_payload,
                    output_response=data,
                    conv_id=conv_id,
                    model=local_model,
                    duration_ms=dur_ms,
                    desc=f"Local Nimble-V3 Skill Selection ({local_model})"
                )
            else:
                error = f"Nimble HTTP {resp.status_code}: {resp.text}"
        except Exception as e:
            logger.warning(f"Local Nimble skill selection failed: {e}")
            error = str(e)

        return matched_skills, evidence_skills, error

    else:
        # DeepSeek and general Ollama models using test_deepseek.py style
        skill_lines = []
        for s in available_skills:
            s_name = s.get("name") or s.get("skill_name")
            desc = s.get("description", "")
            skill_lines.append(f"- {s_name}: {desc}")
        skills_list_str = "\n".join(skill_lines)

        system_instructions = (
            "You are an intelligent routing engine. Classify the user query into the single best tool and provide the reason for selecting:\n"
            f"{skills_list_str}\n"
            "- GENERAL_FALLBACK: General chit-chat or questions not fitting other tools\n\n"
            "Respond ONLY with valid JSON matching this schema:\n"
            '{"selected_tool": "NAME", "confidence_score": 1.0, "arguments": {"language": "python"}, "reason": "string"}'
        )

        req_payload = {
            "model": local_model,
            "prompt": f"{system_instructions}\n\nUser Input: {message}\n\nJSON Output:",
            "format": "json",
            "stream": False,
            "options": {
                "temperature": 0.0,
            }
        }
        try:
            t_start = time.time()
            resp = requests.post(
                f"{ollama_base}/api/generate",
                json=req_payload,
                timeout=timeout
            )
            dur_ms = int((time.time() - t_start) * 1000)
            if resp.status_code == 200:
                raw_resp = resp.json().get("response", "").strip()
                if raw_resp.startswith("```json"):
                    raw_resp = raw_resp[7:]
                if raw_resp.startswith("```"):
                    raw_resp = raw_resp[3:]
                if raw_resp.endswith("```"):
                    raw_resp = raw_resp[:-3]
                parsed_res = json.loads(raw_resp.strip())
                selected_tool = parsed_res.get("selected_tool") or parsed_res.get("selected_skill") or parsed_res.get("selected_skills")
                if isinstance(selected_tool, list):
                    selected_names = selected_tool
                elif selected_tool:
                    selected_names = [selected_tool]
                else:
                    selected_names = []

                confidence_val = float(parsed_res.get("confidence_score") or 1.0)

                for s_name in selected_names:
                    if s_name == "GENERAL_FALLBACK":
                        continue
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
                    chosen_desc = f"{s_name}. {matched_obj.get('description', '')}".strip() if matched_obj and matched_obj.get('description') else (matched_obj.get('description', '') if matched_obj else s_name)
                    evidence_skills.append({
                        "name": s_name,
                        "similarity": confidence_val,
                        "description": chosen_desc,
                        "selection_method": f"LLM Selection ({local_model})"
                    })

                # Log LLM invocation event with request payload as input and response as output
                send_llm_invocation_log(
                    logging_url=logging_url,
                    input_payload=req_payload,
                    output_response=parsed_res,
                    conv_id=conv_id,
                    model=local_model,
                    duration_ms=dur_ms,
                    desc=f"Local DeepSeek Skill Selection ({local_model})"
                )
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
    api_key: Optional[str] = None,
    conv_id: Optional[str] = None,
    logging_url: Optional[str] = None,
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
        req_payload = {
            "model": model_name,
            "prompt": prompt_content,
            "response_mime_type": "application/json"
        }
        t_start = time.time()
        resp = client.models.generate_content(
            model=model_name,
            contents=prompt_content,
            config=types.GenerateContentConfig(
                temperature=0.1,
                response_mime_type="application/json"
            )
        )
        dur_ms = int((time.time() - t_start) * 1000)
        if resp and resp.text:
            parsed_res = json.loads(resp.text.strip())
            selected_names = parsed_res.get("selected_skills", [])
            if isinstance(selected_names, str):
                selected_names = [selected_names]

            # Log LLM invocation event with request payload as input and response as output
            send_llm_invocation_log(
                logging_url=logging_url,
                input_payload=req_payload,
                output_response=parsed_res,
                conv_id=conv_id,
                model=model_name,
                duration_ms=dur_ms,
                desc=f"Gemini LLM Skill Selection ({model_name})"
            )

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
                desc = matched_obj.get("description", "") if matched_obj else ""
                criteria_text = f"{s_name}. {desc}".strip() if desc else s_name
                evidence_skills.append({
                    "name": s_name,
                    "similarity": 1.0,
                    "description": criteria_text,
                    "selection_method": f"LLM Selection ({model_name})"
                })
    except Exception as e:
        logger.warning(f"Gemini skill selection failed: {e}")
        error = str(e)

    return matched_skills, evidence_skills, error
