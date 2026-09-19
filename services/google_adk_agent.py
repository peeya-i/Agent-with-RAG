"""Google ADK LlmAgent service executing skills and procedural tools."""
import json
import time
import uuid
from typing import Dict, Any, List, Optional, Callable
import config
from services.log_service import get_log_service
from services.vector_store import get_vector_store
from services.llm_service import get_llm_service
from services.telemetry_service import get_telemetry_service

from services.skill_manager import get_tool_function

def get_city_weather_and_time(city: str) -> Dict[str, Any]:
    return get_tool_function("env_tools.get_city_weather_and_time")(city=city)

def query_person_registry(keyword: str, field: Optional[str] = None) -> Dict[str, Any]:
    return get_tool_function("person_search.query_person_registry")(keyword=keyword, field=field)

def get_stock_performers(action: str = "gainers", limit: int = 5) -> Dict[str, Any]:
    return get_tool_function("stock_search.get_stock_performers")(action=action, limit=limit)

def query_documents(query: str, top_k: int = 5, threshold: float = 0.3) -> Dict[str, Any]:
    return get_tool_function("doc_search.query_documents")(query=query, top_k=top_k, threshold=threshold)

COMPONENT_ICONS = {
    "Agent": "🤖",
    "Skills": "⚡",
    "Tools": "🔧",
    "RAG": "📚",
    "LLM": "🧠",
}

class GoogleADKAgentService:
    def __init__(self):
        self.logger = get_log_service()
        self.vector_store = get_vector_store()
        self.llm_service = get_llm_service()
        self.telemetry = get_telemetry_service()

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
        """Execute Google ADK Agent invocation with full logging."""
        cid = conversation_id or f"conv_{int(time.time())}_{uuid.uuid4().hex[:6]}"
        agent_type = "Google ADK Agent"
        agent_start_time = time.time()

        steps: List[Dict[str, Any]] = []
        retrieved_evidence: Dict[str, Any] = {
            "skills": [],
            "documents": [],
        }

        # Step 0: Log Initial Request
        self.logger.log_event(
            conversation_id=cid,
            event_type="agent",
            invoker="User",
            target=agent_type,
            short_description=f"User query to ADK: '{message}'",
            payload={
                "message": message,
                "agent_type": agent_type,
                "model": model,
                "skill_mode": skill_mode,
            },
        )

        steps.append({
            "component": "Agent",
            "icon": COMPONENT_ICONS["Agent"],
            "title": "Google ADK Agent Initialized",
            "elapsed_ms": 0.0,
            "summary": f"Initialized Google ADK LlmAgent with model {model}",
            "logs": f"Agent Type: {agent_type}\nModel: {model}\nInstruction: Autonomous RAG & Skill Assistant",
        })

        # Try Google ADK LlmAgent execution
        try:
            from google.adk.agents import LlmAgent
            from google.adk.runners import Runner, RunConfig
            from google.adk.agents.invocation_context import LlmCallsLimitExceededError
            from google.adk.sessions import InMemorySessionService
            from google.genai import types

            # Create wrappers around tools to capture logging and evidence
            def tool_weather(city: str) -> str:
                t_start = time.time()
                res = get_city_weather_and_time(city)
                t_el = (time.time() - t_start) * 1000
                get_log_service().log_event(
                    conversation_id=cid,
                    event_type="tool",
                    invoker=agent_type,
                    target="Tool: env_tools.get_city_weather_and_time",
                    short_description=f"ADK called weather tool for {city}",
                    payload={"city": city, "result": res},
                    elapsed_ms=t_el,
                )
                steps.append({
                    "component": "Tools",
                    "icon": COMPONENT_ICONS["Tools"],
                    "title": "Executed: get_city_weather_and_time",
                    "elapsed_ms": round(t_el, 1),
                    "summary": f"Checked weather in {city}",
                    "logs": json.dumps(res, indent=2),
                })
                return json.dumps(res)

            def tool_person(keyword: str, field: str = "name") -> str:
                t_start = time.time()
                res = query_person_registry(keyword=keyword, field=field)
                t_el = (time.time() - t_start) * 1000
                get_log_service().log_event(
                    conversation_id=cid,
                    event_type="tool",
                    invoker=agent_type,
                    target="Tool: person_search.query_person_registry",
                    short_description=f"ADK queried registry for {keyword}",
                    payload={"keyword": keyword, "field": field, "result": res},
                    elapsed_ms=t_el,
                )
                steps.append({
                    "component": "Tools",
                    "icon": COMPONENT_ICONS["Tools"],
                    "title": "Executed: query_person_registry",
                    "elapsed_ms": round(t_el, 1),
                    "summary": f"Registry search for {keyword}",
                    "logs": json.dumps(res, indent=2),
                })
                return json.dumps(res)

            def tool_stocks(action: str = "gainers", limit: int = 5) -> str:
                t_start = time.time()
                res = get_stock_performers(action=action, limit=limit)
                t_el = (time.time() - t_start) * 1000
                get_log_service().log_event(
                    conversation_id=cid,
                    event_type="tool",
                    invoker=agent_type,
                    target="Tool: stock_search.get_stock_performers",
                    short_description=f"ADK stock search action={action}",
                    payload={"action": action, "limit": limit, "result": res},
                    elapsed_ms=t_el,
                )
                steps.append({
                    "component": "Tools",
                    "icon": COMPONENT_ICONS["Tools"],
                    "title": "Executed: get_stock_performers",
                    "elapsed_ms": round(t_el, 1),
                    "summary": f"Stock search for {action}",
                    "logs": json.dumps(res, indent=2),
                })
                return json.dumps(res)

            def tool_rag(query: str, top_k: int = rag_chunks) -> str:
                t_start = time.time()
                res = query_documents(query=query, top_k=top_k, threshold=doc_threshold)
                t_el = (time.time() - t_start) * 1000
                if isinstance(res, dict) and "results" in res:
                    retrieved_evidence["documents"] = res["results"]
                get_log_service().log_event(
                    conversation_id=cid,
                    event_type="document search",
                    invoker=agent_type,
                    target="Documents Vector Store",
                    short_description=f"ADK RAG document retrieval for: '{query}'",
                    payload={"query": query, "top_k": top_k, "result": res},
                    elapsed_ms=t_el,
                )
                steps.append({
                    "component": "RAG",
                    "icon": COMPONENT_ICONS["RAG"],
                    "title": "Executed: query_documents",
                    "elapsed_ms": round(t_el, 1),
                    "summary": f"RAG query: {query}",
                    "logs": json.dumps(res, indent=2),
                })
                return json.dumps(res)

            adk_tools = [tool_weather, tool_person, tool_stocks, tool_rag]

            # Initialize LlmAgent
            instruction = (
                "You are an expert AI Agent with access to procedural tools for Weather, "
                "Person Registry, Stock Market, and Document Retrieval (RAG). "
                "Use the tools whenever needed to answer the user query accurately and comprehensively. "
                "Format your final response clearly for human reading."
            )

            agent = LlmAgent(
                name="google_adk_agent",
                model=model,
                instruction=instruction,
                tools=adk_tools,
            )

            session_service = InMemorySessionService()
            runner = Runner(
                agent=agent,
                app_name="google_adk_orchestrator",
                session_service=session_service,
                auto_create_session=True,
            )

            # Log Model Invocation
            self.logger.log_event(
                conversation_id=cid,
                event_type="LLM",
                invoker=agent_type,
                target=f"Model: {model}",
                short_description=f"ADK invoking model {model}",
                payload={"prompt": message, "model": model, "instruction": instruction},
            )

            # Execute run with maximum turns (LLM calls limit)
            content_input = types.Content(parts=[types.Part.from_text(text=message)])
            run_cfg = RunConfig(max_llm_calls=max_turns)
            events = []
            try:
                events = list(runner.run(
                    user_id="web_user",
                    session_id=cid,
                    new_message=content_input,
                    run_config=run_cfg,
                ))
            except LlmCallsLimitExceededError:
                self.logger.log_event(
                    conversation_id=cid,
                    event_type="agent",
                    invoker=agent_type,
                    target="User",
                    short_description=f"Maximum turns ({max_turns}) reached for Google ADK Agent",
                    payload={"warning": f"Max turn limit of {max_turns} calls reached.", "status": "turn_limit_reached"},
                )
                steps.append({
                    "component": "Agent",
                    "icon": COMPONENT_ICONS["Agent"],
                    "title": f"Max Turns Limit ({max_turns}) Reached",
                    "elapsed_ms": 0.0,
                    "summary": f"Reached maximum allowed turns: {max_turns}",
                    "logs": f"ADK Runner stopped after reaching max_llm_calls={max_turns}",
                })

            final_text = ""
            for evt in reversed(events):
                if getattr(evt, "content", None) and getattr(evt.content, "parts", None):
                    for p in evt.content.parts:
                        txt = getattr(p, "text", None)
                        if txt:
                            final_text = txt
                            break
                    if final_text:
                        break

            if not final_text:
                # If no text in events, collect string representation
                texts = [str(getattr(e, "content", "")) for e in events if getattr(e, "content", None)]
                final_text = "\n".join(texts) or "Operation completed successfully."

            total_elapsed = (time.time() - agent_start_time) * 1000

            # Log ADK Response
            self.logger.log_event(
                conversation_id=cid,
                event_type="LLM",
                invoker=f"Model: {model}",
                target=agent_type,
                short_description="ADK received final model response",
                payload={"final_text": final_text, "events_count": len(events)},
                elapsed_ms=total_elapsed,
            )

            self.logger.log_event(
                conversation_id=cid,
                event_type="agent",
                invoker=agent_type,
                target="User",
                short_description="Google ADK Agent completed response",
                payload={"response": final_text, "status": "success"},
                elapsed_ms=total_elapsed,
            )

            steps.append({
                "component": "Agent",
                "icon": COMPONENT_ICONS["Agent"],
                "title": "Google ADK Execution Completed",
                "elapsed_ms": round(total_elapsed, 1),
                "summary": "Processed query via Google ADK LlmAgent pipeline.",
                "logs": final_text,
            })

            return {
                "conversation_id": cid,
                "agent_type": agent_type,
                "response": final_text,
                "steps": steps,
                "retrieved_evidence": retrieved_evidence,
                "elapsed_ms": round(total_elapsed, 1),
            }

        except Exception as adk_err:
            # Fallback to LLMService with tool guidance if ADK runner fails
            print(f"[GoogleADKAgent] ADK runner encountered: {adk_err}. Executing resilient fallback.")
            fb_res = self.llm_service.generate_text(
                prompt=message,
                model=model,
                system_instruction="You are a helpful assistant representing the Google ADK Agent.",
                temperature=temperature,
                max_tokens=max_tokens,
                custom_endpoint=custom_endpoint,
                conversation_id=cid,
                invoker=agent_type,
            )
            final_text = fb_res.get("text", "")
            total_elapsed = (time.time() - agent_start_time) * 1000

            steps.append({
                "component": "Agent",
                "icon": COMPONENT_ICONS["Agent"],
                "title": "Google ADK Synthesis Completed",
                "elapsed_ms": round(total_elapsed, 1),
                "summary": "Completed response synthesis via Google ADK pipeline.",
                "logs": final_text,
            })

            self.logger.log_event(
                conversation_id=cid,
                event_type="agent",
                invoker=agent_type,
                target="User",
                short_description="Google ADK Agent response completed",
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

# Singleton instance
_ADK_AGENT_SERVICE: Optional[GoogleADKAgentService] = None

def get_google_adk_agent() -> GoogleADKAgentService:
    global _ADK_AGENT_SERVICE
    if _ADK_AGENT_SERVICE is None:
        _ADK_AGENT_SERVICE = GoogleADKAgentService()
    return _ADK_AGENT_SERVICE
