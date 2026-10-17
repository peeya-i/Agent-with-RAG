import os
import time
import json
import logging
import requests
from datetime import datetime, timezone
from typing import List, Tuple, Optional, Any, Dict

try:
    from .registry import AgentInfo
except ImportError:
    from registry import AgentInfo

logger = logging.getLogger("agent_router.llm_router")


def send_llm_invocation_log(
    logging_url: Optional[str],
    input_payload: Any,
    output_response: Any,
    conv_id: Optional[str] = None,
    model: Optional[str] = None,
    duration_ms: int = 0,
    desc: str = "LLM invocation",
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
        logger.debug(f"Failed to post llm_invocation log: {e}")


def find_agent(selected_id: Optional[str], all_agents: List[AgentInfo]) -> Optional[AgentInfo]:
    """Tolerant and robust lookup of agent by ID, slug, or name."""
    if not selected_id:
        return None
    sel = str(selected_id).strip().lower()

    # 1. Exact ID match (case-insensitive)
    for a in all_agents:
        if a.id.lower() == sel:
            return a

    # 2. Normalized ID match without prefixes ('agent-', 'agents-') or punctuation
    def normalize_id(text: str) -> str:
        t = str(text).lower().strip()
        for prefix in ["agent-", "agent_", "agents-", "agents_"]:
            if t.startswith(prefix):
                t = t[len(prefix):]
        return t.replace("-", "").replace("_", "").replace(" ", "")

    sel_norm = normalize_id(sel)
    for a in all_agents:
        if normalize_id(a.id) == sel_norm:
            return a

    # 3. Exact match against agent.name (case-insensitive)
    for a in all_agents:
        if a.name.lower() == sel:
            return a

    # 4. Normalized name match
    for a in all_agents:
        a_name_norm = normalize_id(a.name)
        if a_name_norm == sel_norm or sel_norm in a_name_norm or a_name_norm in sel_norm:
            return a

    # 5. Substring ID match
    for a in all_agents:
        a_norm = normalize_id(a.id)
        if sel_norm and (sel_norm in a_norm or a_norm in sel_norm):
            return a

    return None


def build_routing_prompt(
    all_agents: List[AgentInfo],
    query: str,
    max_sample_prompts: Optional[int] = None
) -> Tuple[str, str]:
    """Constructs unified system instruction and user content for LLM agent routing (Gemini, Ollama, etc.)."""
    valid_ids = [a.id for a in all_agents]
    valid_ids_str = ", ".join([f"'{aid}'" for aid in valid_ids])

    agent_fields_json = []
    for a in all_agents:
        prompts = a.sample_prompts or []
        if max_sample_prompts is not None and max_sample_prompts > 0:
            prompts = prompts[:max_sample_prompts]
        agent_fields_json.append({
            "agent_id": a.id,
            "name": a.name,
            "description": a.description,
            "sample_prompts": prompts,
            "is_default": a.is_default,
            "status": a.status,
        })

    system_instruction = (
        "You are an intelligent AI Agent Router orchestrator.\n"
        "Given a user prompt and a list of available candidate agents with their semantic fields (name, description, sample prompts) in JSON format, "
        "analyze the prompt and select which agent should be used to process the prompt.\n"
        f"The candidate agent IDs are: {valid_ids_str}.\n"
        "If the prompt matches a specialized agent's purpose, select that specialized agent.\n"
        "If no specialized agent is an appropriate match or if the prompt is general conversation, select the default agent (agents-default).\n"
        "Respond ONLY with a JSON object in this exact format:\n"
        "{\n"
        f'  "selected_agent_id": "<exact agent_id from candidate list: {valid_ids_str}>",\n'
        '  "confidence_score": <float between 0.0 and 1.0>,\n'
        '  "reasoning": "<short explanation why this agent was chosen>"\n'
        "}\n"
        "CRITICAL: Do NOT alter, shorten, or remove prefixes from the selected_agent_id. Copy it exactly as provided."
    )

    user_content = (
        f"Available Agents:\n{json.dumps(agent_fields_json, indent=2)}\n\n"
        f"User Prompt to Route:\n\"{query}\""
    )

    return system_instruction, user_content


def build_gemini_routing_prompt(all_agents: List[AgentInfo], query: str) -> Tuple[str, str]:
    """Constructs routing prompt for Gemini Main LLM."""
    return build_routing_prompt(all_agents, query)


def decide_route_with_gemini(
    query: str,
    all_agents: List[AgentInfo],
    default_agent: Optional[AgentInfo],
    gemini_api_key: Optional[str] = None,
    conv_id: Optional[str] = None,
    logging_url: Optional[str] = None,
) -> Tuple[Optional[AgentInfo], float, List[Dict[str, Any]], bool, str, float, str]:
    """Uses Google GenAI / Gemini to select the target agent."""
    start_time = time.time()
    if not all_agents:
        latency = (time.time() - start_time) * 1000.0
        return None, 0.0, [], True, "No agents registered in system.", latency, "gemini-3.5-flash-lite"

    system_instruction, user_content = build_gemini_routing_prompt(all_agents, query)
    selected_id = default_agent.id if default_agent else (all_agents[0].id if all_agents else "")
    confidence = 1.0
    reasoning = "Default selection"
    llm_model_used = "gemini-3.5-flash-lite"

    if gemini_api_key:
        try:
            from google import genai
            from google.genai import types
            client = genai.Client(api_key=gemini_api_key)

            candidate_models = ["gemini-3.5-flash-lite", "gemini-3.1-flash-lite", "gemma-4-26b-a4b-it", "gemini-3.8-flash"]
            for try_model in candidate_models:
                try:
                    llm_start = time.time()
                    resp = client.models.generate_content(
                        model=try_model,
                        contents=user_content,
                        config=types.GenerateContentConfig(
                            system_instruction=system_instruction,
                            temperature=0.1,
                            max_output_tokens=600,
                            response_mime_type="application/json"
                        )
                    )
                    dur_ms = int((time.time() - llm_start) * 1000)
                    resp_text = resp.text.strip() if resp and resp.text else "{}"
                    parsed = json.loads(resp_text)
                    selected_id = parsed.get("selected_agent_id") or selected_id
                    confidence = float(parsed.get("confidence_score") or parsed.get("confidence") or 0.95)
                    reasoning = parsed.get("reasoning") or "LLM routing decision"
                    llm_model_used = try_model

                    # Log LLM invocation event with request payload as input and response as output
                    req_payload = {
                        "model": try_model,
                        "system_instruction": system_instruction,
                        "prompt": user_content
                    }
                    send_llm_invocation_log(
                        logging_url=logging_url,
                        input_payload=req_payload,
                        output_response=parsed,
                        conv_id=conv_id,
                        model=try_model,
                        duration_ms=dur_ms,
                        desc=f"Main LLM Agent Routing Decision ({try_model})"
                    )
                    break
                except Exception as e:
                    logger.warning(f"Error calling LLM {try_model} for agent routing: {e}")
        except Exception as outer_e:
            logger.error(f"Failed to initialize GenAI client in router: {outer_e}")

    # Locate selected agent object tolerantly
    target_agent = find_agent(selected_id, all_agents)
    if not target_agent:
        target_agent = default_agent or (all_agents[0] if all_agents else None)
        reasoning += " (Target agent not found, reverted to default)"

    # Check availability
    is_fallback = False
    if target_agent and not target_agent.is_available:
        is_fallback = True
        explanation = f"Main LLM selected '{target_agent.name}', but status is DOWN. Falling back to default agents container."
        target_agent = default_agent
    elif target_agent and target_agent.is_default:
        is_fallback = True
        explanation = f"Main LLM selected Default Agent: {reasoning}"
    else:
        explanation = f"Main LLM specialized routing: {reasoning}"

    routing_latency = (time.time() - start_time) * 1000.0

    scored = []
    for a in all_agents:
        scored.append({
            "agent_id": a.id,
            "agent_name": a.name,
            "score": confidence if (target_agent and a.id == target_agent.id) else 0.0,
            "status": a.status,
            "is_available": a.is_available,
            "is_default": a.is_default,
        })
    scored.sort(key=lambda x: x["score"], reverse=True)

    return target_agent, confidence, scored, is_fallback, explanation, routing_latency, llm_model_used


def build_ollama_routing_prompt(all_agents: List[AgentInfo], query: str) -> Tuple[str, str]:
    """Constructs routing prompt for Ollama local LLM (caps sample prompts to 3)."""
    return build_routing_prompt(all_agents, query, max_sample_prompts=3)


def decide_route_with_ollama(
    query: str,
    model_name: str,
    all_agents: List[AgentInfo],
    default_agent: Optional[AgentInfo],
    ollama_url: Optional[str] = None,
    conv_id: Optional[str] = None,
    logging_url: Optional[str] = None,
) -> Tuple[Optional[AgentInfo], float, List[Dict[str, Any]], bool, str, float, str]:
    """Uses a local Ollama LLM (Nimble-V3 choice routing or DeepSeek JSON routing) to route the user query."""
    start_time = time.time()
    if not all_agents:
        latency = (time.time() - start_time) * 1000.0
        return None, 0.0, [], True, "No agents registered in system.", latency, f"Local {model_name}"

    clean_model = model_name.replace("local:", "").replace("Local ", "").strip()
    selected_id = default_agent.id if default_agent else (all_agents[0].id if all_agents else "")
    confidence = 1.0
    reasoning = f"Local Ollama {clean_model} routing decision"

    ollama_base = ollama_url or os.environ.get("OLLAMA_URL", "http://ollama:11434")
    if not os.environ.get("RUNNING_IN_DOCKER") and "ollama:11434" in ollama_base:
        ollama_base = ollama_base.replace("ollama:11434", "localhost:11434")

    is_nimble = "nimble" in clean_model.lower()

    if is_nimble:
        # Nimble-v3 choice router using /v1/systemone endpoint
        criteria = {}
        for a in all_agents:
            criteria[a.id] = f"{a.name}. {a.description}".strip()

        req_payload = {
            "model": "nimble-v3",
            "state": query,
            "questions": {
                "route_intent": {
                    "type": "choice",
                    "instructions": "Which specialized tool or category fits the user's intent?",
                    "criteria": criteria
                }
            }
        }
        try:
            llm_start = time.time()
            resp = requests.post(f"{ollama_base}/v1/systemone", json=req_payload, timeout=60)
            dur_ms = int((time.time() - llm_start) * 1000)
            if resp.status_code == 200:
                data = resp.json()
                if "error" in data:
                    raise RuntimeError(f"Nimble error: {data['error']}")
                selected_choice = data.get("answers", {}).get("route_intent", {}).get("choice")
                if selected_choice:
                    selected_id = selected_choice
                confidence = 1.0
                reasoning = f"Nimble-V3 choice classification selected '{selected_id}'"

                # Log LLM invocation event
                send_llm_invocation_log(
                    logging_url=logging_url,
                    input_payload=req_payload,
                    output_response=data,
                    conv_id=conv_id,
                    model=clean_model,
                    duration_ms=dur_ms,
                    desc=f"Local Nimble-V3 Agent Routing Decision ({clean_model})"
                )
        except Exception as e:
            logger.warning(f"Error calling local Nimble model {clean_model}: {e}")
            reasoning += f" (Fallback due to: {e})"

        target_agent = find_agent(selected_id, all_agents)
        if not target_agent:
            target_agent = default_agent or (all_agents[0] if all_agents else None)
            reasoning += " (Target agent not found, reverted to default)"

        is_fallback = False
        display_label = f"Local {clean_model}"
        if target_agent and not target_agent.is_available:
            is_fallback = True
            explanation = f"{display_label} selected '{target_agent.name}', but status is DOWN. Falling back to default agents container."
            target_agent = default_agent
        elif target_agent and target_agent.is_default:
            is_fallback = True
            explanation = f"{display_label} selected Default Agent: {reasoning}"
        else:
            explanation = f"{display_label} specialized routing: {reasoning}"

        routing_latency = (time.time() - start_time) * 1000.0

        # Return just 1 agent with confidence of 1 and routing_latency
        scored = [{
            "agent_id": target_agent.id,
            "agent_name": target_agent.name,
            "score": 1.0,
            "status": target_agent.status,
            "is_available": target_agent.is_available,
            "is_default": target_agent.is_default,
        }]

        return target_agent, 1.0, scored, is_fallback, explanation, routing_latency, display_label

    else:
        # DeepSeek and general Ollama models using test_deepseek.py style
        agent_lines = []
        for a in all_agents:
            desc = a.description or a.name
            agent_lines.append(f"- {a.id}: {desc}")
        agents_list_str = "\n".join(agent_lines)

        system_instructions = (
            "You are an intelligent routing engine. Classify the user query into the single best tool and provide the reason for selecting:\n"
            f"{agents_list_str}\n"
            "- GENERAL_FALLBACK: General chit-chat or questions not fitting other tools\n\n"
            "Respond ONLY with valid JSON matching this schema:\n"
            '{"selected_tool": "NAME", "confidence_score": 1.0, "arguments": {"language": "python"}, "reason": "string"}'
        )

        req_payload = {
            "model": clean_model,
            "prompt": f"{system_instructions}\n\nUser Input: {query}\n\nJSON Output:",
            "format": "json",
            "stream": False,
            "options": {
                "temperature": 0.0,
            }
        }
        try:
            llm_start = time.time()
            resp = requests.post(f"{ollama_base}/api/generate", json=req_payload, timeout=60)
            dur_ms = int((time.time() - llm_start) * 1000)
            if resp.status_code == 200:
                raw_text = resp.json().get("response", "").strip()
                if raw_text.startswith("```json"):
                    raw_text = raw_text[7:]
                if raw_text.startswith("```"):
                    raw_text = raw_text[3:]
                if raw_text.endswith("```"):
                    raw_text = raw_text[:-3]
                raw_text = raw_text.strip()
                parsed = json.loads(raw_text)
                selected_tool = parsed.get("selected_tool") or parsed.get("selected_agent_id") or parsed.get("selected_agent")
                if selected_tool and selected_tool != "GENERAL_FALLBACK":
                    selected_id = selected_tool
                elif selected_tool == "GENERAL_FALLBACK":
                    selected_id = default_agent.id if default_agent else "agents-default"

                if parsed.get("confidence_score") is not None:
                    confidence = float(parsed["confidence_score"])
                elif parsed.get("confidence") is not None:
                    confidence = float(parsed["confidence"])
                if parsed.get("reason"):
                    reasoning = parsed["reason"]
                elif parsed.get("reasoning"):
                    reasoning = parsed["reasoning"]

                # Log LLM invocation event with request payload as input and response as output
                send_llm_invocation_log(
                    logging_url=logging_url,
                    input_payload=req_payload,
                    output_response=parsed,
                    conv_id=conv_id,
                    model=clean_model,
                    duration_ms=dur_ms,
                    desc=f"Local DeepSeek Agent Routing Decision ({clean_model})"
                )
        except Exception as e:
            logger.warning(f"Error calling local Ollama model {clean_model}: {e}")
            reasoning += f" (Fallback due to: {e})"

        target_agent = find_agent(selected_id, all_agents)
        if not target_agent:
            target_agent = default_agent or (all_agents[0] if all_agents else None)
            reasoning += " (Target agent not found, reverted to default)"

        is_fallback = False
        display_label = f"Local {clean_model}"
        if target_agent and not target_agent.is_available:
            is_fallback = True
            explanation = f"{display_label} selected '{target_agent.name}', but status is DOWN. Falling back to default agents container."
            target_agent = default_agent
        elif target_agent and target_agent.is_default:
            is_fallback = True
            explanation = f"{display_label} selected Default Agent: {reasoning}"
        else:
            explanation = f"{display_label} specialized routing: {reasoning}"

        routing_latency = (time.time() - start_time) * 1000.0

        scored = []
        for a in all_agents:
            scored.append({
                "agent_id": a.id,
                "agent_name": a.name,
                "score": confidence if (target_agent and a.id == target_agent.id) else 0.0,
                "status": a.status,
                "is_available": a.is_available,
                "is_default": a.is_default,
            })
        scored.sort(key=lambda x: x["score"], reverse=True)

        return target_agent, confidence, scored, is_fallback, explanation, routing_latency, display_label
