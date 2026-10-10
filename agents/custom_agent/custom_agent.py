import os
import json
import time
import re
from datetime import datetime, timezone
import requests

class CustomAgent:
    def __init__(self, doc_rag_url="http://doc_rag:8003", tools_url="http://tools:8005", logging_url="http://logging:8006", gemini_api_key=None):
        self.doc_rag_url = doc_rag_url
        self.tools_url = tools_url
        self.logging_url = logging_url
        self.gemini_api_key = gemini_api_key or os.environ.get("GEMINI_API_KEY", "")

    def _resolve(self, url, host, port):
        if not os.environ.get("RUNNING_IN_DOCKER") and f"{host}:{port}" in url:
            return url.replace(f"{host}:{port}", f"127.0.0.1:{port}")
        return url

    def log(self, invoker, recipient, event_type, desc, payload, conv_id=None, status="success", dur_ms=0, in_tok=0, out_tok=0, model=None, is_error=False, user=None, domain=None):
        try:
            url = self._resolve(self.logging_url, "logging", 8006)
            requests.post(f"{url}/api/logs", json={
                "invoker": invoker,
                "recipient": recipient,
                "conversation_id": conv_id,
                "user": user or getattr(self, "current_user", None),
                "domain": domain or getattr(self, "current_domain", None),
                "type": event_type,
                "short_description": desc,
                "payload": payload,
                "status": status,
                "duration_ms": dur_ms,
                "input_tokens": in_tok,
                "output_tokens": out_tok,
                "model": model,
                "is_error": is_error,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }, timeout=2)
        except Exception:
            pass

    def call_llm(self, prompt, system_instruction=None, model="gemma-4-26b-a4b-it", temperature=0.7, max_tokens=2048, custom_endpoint=None, conv_id=None):
        start_time = time.time()
        
        # If custom OpenAI-compatible endpoint specified and model is custom
        is_custom_model = "custom" in (model or "").lower()
        if custom_endpoint and is_custom_model:
            try:
                headers = {"Content-Type": "application/json"}
                msgs = []
                if system_instruction:
                    msgs.append({"role": "system", "content": system_instruction})
                msgs.append({"role": "user", "content": prompt})

                payload = {
                    "model": model,
                    "messages": msgs,
                    "temperature": temperature,
                    "max_tokens": max_tokens
                }
                self.log(
                    invoker="Custom Agent",
                    recipient="Custom LLM",
                    event_type="llm_invocation",
                    desc=f"Sent prompt to custom model: {model}",
                    payload=payload,
                    conv_id=conv_id,
                    model=model
                )
                resp = requests.post(custom_endpoint, json=payload, headers=headers, timeout=30)
                dur_ms = int((time.time() - start_time) * 1000)
                res_json = resp.json()
                text = res_json.get("choices", [{}])[0].get("message", {}).get("content", "")
                
                usage = res_json.get("usage", {})
                in_tok = usage.get("prompt_tokens", len(prompt) // 4)
                out_tok = usage.get("completion_tokens", len(text) // 4)

                self.log(
                    invoker="Custom LLM",
                    recipient="Custom Agent",
                    event_type="llm_response",
                    desc=f"Received response from custom model: {model} ({dur_ms}ms)",
                    payload={
                        "model": model,
                        "response_text": text,
                        "response": text,
                        "raw_response": res_json,
                        "input_tokens": in_tok,
                        "output_tokens": out_tok,
                        "duration_ms": dur_ms,
                        "prompt": prompt,
                        "system_instruction": system_instruction
                    },
                    conv_id=conv_id,
                    dur_ms=dur_ms,
                    in_tok=in_tok,
                    out_tok=out_tok,
                    model=model
                )
                return text, in_tok, out_tok, dur_ms
            except Exception as e:
                dur_ms = int((time.time() - start_time) * 1000)
                self.log("Custom Agent", "Custom LLM", "llm_error", f"Error calling custom LLM: {e}", {"error": str(e)}, conv_id, "error", dur_ms, is_error=True)
                return f"Error contacting custom model: {e}", 0, 0, dur_ms

        # Google Gemini AI Studio client
        if self.gemini_api_key:
            from google import genai
            from google.genai import types
            client = genai.Client(api_key=self.gemini_api_key)

            config_params = {
                "temperature": temperature,
                "max_output_tokens": max_tokens
            }
            if system_instruction:
                config_params["system_instruction"] = system_instruction

            # Try requested model, and failover across active models on 503 / 404 / 429
            candidate_models = [model]
            for fb in ["gemini-3.1-flash-lite", "gemini-3.5-flash-lite", "gemini-3.8-flash", "gemma-4-26b-a4b-it"]:
                if fb not in candidate_models:
                    candidate_models.append(fb)

            last_err = None
            for try_model in candidate_models:
                for attempt in range(2):
                    try:
                        self.log(
                            invoker="Custom Agent",
                            recipient="LLM",
                            event_type="llm_invocation",
                            desc=f"Sent prompt to Google GenAI ({try_model})",
                            payload={
                                "model": try_model,
                                "prompt": prompt,
                                "system_instruction": system_instruction,
                                "config": config_params
                            },
                            conv_id=conv_id,
                            model=try_model
                        )

                        resp = client.models.generate_content(
                            model=try_model,
                            contents=prompt,
                            config=types.GenerateContentConfig(**config_params)
                        )
                        dur_ms = int((time.time() - start_time) * 1000)
                        text = resp.text or ""

                        # Token usage
                        usage_meta = getattr(resp, "usage_metadata", None)
                        in_tok = getattr(usage_meta, "prompt_token_count", len(prompt) // 4) or (len(prompt) // 4)
                        out_tok = getattr(usage_meta, "candidates_token_count", len(text) // 4) or (len(text) // 4)

                        self.log(
                            invoker="LLM",
                            recipient="Custom Agent",
                            event_type="llm_response",
                            desc=f"Received response from Google GenAI ({try_model}) in {dur_ms}ms",
                            payload={
                                "model": try_model,
                                "response_text": text,
                                "response": text,
                                "prompt": prompt,
                                "system_instruction": system_instruction,
                                "input_tokens": in_tok,
                                "output_tokens": out_tok,
                                "duration_ms": dur_ms
                            },
                            conv_id=conv_id,
                            dur_ms=dur_ms,
                            in_tok=in_tok,
                            out_tok=out_tok,
                            model=try_model
                        )
                        return text, in_tok, out_tok, dur_ms
                    except Exception as e:
                        last_err = e
                        err_str = str(e)
                        if "503" in err_str or "404" in err_str or "429" in err_str:
                            time.sleep(0.5)
                            continue
                        break

            dur_ms = int((time.time() - start_time) * 1000)
            self.log("Custom Agent", "LLM", "llm_error", f"Gemini API error: {last_err}", {"error": str(last_err)}, conv_id, "error", dur_ms, is_error=True)
            return self._fallback_assistant_response(prompt, system_instruction), 50, 100, dur_ms

        # Fallback simulation if no API key configured
        dur_ms = int((time.time() - start_time) * 1000)
        return self._fallback_assistant_response(prompt, system_instruction), 50, 100, dur_ms

    def _fallback_assistant_response(self, prompt, system_instruction):
        return f"Synthesized answer based on available context and tools:\n\n{prompt[-300:] if len(prompt) > 300 else prompt}"

    def run(self, message, conversation_id, model="gemma-4-26b-a4b-it", temperature=0.7, max_tokens=2048,
            max_turns=5, skill_selector="Vector Store Selects", skill_threshold=0.2, doc_threshold=0.3,
            max_chunks=5, custom_endpoint=None, api_key=None, jwt_token=None, configured_keys=None, **kwargs):
        
        configured_keys = configured_keys or {}
        jwt_token = jwt_token or kwargs.get("jwt_token")
        if not jwt_token and api_key and ("." in api_key or api_key.startswith("eyJ")):
            jwt_token = api_key
        self.current_user = kwargs.get("user") or kwargs.get("username") or kwargs.get("email") or "anonymous"
        self.current_domain = kwargs.get("domain") or ""
        agent_start = time.time()
        steps = []
        max_turns = max(1, min(int(max_turns or 5), 10))

        # Build prior conversation context if passed
        chat_history = kwargs.get("history") or []
        history_prompt = ""
        if chat_history and isinstance(chat_history, list):
            history_lines = []
            for h in chat_history[-6:]:
                role = "User" if h.get("role") in ["user", "human"] else "Assistant"
                c_text = (h.get("content") or "").strip()
                if c_text:
                    history_lines.append(f"{role}: {c_text}")
            if history_lines:
                history_prompt = "Conversation History (Prior Turns):\n" + "\n".join(history_lines) + "\n\n"

        # Initial Agent Invocaton Log
        self.log(
            invoker="Web UI",
            recipient="Custom Agent",
            event_type="received_chat_request",
            desc=f"User query received: '{message[:50]}...'",
            payload={
                "message": message,
                "agent_type": "Custom Agent",
                "model": model,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "max_turns": max_turns,
                "skill_selector": skill_selector
            },
            conv_id=conversation_id,
            model=model
        )

        steps.append({
            "component": "Agent",
            "icon": "🤖",
            "title": "Agent Initialized",
            "description": f"Processing query with {skill_selector} (Max turns: {max_turns})",
            "elapsed_ms": int((time.time() - agent_start) * 1000)
        })

        matched_skills = []
        retrieved_evidence = {
            "skills": [],
            "documents": []
        }

        # 1. Skill Selection
        s_start = time.time()
        if skill_selector == "Vector Store Selects":
            # Query doc_RAG skill vector store
            try:
                rag_url = self._resolve(self.doc_rag_url, "doc_rag", 8003)
                skill_req = {
                    "db_type": "skill",
                    "query": message,
                    "threshold": skill_threshold,
                    "limit": 2,
                    "conversation_id": conversation_id,
                    "jwt_token": jwt_token,
                    "invoker": "Custom Agent"
                }
                self.log(
                    invoker="Custom Agent",
                    recipient="Vector DB",
                    event_type="skill_vector_query",
                    desc=f"Query skills vector DB: '{message[:80]}'",
                    payload=skill_req,
                    conv_id=conversation_id
                )
                headers = {"Content-Type": "application/json"}
                if jwt_token:
                    headers["Authorization"] = f"Bearer {jwt_token}"
                resp = requests.post(f"{rag_url}/api/rag/query", json=skill_req, headers=headers, timeout=5)
                if resp.status_code == 200:
                    matched_skills = resp.json().get("results", [])
                    for s in matched_skills:
                        s_name = s.get("skill_name") or s.get("name") or "Skill"
                        score = round(float(s.get("similarity_score", 0)), 4) if s.get("similarity_score") is not None else 0.0
                        desc = (s.get("chunk_text") or s.get("text") or "")[:300]
                        retrieved_evidence["skills"].append({
                            "name": s_name,
                            "similarity": score,
                            "description": desc
                        })
                    self.log(
                        invoker="Vector DB",
                        recipient="Custom Agent",
                        event_type="received_skill_vector_response",
                        desc=f"Received {len(matched_skills)} matched skills",
                        payload={"results": matched_skills, "count": len(matched_skills)},
                        conv_id=conversation_id
                    )
            except Exception as e:
                pass
            
            steps.append({
                "component": "Skills",
                "icon": "⚡",
                "title": "Skills Vector Search",
                "description": f"Retrieved {len(matched_skills)} skills matching threshold {skill_threshold}",
                "elapsed_ms": int((time.time() - s_start) * 1000),
                "data": matched_skills
            })

        elif skill_selector == "Use AI Agent with Tools":
            # Ask LLM to pick appropriate skill
            steps.append({
                "component": "Skills",
                "icon": "⚡",
                "title": "LLM Skill Evaluation",
                "description": "Evaluating all available tools against user intent",
                "elapsed_ms": int((time.time() - s_start) * 1000)
            })
            matched_skills = [{"skill_name": "all_tools", "text": "All registered tools enabled"}]

        elif skill_selector.startswith("Skill:"):
            target_skill = skill_selector.replace("Skill:", "").strip()
            matched_skills = [{"skill_name": target_skill, "text": f"User explicitly selected skill {target_skill}"}]
            steps.append({
                "component": "Skills",
                "icon": "⚡",
                "title": "Manual Skill Selected",
                "description": f"Using skill: {target_skill}",
                "elapsed_ms": int((time.time() - s_start) * 1000)
            })

        # 2. Execution Loop
        turn = 0
        context_history = []
        final_answer = ""
        current_observation = ""

        # Limit to top 2 skills if multiple found
        active_skills = matched_skills[:2]

        while turn < max_turns:
            turn += 1
            loop_start = time.time()

            if not active_skills:
                # No skill found: direct assistant prompt
                sys_prompt = "You are a helpful, accurate AI assistant. Answer the user question clearly and concisely."
                user_prompt = f"{history_prompt}User Question: {message}"
                res_text, _, _, dur = self.call_llm(user_prompt, sys_prompt, model, temperature, max_tokens, custom_endpoint, conversation_id)
                final_answer = res_text
                steps.append({
                    "component": "LLM",
                    "icon": "🧠",
                    "title": "Direct Assistant Synthesis",
                    "description": f"Answered directly without tools ({dur}ms)",
                    "elapsed_ms": dur
                })
                break

            # Skills present: determine if tool should be executed
            skill_context_str = "\n\n".join([f"Skill: {s.get('skill_name', 'tool')}\n{s.get('text', '')}" for s in active_skills])
            system_prompt = (
                "You are an intelligent agent orchestrator with access to procedural tools.\n"
                "Review the user query and available skills. If you need more information or if a tool should be executed, "
                "respond ONLY with a JSON object specifying the tool and arguments. For example:\n"
                "{\n"
                '  "tool": "person_search.query_person_registry",\n'
                '  "arguments": {\n'
                '    "keywords": ["Lucas Dubois"],\n'
                '    "field": "name"\n'
                "  }\n"
                "}\n"
                "Available tools: \n"
                "- person_search.query_person_registry (arguments: keywords [list of texts or search string], field)\n"
                "- customer_search.query_customer_registry (arguments: keywords [list of texts or search string], field)\n"
                "- stock_search.query_stocks (arguments: action ['gainers', 'losers', 'quote'], limit, ticker)\n"
                "- time_weather.get_current_weather (arguments: city)\n"
                "- doc_search.query_documents (arguments: query, limit)\n\n"
                "If you already have enough information to answer the question completely, DO NOT output JSON. "
                "Instead, output your complete final answer to the user."
            )

            prompt_content = f"{history_prompt}User Query: {message}\n\nAvailable Skills:\n{skill_context_str}\n"
            if context_history:
                prompt_content += "\nPrevious Observations:\n" + "\n".join(context_history) + "\n"

            llm_res, in_tok, out_tok, dur_ms = self.call_llm(
                prompt_content, system_prompt, model, temperature, max_tokens, custom_endpoint, conversation_id
            )

            # Check if LLM outputted JSON tool call
            tool_call = None
            try:
                # Look for JSON block or JSON brackets
                json_match = re.search(r"\{[\s\S]*\"tool\"[\s\S]*\}", llm_res)
                if json_match:
                    tool_call = json.loads(json_match.group(0))
            except Exception:
                tool_call = None

            if tool_call and "tool" in tool_call and turn < max_turns:
                t_name = tool_call["tool"]
                t_args = tool_call.get("arguments", {})

                steps.append({
                    "component": "LLM",
                    "icon": "🧠",
                    "title": f"Turn {turn}: Tool Decision",
                    "description": f"Decided to invoke {t_name}",
                    "elapsed_ms": dur_ms,
                    "payload": tool_call
                })

                # Execute Tool
                t_start = time.time()
                tool_result = None

                if "doc" in t_name.lower():
                    # Query doc_RAG
                    try:
                        rag_url = self._resolve(self.doc_rag_url, "doc_rag", 8003)
                        doc_req = {
                            "db_type": "document",
                            "query": t_args.get("query", message),
                            "threshold": doc_threshold,
                            "limit": max_chunks,
                            "conversation_id": conversation_id,
                            "jwt_token": jwt_token,
                            "invoker": "Custom Agent"
                        }
                        self.log(
                            invoker="Custom Agent",
                            recipient="Vector DB",
                            event_type="document_vector_query",
                            desc=f"Query document vector DB: '{doc_req['query'][:80]}'",
                            payload=doc_req,
                            conv_id=conversation_id
                        )
                        headers = {"Content-Type": "application/json"}
                        if jwt_token:
                            headers["Authorization"] = f"Bearer {jwt_token}"
                        r = requests.post(f"{rag_url}/api/rag/query", json=doc_req, headers=headers, timeout=5)
                        tool_result = r.json()
                        if tool_result and isinstance(tool_result, dict):
                            doc_items = tool_result.get("results") or tool_result.get("matched_items") or []
                            doc_groups = {}
                            for item in doc_items:
                                meta = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
                                d_name = item.get("document_name") or meta.get("document_name") or item.get("name") or "Document"
                                score = round(float(item.get("similarity_score", 0)), 4) if item.get("similarity_score") is not None else 0.0
                                idx = meta.get("chunk_index", 0)
                                txt = item.get("chunk_text") or item.get("text") or ""
                                if d_name not in doc_groups:
                                    doc_groups[d_name] = {
                                        "doc_name": d_name,
                                        "highest_similarity": score,
                                        "chunks": []
                                    }
                                if score > doc_groups[d_name]["highest_similarity"]:
                                    doc_groups[d_name]["highest_similarity"] = score
                                if not any(c["index"] == idx and abs(c["similarity"] - score) < 1e-4 for c in doc_groups[d_name]["chunks"]):
                                    doc_groups[d_name]["chunks"].append({
                                        "index": idx,
                                        "similarity": score,
                                        "text": txt
                                    })
                            retrieved_evidence["documents"].extend(list(doc_groups.values()))
                        self.log(
                            invoker="Vector DB",
                            recipient="Custom Agent",
                            event_type="received_document_vector_response",
                            desc=f"Received document chunks from vector store",
                            payload=tool_result,
                            conv_id=conversation_id
                        )
                    except Exception as e:
                        tool_result = {"error": str(e)}
                    comp_name = "RAG"
                    comp_icon = "📚"
                else:
                    # Query Tools container
                    try:
                        tools_url = self._resolve(self.tools_url, "tools", 8005)
                        tool_req = {
                            "tool": t_name,
                            "arguments": t_args,
                            "conversation_id": conversation_id,
                            "jwt_token": jwt_token,
                            "invoker": "Custom Agent"
                        }
                        self.log(
                            invoker="Custom Agent",
                            recipient="tools",
                            event_type="tool_invocation",
                            desc=f"Invoking tool: {t_name}",
                            payload=tool_req,
                            conv_id=conversation_id
                        )
                        headers = {"Content-Type": "application/json"}
                        if jwt_token:
                            headers["Authorization"] = f"Bearer {jwt_token}"
                        r = requests.post(f"{tools_url}/api/tools/call", json=tool_req, headers=headers, timeout=8)
                        tool_result = r.json().get("result", {})
                        self.log(
                            invoker="tools",
                            recipient="Custom Agent",
                            event_type="tool_response",
                            desc=f"Received response from tool: {t_name}",
                            payload={"tool": t_name, "result": tool_result},
                            conv_id=conversation_id
                        )
                    except Exception as e:
                        tool_result = {"error": str(e)}
                    comp_name = "Tools"
                    comp_icon = "🔧"

                t_dur = int((time.time() - t_start) * 1000)
                obs_str = f"Observation from {t_name}: {json.dumps(tool_result)}"
                context_history.append(obs_str)

                steps.append({
                    "component": comp_name,
                    "icon": comp_icon,
                    "title": f"Executed {t_name}",
                    "description": f"Received result in {t_dur}ms",
                    "elapsed_ms": t_dur,
                    "result": tool_result
                })
            else:
                # LLM outputted final answer
                final_answer = llm_res
                steps.append({
                    "component": "LLM",
                    "icon": "🧠",
                    "title": f"Turn {turn}: Synthesis Complete",
                    "description": f"Generated final answer ({dur_ms}ms)",
                    "elapsed_ms": dur_ms
                })
                break

        # If loop reached max turns without breaking, make final call
        if not final_answer:
            final_sys = "You are a helpful assistant. Synthesize the final answer based on the collected context."
            final_p = f"{history_prompt}User Query: {message}\n\nInformation Collected:\n" + "\n".join(context_history)
            final_answer, _, _, dur_ms = self.call_llm(final_p, final_sys, model, temperature, max_tokens, custom_endpoint, conversation_id)
            steps.append({
                "component": "LLM",
                "icon": "🧠",
                "title": "Final Synthesis",
                "description": f"Completed turn limit response ({dur_ms}ms)",
                "elapsed_ms": dur_ms
            })

        total_elapsed = int((time.time() - agent_start) * 1000)

        # Log Final Response with FULL steps payload
        self.log(
            invoker="Custom Agent",
            recipient="Web UI",
            event_type="send_chat_response",
            desc=f"Agent response completed in {total_elapsed}ms",
            payload={
                "conversation_id": conversation_id,
                "user_query": message,
                "response": final_answer,
                "agent_type": "Custom Agent",
                "model": model,
                "elapsed_ms": total_elapsed,
                "steps": steps,
                "retrieved_evidence": retrieved_evidence
            },
            conv_id=conversation_id,
            dur_ms=total_elapsed,
            model=model
        )

        return {
            "conversation_id": conversation_id,
            "user_query": message,
            "response": final_answer,
            "agent_type": "Custom Agent",
            "model": model,
            "elapsed_ms": total_elapsed,
            "steps": steps,
            "retrieved_evidence": retrieved_evidence
        }
