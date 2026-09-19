"""Custom Agent orchestrator implementing multi-turn reasoning and tool execution."""
import json
import re
import time
import uuid
from typing import Dict, Any, List, Optional
import config
from services.llm_service import get_llm_service
from services.skill_manager import get_skill_manager
from services.vector_store import get_vector_store
from services.log_service import get_log_service

COMPONENT_ICONS = {
    "Agent": "🤖",
    "Skills": "⚡",
    "Tools": "🔧",
    "RAG": "📚",
    "LLM": "🧠",
}

class AgentOrchestrator:
    def __init__(self):
        self.llm = get_llm_service()
        self.skill_manager = get_skill_manager()
        self.vector_store = get_vector_store()
        self.logger = get_log_service()

    def process_message(
        self,
        message: str,
        conversation_id: Optional[str] = None,
        model: str = config.DEFAULT_LLM_MODEL,
        temperature: float = config.DEFAULT_TEMPERATURE,
        max_tokens: Optional[int] = None,
        max_turns: int = config.DEFAULT_MAX_TURNS,
        rag_chunks: int = config.DEFAULT_RAG_CHUNKS,
        skill_mode: str = "Vector Store",
        skill_threshold: float = config.DEFAULT_SKILL_THRESHOLD,
        doc_threshold: float = config.DEFAULT_DOC_THRESHOLD,
        custom_endpoint: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute Custom Agent reasoning loop per specification."""
        cid = conversation_id or f"conv_{int(time.time())}_{uuid.uuid4().hex[:6]}"
        agent_start_time = time.time()
        agent_type = "Custom Agent"

        steps: List[Dict[str, Any]] = []
        retrieved_evidence: Dict[str, Any] = {
            "skills": [],
            "documents": [],
        }

        # Step 0: Log Initial User Agent Request
        self.logger.log_event(
            conversation_id=cid,
            event_type="agent",
            invoker="User",
            target=agent_type,
            short_description=f"User query: '{message}'",
            payload={
                "message": message,
                "agent_type": agent_type,
                "model": model,
                "skill_mode": skill_mode,
                "max_turns": max_turns,
                "rag_chunks": rag_chunks,
            },
        )

        steps.append({
            "component": "Agent",
            "icon": COMPONENT_ICONS["Agent"],
            "title": "Agent Initialized",
            "elapsed_ms": 0.0,
            "summary": f"Received user query: {message}",
            "logs": f"Agent Type: {agent_type}\nModel: {model}\nMax Turns: {max_turns}\nSkill Selection Mode: {skill_mode}",
        })

        # Step 1: Skill Selection
        s_start = time.time()
        applicable_skills: List[Dict[str, Any]] = []

        if skill_mode in ["Vector Store", "Vector Store Selects"]:
            applicable_skills = self.vector_store.query_skills(
                query=message,
                threshold=skill_threshold,
                top_k=5,
                conversation_id=cid,
            )
            s_elapsed = (time.time() - s_start) * 1000
            skill_names = [s["skill_name"] for s in applicable_skills]
            retrieved_evidence["skills"] = [
                {"name": s["skill_name"], "similarity": s["similarity"], "description": s["description"]}
                for s in applicable_skills
            ]

            steps.append({
                "component": "Skills",
                "icon": COMPONENT_ICONS["Skills"],
                "title": "Vector Store Skill Matching",
                "elapsed_ms": round(s_elapsed, 1),
                "summary": f"Matched {len(applicable_skills)} skill(s) above threshold {skill_threshold}: {', '.join(skill_names) if skill_names else 'None'}",
                "logs": json.dumps(retrieved_evidence["skills"], indent=2),
            })

        elif skill_mode in ["LLM Selected", "LLM Selects"]:
            all_skills = self.skill_manager.list_available_skills()
            skills_catalog = "\n".join([f"- {s['name']}: {s['description']}" for s in all_skills])
            selector_prompt = (
                f"Given the user query: \"{message}\"\n\n"
                f"Available skills:\n{skills_catalog}\n\n"
                f"Identify which skills (at most 2) are required to answer the query. "
                f"Respond with a JSON array of skill names, e.g. [\"time-weather-skill\"]. If none apply, return []."
            )
            sel_res = self.llm.generate_text(
                prompt=selector_prompt,
                model=model,
                temperature=0.0,
                custom_endpoint=custom_endpoint,
                conversation_id=cid,
                invoker="Custom Agent",
            )
            s_elapsed = (time.time() - s_start) * 1000
            try:
                m = re.search(r"\[.*?\]", sel_res["text"], re.DOTALL)
                chosen = json.loads(m.group(0)) if m else []
                for s in all_skills:
                    if s["name"] in chosen:
                        applicable_skills.append({
                            "skill_name": s["name"],
                            "similarity": 1.0,
                            "content": s["description"],
                            "description": s["description"],
                        })
            except Exception:
                pass

            retrieved_evidence["skills"] = [
                {"name": s["skill_name"], "similarity": 1.0, "description": s["description"]}
                for s in applicable_skills
            ]
            steps.append({
                "component": "Skills",
                "icon": COMPONENT_ICONS["Skills"],
                "title": "LLM Skill Selection",
                "elapsed_ms": round(s_elapsed, 1),
                "summary": f"LLM selected {len(applicable_skills)} skill(s): {', '.join([s['skill_name'] for s in applicable_skills]) if applicable_skills else 'None'}",
                "logs": sel_res.get("text", ""),
            })

        else:
            # Specific skill selected from dropdown
            all_skills = self.skill_manager.list_available_skills()
            for s in all_skills:
                if s["name"] == skill_mode:
                    applicable_skills.append({
                        "skill_name": s["name"],
                        "similarity": 1.0,
                        "content": s["description"],
                        "description": s["description"],
                    })
                    break
            s_elapsed = (time.time() - s_start) * 1000
            retrieved_evidence["skills"] = [
                {"name": s["skill_name"], "similarity": 1.0, "description": s["description"]}
                for s in applicable_skills
            ]
            steps.append({
                "component": "Skills",
                "icon": COMPONENT_ICONS["Skills"],
                "title": "Explicit Skill Selected",
                "elapsed_ms": round(s_elapsed, 1),
                "summary": f"Using explicitly selected skill: {skill_mode}",
                "logs": f"Selected: {skill_mode}",
            })

        # Step 2: If no skills found, send directly to LLM
        if not applicable_skills:
            final_res = self.llm.generate_text(
                prompt=message,
                model=model,
                system_instruction="You are a helpful and knowledgeable AI assistant. Provide clear, accurate, and structured answers.",
                temperature=temperature,
                max_tokens=max_tokens,
                custom_endpoint=custom_endpoint,
                conversation_id=cid,
                invoker="Custom Agent",
            )
            final_text = final_res.get("text", "")
            total_elapsed = (time.time() - agent_start_time) * 1000

            steps.append({
                "component": "Agent",
                "icon": COMPONENT_ICONS["Agent"],
                "title": "Direct LLM Synthesis",
                "elapsed_ms": round(final_res.get("elapsed_ms", 0), 1),
                "summary": "No domain skills required; synthesized direct response.",
                "logs": final_text,
            })

            self.logger.log_event(
                conversation_id=cid,
                event_type="agent",
                invoker=agent_type,
                target="User",
                short_description="Direct answer completed",
                payload={"response": final_text, "status": "success"},
                elapsed_ms=total_elapsed,
            )

            return {
                "conversation_id": cid,
                "agent_type": agent_type,
                "response": final_text,
                "steps": steps,
                "retrieved_evidence": retrieved_evidence,
                "elapsed_ms": round(total_elapsed, 1),
            }

        # Step 3: Multi-turn reasoning with 2 highest matching skills
        selected_skills = applicable_skills[:2]
        skills_context = ""
        for s in selected_skills:
            skills_context += f"\n--- Skill: {s['skill_name']} ---\n{s.get('content', '')}\n"

        system_prompt = (
            "You are an advanced AI Agent orchestrator. You have access to the following skills and their procedural tools:\n"
            f"{skills_context}\n\n"
            "Instructions:\n"
            "1. Evaluate if any tool must be executed to gather facts to answer the user query.\n"
            "2. If a tool should be executed, respond ONLY with a JSON object in this exact format:\n"
            "{\n"
            "  \"tool\": \"<module_name>.<function_name>\",\n"
            "  \"arguments\": {\n"
            "    \"<arg_name>\": <arg_value>\n"
            "  }\n"
            "}\n"
            "For example: {\"tool\": \"person_search.query_person_registry\", \"arguments\": {\"keyword\": \"Lucas Dubois\", \"field\": \"name\"}}\n"
            "Or for weather: {\"tool\": \"env_tools.get_city_weather_and_time\", \"arguments\": {\"city\": \"Tokyo\"}}\n"
            "Or for documents: {\"tool\": \"doc_search.query_documents\", \"arguments\": {\"query\": \"marketing strategy\", \"top_k\": 5}}\n"
            "3. If all information is available, or no tool execution is needed, provide your final comprehensive answer directly without returning JSON."
        )

        current_prompt = f"User Question: {message}"
        turn_count = 0
        final_text = ""

        while turn_count < max_turns:
            turn_count += 1
            t_res = self.llm.generate_text(
                prompt=current_prompt,
                model=model,
                system_instruction=system_prompt,
                temperature=0.2 if turn_count < max_turns else temperature,
                max_tokens=max_tokens,
                custom_endpoint=custom_endpoint,
                conversation_id=cid,
                invoker="Custom Agent",
            )
            raw_output = t_res.get("text", "")

            # Check if output contains tool execution JSON
            tool_call = self._extract_tool_call(raw_output)
            if tool_call and "tool" in tool_call and turn_count < max_turns:
                t_name = tool_call["tool"]
                t_args = tool_call.get("arguments", {})
                
                # Check if this tool is RAG document search
                is_rag = "doc" in t_name.lower() or "document" in t_name.lower()
                component_tag = "RAG" if is_rag else "Tools"
                icon_tag = COMPONENT_ICONS["RAG"] if is_rag else COMPONENT_ICONS["Tools"]

                # If it's doc search, update top_k and threshold from UI parameters
                if is_rag:
                    t_args.setdefault("top_k", rag_chunks)
                    t_args.setdefault("threshold", doc_threshold)

                # Execute tool
                tool_start = time.time()
                t_exec = self.skill_manager.execute_tool(
                    tool_name=t_name,
                    arguments=t_args,
                    conversation_id=cid,
                    invoker=agent_type,
                )
                t_elapsed = (time.time() - tool_start) * 1000

                # Capture retrieved documents if RAG was invoked
                if is_rag and t_exec.get("status") == "success":
                    rag_res = t_exec.get("result", {})
                    if isinstance(rag_res, dict) and "results" in rag_res:
                        retrieved_evidence["documents"] = rag_res["results"]
                    elif isinstance(rag_res, list):
                        retrieved_evidence["documents"] = rag_res

                steps.append({
                    "component": component_tag,
                    "icon": icon_tag,
                    "title": f"Executed: {t_name}",
                    "elapsed_ms": round(t_elapsed, 1),
                    "summary": f"Called {t_name} with arguments: {json.dumps(t_args)}",
                    "logs": json.dumps(t_exec, indent=2),
                })

                # Append tool results into prompt for next turn
                current_prompt += (
                    f"\n\n[Turn {turn_count} Tool Observation]\n"
                    f"Tool: {t_name}\n"
                    f"Result: {json.dumps(t_exec.get('result', t_exec))}\n"
                    f"Now provide the final synthesized response to the user query, or execute another tool if needed."
                )
            else:
                # Direct response produced
                final_text = raw_output
                break

        # If loop reached max_turns without direct answer, make final synthesis call
        if not final_text:
            synth_prompt = (
                f"Original User Question: {message}\n\n"
                f"Context & Tool Observations:\n{current_prompt}\n\n"
                f"Provide a clear, helpful, and comprehensive final answer to the user based on the observations."
            )
            final_res = self.llm.generate_text(
                prompt=synth_prompt,
                model=model,
                system_instruction="You are a helpful and knowledgeable AI assistant. Format the final output clearly for human reading.",
                temperature=temperature,
                max_tokens=max_tokens,
                custom_endpoint=custom_endpoint,
                conversation_id=cid,
                invoker="Custom Agent",
            )
            final_text = final_res.get("text", "")

        total_elapsed = (time.time() - agent_start_time) * 1000

        steps.append({
            "component": "Agent",
            "icon": COMPONENT_ICONS["Agent"],
            "title": "Final Response Synthesized",
            "elapsed_ms": round(total_elapsed, 1),
            "summary": f"Completed multi-turn reasoning in {turn_count} turn(s).",
            "logs": final_text,
        })

        # Log Final Agent Response per specification
        self.logger.log_event(
            conversation_id=cid,
            event_type="agent",
            invoker=agent_type,
            target="User",
            short_description="Response completed",
            payload={"response": final_text, "status": "success"},
            elapsed_ms=total_elapsed,
        )

        return {
            "conversation_id": cid,
            "agent_type": agent_type,
            "response": final_text,
            "steps": steps,
            "retrieved_evidence": retrieved_evidence,
            "elapsed_ms": round(total_elapsed, 1),
        }

    def _extract_tool_call(self, text: str) -> Optional[Dict[str, Any]]:
        """Extract tool call JSON from text if present."""
        if not text:
            return None

        # 1. Direct parse
        try:
            obj = json.loads(text.strip())
            if isinstance(obj, dict) and "tool" in obj:
                return obj
        except Exception:
            pass

        # 2. Markdown code block
        block_m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
        if block_m:
            candidate = block_m.group(1).strip()
            try:
                obj = json.loads(candidate)
                if isinstance(obj, dict) and "tool" in obj:
                    return obj
            except Exception:
                pass

        # 3. Scan for opening brace and use JSONDecoder.raw_decode for nested objects
        decoder = json.JSONDecoder()
        for idx in range(len(text)):
            if text[idx] == "{":
                try:
                    obj, _ = decoder.raw_decode(text[idx:])
                    if isinstance(obj, dict) and "tool" in obj:
                        return obj
                except Exception:
                    continue

        return None

# Singleton instance
_AGENT_ORCHESTRATOR: Optional[AgentOrchestrator] = None

def get_agent_orchestrator() -> AgentOrchestrator:
    global _AGENT_ORCHESTRATOR
    if _AGENT_ORCHESTRATOR is None:
        _AGENT_ORCHESTRATOR = AgentOrchestrator()
    return _AGENT_ORCHESTRATOR
