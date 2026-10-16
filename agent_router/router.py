import os
import json
import time
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Tuple
import requests

try:
    from .registry import AgentRegistry, AgentInfo
    from .embeddings import EmbeddingEngine
except (ImportError, ValueError):
    from registry import AgentRegistry, AgentInfo
    from embeddings import EmbeddingEngine


logger = logging.getLogger(__name__)

SIMILARITY_THRESHOLD = 0.50  # 50% threshold specified in requirements

class AgentMatchScore:
    def __init__(
        self,
        agent_id: str,
        agent_name: str,
        score: float,
        status: str,
        is_available: bool,
        is_default: bool,
    ):
        self.agent_id = agent_id
        self.agent_name = agent_name
        self.score = float(score)
        self.status = status
        self.is_available = is_available
        self.is_default = is_default

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "score": round(self.score, 4),
            "similarity_percent": f"{round(self.score * 100, 1)}%",
            "status": self.status,
            "is_available": self.is_available,
            "is_default": self.is_default,
        }

class RoutingResult:
    def __init__(
        self,
        query: str,
        selected_agent: Optional[AgentInfo] = None,
        similarity_score: float = 0.0,
        ranked_scores: Optional[List[AgentMatchScore]] = None,
        is_default_fallback: bool = False,
        response_data: Optional[Dict[str, Any]] = None,
        explanation: str = "",
        routing_latency_ms: float = 0.0,
        total_latency_ms: float = 0.0,
        threshold: float = SIMILARITY_THRESHOLD,
        status_code: int = 200,
        model_used: Optional[str] = None,
        selector_type: Optional[str] = None,
    ):
        self.query = query
        self.selected_agent = selected_agent
        self.similarity_score = round(similarity_score, 4)
        self.ranked_scores = ranked_scores or []
        self.is_default_fallback = is_default_fallback
        self.response_data = response_data
        self.explanation = explanation
        self.routing_latency_ms = round(routing_latency_ms, 2)
        self.total_latency_ms = round(total_latency_ms, 2)
        self.threshold = threshold
        self.status_code = int(status_code)
        self.model_used = model_used
        self.selector_type = selector_type

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "selected_agent": self.selected_agent.to_dict() if self.selected_agent else None,
            "similarity_score": self.similarity_score,
            "similarity_percent": f"{round(self.similarity_score * 100, 1)}%",
            "threshold": self.threshold,
            "is_default_fallback": self.is_default_fallback,
            "ranked_scores": [s.to_dict() for s in self.ranked_scores],
            "response": self.response_data,
            "explanation": self.explanation,
            "routing_latency_ms": self.routing_latency_ms,
            "total_latency_ms": self.total_latency_ms,
            "model_used": self.model_used,
            "selector_type": self.selector_type,
        }

class VectorRouter:
    """Routes incoming queries to the most semantically relevant agent using vector embeddings.
    
    If no specialized agent has a similarity score higher than 50% (0.50),
    or if the best matching specialized agent is offline (DOWN),
    the router falls back to the default agents container.
    """

    def __init__(
        self,
        registry: AgentRegistry,
        embedding_engine: Optional[EmbeddingEngine] = None,
        threshold: float = SIMILARITY_THRESHOLD,
        gemini_api_key: Optional[str] = None,
        selector_type: str = "embedding",
        active_model: str = "bge-large",
        logging_url: Optional[str] = None,
    ):
        self.registry = registry
        self.embedding_engine = embedding_engine or registry.embedding_engine
        self.threshold = threshold
        self.gemini_api_key = gemini_api_key or os.environ.get("GEMINI_API_KEY", "")
        self.selector_type = selector_type
        self.active_model = active_model
        self.logging_url = logging_url or os.environ.get("LOGGING_URL", "http://logging:8006")

    def _log_router_event(self, invoker: str, recipient: str, event_type: str, desc: str, payload: Dict[str, Any], conv_id: Optional[str] = None, status: str = "success", duration_ms: int = 0, model: str = "", user: Optional[str] = None, domain: Optional[str] = None, target: Optional[str] = None):
        try:
            url = self.logging_url
            if not os.environ.get("RUNNING_IN_DOCKER") and "logging:8006" in url:
                url = url.replace("logging:8006", "127.0.0.1:8006")
            tgt = target or recipient
            log_body = {
                "invoker": invoker,
                "recipient": recipient,
                "target": tgt,
                "conversation_id": conv_id,
                "type": event_type,
                "short_description": desc,
                "payload": payload,
                "status": status,
                "duration_ms": duration_ms,
                "model": model,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            if user:
                log_body["user"] = user
            if domain:
                log_body["domain"] = domain
            requests.post(f"{url}/api/logs", json=log_body, timeout=2)
        except Exception:
            pass

    def decide_route_with_llm(
        self,
        query: str,
        candidate_agents: Optional[List[AgentInfo]] = None,
        conv_id: Optional[str] = None,
    ) -> (AgentInfo, float, List[AgentMatchScore], bool, str, float):
        """Uses the Main LLM with structured JSON representing all agents' semantic fields to pick the agent."""
        start_time = time.time()
        all_agents = candidate_agents if candidate_agents is not None else self.registry.list_all_agents()
        default_agent = next((a for a in all_agents if a.is_default), None) or self.registry.get_default_agent()

        if not all_agents:
            routing_latency = (time.time() - start_time) * 1000.0
            return None, 0.0, [], True, "No agents registered in system.", routing_latency

        # Fields used for semantic understanding of all agents in JSON
        agent_fields_json = []
        for a in all_agents:
            agent_fields_json.append({
                "id": a.id,
                "title": a.name,
                "description": a.description,
                "sample_prompts": a.sample_prompts or [],
                "is_default": a.is_default,
                "status": a.status,
            })

        system_instruction = (
            "You are an intelligent Agent Router orchestrator.\n"
            "Given a user prompt and a list of available agents with their semantic fields (title, description, sample prompts) in JSON format, "
            "analyze the prompt and select which agent should be used to process the prompt.\n"
            "If the prompt matches a specialized agent's purpose, select that specialized agent.\n"
            "If no specialized agent is an appropriate match or if the prompt is general conversation, select the default agent (agents-default).\n"
            "Respond ONLY with a JSON object in this exact format:\n"
            "{\n"
            '  "selected_agent_id": "<id of the agent>",\n'
            '  "confidence_score": <float between 0.0 and 1.0>,\n'
            '  "reasoning": "<short explanation why this agent was chosen>"\n'
            "}"
        )

        user_content = (
            f"Available Agents:\n{json.dumps(agent_fields_json, indent=2)}\n\n"
            f"User Prompt to Route:\n\"{query}\""
        )

        selected_id = default_agent.id if default_agent else (all_agents[0].id if all_agents else "")
        confidence = 1.0
        reasoning = "Default selection"
        llm_model_used = "gemini-3.5-flash-lite"
        llm_success = False

        if self.gemini_api_key:
            try:
                from google import genai
                from google.genai import types
                client = genai.Client(api_key=self.gemini_api_key)

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
                        llm_success = True
                        break
                    except Exception as e:
                        logger.warning(f"Error calling LLM {try_model} for agent routing: {e}")
            except Exception as outer_e:
                logger.error(f"Failed to initialize GenAI client in router: {outer_e}")

        # Locate selected agent object
        target_agent = next((a for a in all_agents if a.id == selected_id), None)
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
            scored.append(AgentMatchScore(
                agent_id=a.id,
                agent_name=a.name,
                score=confidence if (target_agent and a.id == target_agent.id) else 0.0,
                status=a.status,
                is_available=a.is_available,
                is_default=a.is_default,
            ))
        scored.sort(key=lambda x: x.score, reverse=True)

        self.last_model_used = llm_model_used
        self.last_selector_type = "llm"

        return target_agent, confidence, scored, is_fallback, explanation, routing_latency

    def decide_route(
        self,
        query: str,
        threshold: Optional[float] = None,
        candidate_agents: Optional[List[AgentInfo]] = None,
        model: Optional[str] = None,
        conv_id: Optional[str] = None,
        selector_type: Optional[str] = None,
    ) -> (AgentInfo, float, List[AgentMatchScore], bool, str, float):
        """Calculates embeddings or queries Main LLM, scores active agents, and selects agent."""
        effective_sel = selector_type or getattr(self, "selector_type", "embedding")
        is_llm = (effective_sel == "llm" or model in ["main_llm", "llm", "Main LLM select"])

        if is_llm:
            return self.decide_route_with_llm(query, candidate_agents=candidate_agents, conv_id=conv_id)

        start_time = time.time()
        effective_threshold = threshold if threshold is not None else self.threshold
        target_model = model or getattr(self, "active_model", None) or getattr(self.embedding_engine, "model", "bge-large:latest")
        self.last_model_used = target_model
        self.last_selector_type = "embedding"
        query_vec = self.embedding_engine.embed_text(query, model=target_model)

        all_agents = candidate_agents if candidate_agents is not None else self.registry.list_all_agents()
        default_agent = next((a for a in all_agents if a.is_default), None) or self.registry.get_default_agent()

        if not all_agents:
            routing_latency = (time.time() - start_time) * 1000.0
            return None, 0.0, [], True, "No agents registered in system.", routing_latency

        scored: List[AgentMatchScore] = []

        # Score every candidate agent
        for agent in all_agents:
            agent_vec = agent.get_embedding_for_model(self.embedding_engine, model=target_model)
            sample_vecs = agent.get_sample_embeddings_for_model(self.embedding_engine, model=target_model)

            sims = [self.embedding_engine.compute_similarity(query_vec, agent_vec)]
            for s_emb in sample_vecs:
                sims.append(self.embedding_engine.compute_similarity(query_vec, s_emb))
            sim = max(sims) if sims else 0.0

            scored.append(AgentMatchScore(
                agent_id=agent.id,
                agent_name=agent.name,
                score=sim,
                status=agent.status,
                is_available=agent.is_available,
                is_default=agent.is_default,
            ))

        # Sort all scored agents descending by similarity score
        scored.sort(key=lambda x: x.score, reverse=True)

        # Sort specialized agents descending by similarity
        specialized_scored = [s for s in scored if not s.is_default]
        specialized_scored.sort(key=lambda x: x.score, reverse=True)

        routing_latency = (time.time() - start_time) * 1000.0

        # Check if we have a specialized candidate
        if specialized_scored:
            top_match = specialized_scored[0]
            # Rule: Match must be HIGHER than threshold
            default_score = next((s.score for s in scored if s.is_default), 0.0)
            if top_match.score > effective_threshold:
                if top_match.is_available:
                    target_agent = next((a for a in all_agents if a.id == top_match.agent_id), None) or self.registry.get_agent(top_match.agent_id)
                    explanation = (
                        f"Specialized match '{top_match.agent_name}' exceeded {int(effective_threshold * 100)}% threshold "
                        f"with score {top_match.score:.4f} ({top_match.score * 100:.1f}%)."
                    )
                    return target_agent, top_match.score, scored, False, explanation, routing_latency
                else:
                    explanation = (
                        f"Top specialized agent '{top_match.agent_name}' matched at {top_match.score * 100:.1f}%, "
                        f"but status is DOWN. Falling back to default agents container."
                    )
                    return default_agent, default_score, scored, True, explanation, routing_latency
            else:
                default_score = next((s.score for s in scored if s.is_default), 0.0)
                explanation = (
                    f"No specialized agent matched above {int(effective_threshold * 100)}% threshold "
                    f"(best candidate '{top_match.agent_name}' scored {top_match.score * 100:.1f}%). "
                    f"Defaulting to primary agents container."
                )
                return default_agent, default_score, scored, True, explanation, routing_latency

        # If no specialized agent is registered, use default
        default_score = next((s.score for s in scored if s.is_default), 0.0)
        explanation = "No specialized agents registered. Defaulting to primary agents container."
        return default_agent, default_score, scored, True, explanation, routing_latency

    def forward_request(
        self,
        agent: AgentInfo,
        payload: Dict[str, Any],
        headers: Optional[Dict[str, str]] = None,
        timeout: int = 180,
        conv_id: Optional[str] = None,
    ) -> Tuple[Dict[str, Any], int]:
        """Dispatches chat request to agent container over HTTP REST protocol."""
        url = f"{agent.url}/api/agent/chat"
        req_headers = {"Content-Type": "application/json"}
        if headers:
            for k, v in headers.items():
                if k.lower() in ["authorization", "x-user-id", "x-domain", "x-invoker"]:
                    req_headers[k] = v

        # Identify self as invoker
        payload["invoker"] = "agents_router"
        req_headers["X-Invoker"] = "agents_router"

        c_id = conv_id or (payload.get("conversation_id") if isinstance(payload, dict) else None)
        target_name = agent.name or agent.id
        user_name = payload.get("user") or payload.get("username")
        domain_name = payload.get("domain")

        # Create log that agents_router is forwarding prompt to target agent
        self._log_router_event(
            invoker="agents_router",
            recipient=target_name,
            target=target_name,
            event_type="forward_chat_request",
            desc=f"Agent Router forwarding prompt to '{target_name}'",
            payload={
                "message": payload.get("message") or payload.get("query"),
                "conversation_id": c_id,
                "target_agent": target_name,
                "target_agent_id": agent.id,
                "target_url": url,
                "request": payload,
                "request_payload": payload,
                "invoker": "agents_router",
                "target": target_name
            },
            conv_id=c_id,
            user=user_name,
            domain=domain_name
        )

        logger.info(f"Forwarding prompt to agent '{agent.id}' at {url}...")
        resp = requests.post(url, json=payload, headers=req_headers, timeout=timeout)
        agent.queries_handled += 1
        return resp.json(), resp.status_code

    def route_and_execute(
        self,
        query: str,
        payload: Dict[str, Any],
        headers: Optional[Dict[str, str]] = None,
        model: Optional[str] = None,
        conv_id: Optional[str] = None,
    ) -> RoutingResult:
        """Decides agent route based on vector embedding or LLM and executes prompt via HTTP REST."""
        total_start = time.time()
        req_model = model or (payload.get("embedder_model") or payload.get("router_model") if isinstance(payload, dict) else None)
        if req_model == "default":
            req_model = None
        req_sel = payload.get("selector_type") or payload.get("agent_selector") if isinstance(payload, dict) else None
        agent, top_score, ranked, is_fallback, explanation, route_ms = self.decide_route(
            query,
            model=req_model,
            conv_id=conv_id,
            selector_type=req_sel
        )

        model_used = (
            getattr(self, "last_model_used", None)
            or req_model
            or getattr(self, "active_model", "bge-large:latest")
        )
        selector_type = (
            getattr(self, "last_selector_type", None)
            or req_sel
            or getattr(self, "selector_type", "embedding")
        )
        display_model = "Main LLM select" if (selector_type == "llm" or getattr(self, "active_model", "") == "main_llm") else model_used
        chosen_agent = agent.name if agent else "Default Multi-Tool Agent"

        # Full payload of the routing response about which agent should be used
        routing_decision_response = {
            "selected_agent": agent.to_dict() if agent else None,
            "model_used": display_model,
            "underlying_model": model_used,
            "selector_type": selector_type,
            "similarity_score": round(top_score, 4),
            "similarity_percent": f"{round(top_score * 100, 1)}%",
            "threshold": round(self.threshold, 4),
            "is_default_fallback": is_fallback,
            "explanation": explanation,
            "routing_latency_ms": round(route_ms, 2),
            "ranked_scores": [s.to_dict() for s in (ranked or [])]
        }

        user_name = payload.get("user") or payload.get("username") if isinstance(payload, dict) else None
        domain_name = payload.get("domain") if isinstance(payload, dict) else None
        c_id = conv_id or (payload.get("conversation_id") if isinstance(payload, dict) else None)

        # Log routing decision immediately after deciding which agent to use, before forwarding prompt to agent
        self._log_router_event(
            invoker="agents_router",
            recipient="agents_router",
            target="agents_router",
            event_type="agent_router",
            desc=f"Agent Router routed query to '{chosen_agent}' using {display_model} ({round(route_ms)}ms)",
            payload={
                "request": payload,
                "response": routing_decision_response,
                "request_payload": payload,
                "response_payload": routing_decision_response,
                "model_used": display_model,
                "selected_agent": chosen_agent
            },
            conv_id=c_id,
            duration_ms=int(route_ms),
            status="success" if agent else "error",
            model=display_model,
            user=user_name,
            domain=domain_name
        )

        if not agent:
            return RoutingResult(
                query=query,
                explanation=explanation,
                routing_latency_ms=route_ms,
                total_latency_ms=(time.time() - total_start) * 1000.0,
                model_used=model_used,
                selector_type=selector_type,
            )

        resp_data = None
        status_code = 200
        try:
            resp_data, status_code = self.forward_request(agent, payload, headers=headers, conv_id=conv_id)
        except Exception as e:
            logger.error(f"Failed to communicate with agent '{agent.id}' at {agent.url}: {e}")
            # If specialized agent failed, try fallback to default agent if not already default
            default_agent = self.registry.get_default_agent()
            if agent.id != default_agent.id and default_agent:
                logger.warning(f"Specialized agent failed; falling back to default agent '{default_agent.id}'...")
                try:
                    resp_data, status_code = self.forward_request(default_agent, payload, headers=headers, conv_id=conv_id)
                    explanation += f" (Specialized agent unreachable; recovered via default agent)."
                    agent = default_agent
                    is_fallback = True
                except Exception as ex2:
                    resp_data = {"error": f"Failed reaching both specialized ({e}) and default agent ({ex2})"}
                    status_code = 502
            else:
                resp_data = {"error": f"Agent communication failure: {str(e)}"}
                status_code = 502

        total_latency = (time.time() - total_start) * 1000.0

        # Inject routing metadata into the response
        if isinstance(resp_data, dict):
            if "conversation_id" not in resp_data and payload.get("conversation_id"):
                resp_data["conversation_id"] = payload.get("conversation_id")
            resp_data["router_metadata"] = {
                "routed_agent_id": agent.id,
                "routed_agent_name": agent.name,
                "routed_agent_url": agent.url,
                "similarity_score": round(top_score, 4),
                "threshold": self.threshold,
                "is_default_fallback": is_fallback,
                "routing_latency_ms": round(route_ms, 2),
                "total_latency_ms": round(total_latency, 2),
                "explanation": explanation,
                "model_used": model_used,
                "selector_type": selector_type,
            }

        return RoutingResult(
            query=query,
            selected_agent=agent,
            similarity_score=top_score,
            ranked_scores=ranked,
            is_default_fallback=is_fallback,
            response_data=resp_data,
            explanation=explanation,
            routing_latency_ms=route_ms,
            total_latency_ms=total_latency,
            threshold=self.threshold,
            status_code=status_code,
            model_used=model_used,
            selector_type=selector_type,
        )
