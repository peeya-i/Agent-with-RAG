"""LLM service connecting to Google AI Studio and Custom OpenAI-compatible endpoints."""
import json
import time
from typing import Dict, Any, List, Optional
import requests
from google import genai
from google.genai import types
import config
from services.log_service import get_log_service
from services.telemetry_service import get_telemetry_service

class LLMService:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or config.GEMINI_API_KEY
        self.client = genai.Client(api_key=self.api_key) if self.api_key else None
        self.logger = get_log_service()
        self.telemetry = get_telemetry_service()
        self._cached_models: Optional[List[Dict[str, Any]]] = None

    def get_active_models(self, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """Fetch list of ONLY active LLM models capable of text generation (generateContent)."""
        if self._cached_models and not force_refresh:
            return self._cached_models

        models_list: List[Dict[str, Any]] = []
        if self.client:
            try:
                raw_models = self.client.models.list()
                for m in raw_models:
                    supported = getattr(m, "supported_actions", []) or []
                    if "generateContent" in supported:
                        name = m.name
                        if name.startswith("models/"):
                            name = name[len("models/"):]
                        
                        out_limit = getattr(m, "output_token_limit", 4096) or 4096
                        in_limit = getattr(m, "input_token_limit", 32768) or 32768
                        
                        models_list.append({
                            "id": name,
                            "display_name": getattr(m, "display_name", name) or name,
                            "output_token_limit": out_limit,
                            "input_token_limit": in_limit,
                            "description": getattr(m, "description", "") or "",
                        })
            except Exception as e:
                print(f"[LLMService] Failed to list models from Google AI Studio: {e}")

        # Ensure DEFAULT_LLM_MODEL is included
        found_default = False
        for item in models_list:
            if item["id"] == config.DEFAULT_LLM_MODEL:
                found_default = True
                break
        
        if not found_default:
            models_list.insert(0, {
                "id": config.DEFAULT_LLM_MODEL,
                "display_name": config.DEFAULT_LLM_MODEL,
                "output_token_limit": 32768,
                "input_token_limit": 262144,
                "description": "Google Gemma 4 26B instruction-tuned model",
            })

        # Put default model at top of list
        models_list.sort(key=lambda x: 0 if x["id"] == config.DEFAULT_LLM_MODEL else 1)
        self._cached_models = models_list
        return models_list

    def get_model_max_tokens(self, model_id: str) -> int:
        """Return maximum output tokens allowed for model."""
        models = self.get_active_models()
        for m in models:
            if m["id"] == model_id:
                return m.get("output_token_limit", 4096)
        return 4096

    def generate_text(
        self,
        prompt: str,
        model: str = config.DEFAULT_LLM_MODEL,
        system_instruction: Optional[str] = None,
        temperature: float = config.DEFAULT_TEMPERATURE,
        max_tokens: Optional[int] = None,
        custom_endpoint: Optional[str] = None,
        conversation_id: str = "system",
        invoker: str = "Custom Agent",
    ) -> Dict[str, Any]:
        """Send prompt to LLM and log full request & response payloads per specification."""
        start_time = time.time()
        max_tok = max_tokens or config.DEFAULT_MAX_TOKENS

        # Log LLM Invocation request with FULL payload
        req_payload = {
            "model": model,
            "prompt": prompt,
            "system_instruction": system_instruction,
            "temperature": temperature,
            "max_tokens": max_tok,
            "custom_endpoint": custom_endpoint,
        }

        self.logger.log_event(
            conversation_id=conversation_id,
            event_type="LLM",
            invoker=invoker,
            target=f"Model: {model}",
            short_description=f"Prompt sent to {model} ({len(prompt)} chars)",
            payload=req_payload,
        )

        # Dispatch call
        if custom_endpoint and custom_endpoint.strip():
            return self._call_custom_endpoint(
                endpoint=custom_endpoint.strip(),
                model=model,
                prompt=prompt,
                system_instruction=system_instruction,
                temperature=temperature,
                max_tokens=max_tok,
                conversation_id=conversation_id,
                start_time=start_time,
                invoker=invoker,
            )
        else:
            return self._call_google_genai(
                model=model,
                prompt=prompt,
                system_instruction=system_instruction,
                temperature=temperature,
                max_tokens=max_tok,
                conversation_id=conversation_id,
                start_time=start_time,
                invoker=invoker,
            )

    def _call_google_genai(
        self,
        model: str,
        prompt: str,
        system_instruction: Optional[str],
        temperature: float,
        max_tokens: int,
        conversation_id: str,
        start_time: float,
        invoker: str,
    ) -> Dict[str, Any]:
        if not self.client:
            raise RuntimeError("Google GenAI client is not initialized. Check GEMINI_API_KEY.")

        try:
            # Build configuration
            gen_config = types.GenerateContentConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
                system_instruction=system_instruction if system_instruction else None,
            )

            response = self.client.models.generate_content(
                model=model,
                contents=prompt,
                config=gen_config,
            )
            elapsed_ms = (time.time() - start_time) * 1000

            resp_text = response.text or ""
            
            # Extract usage metadata
            usage = getattr(response, "usage_metadata", None)
            input_tokens = getattr(usage, "prompt_token_count", len(prompt.split()) * 2) or 0
            output_tokens = getattr(usage, "candidates_token_count", len(resp_text.split()) * 2) or 0

            resp_payload = {
                "response_text": resp_text,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "finish_reason": str(getattr(response.candidates[0], "finish_reason", "STOP")) if response.candidates else "STOP",
                "raw_response": str(response),
            }

            # Log LLM Response with FULL payload
            self.logger.log_event(
                conversation_id=conversation_id,
                event_type="LLM",
                invoker=f"Model: {model}",
                target=invoker,
                short_description=f"Response received from {model} ({output_tokens} tokens)",
                payload=resp_payload,
                elapsed_ms=elapsed_ms,
            )

            # Record Telemetry
            self.telemetry.record_invocation(
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                elapsed_ms=elapsed_ms,
                is_error=False,
            )

            return {
                "text": resp_text,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "elapsed_ms": elapsed_ms,
                "model": model,
                "status": "success",
            }

        except Exception as e:
            elapsed_ms = (time.time() - start_time) * 1000
            err_payload = {"error": str(e), "model": model}
            self.logger.log_event(
                conversation_id=conversation_id,
                event_type="LLM",
                invoker=f"Model: {model}",
                target=invoker,
                short_description=f"Model call failed: {str(e)}",
                payload=err_payload,
                elapsed_ms=elapsed_ms,
                is_error=True,
            )

            self.telemetry.record_invocation(
                model=model,
                input_tokens=len(prompt.split()),
                output_tokens=0,
                elapsed_ms=elapsed_ms,
                is_error=True,
            )
            raise

    def _call_custom_endpoint(
        self,
        endpoint: str,
        model: str,
        prompt: str,
        system_instruction: Optional[str],
        temperature: float,
        max_tokens: int,
        conversation_id: str,
        start_time: float,
        invoker: str,
    ) -> Dict[str, Any]:
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        try:
            resp = requests.post(endpoint, json=payload, timeout=60)
            elapsed_ms = (time.time() - start_time) * 1000
            
            if resp.status_code == 200:
                data = resp.json()
                choice = data.get("choices", [{}])[0]
                resp_text = choice.get("message", {}).get("content", "")
                usage = data.get("usage", {})
                in_tok = usage.get("prompt_tokens", len(prompt.split()))
                out_tok = usage.get("completion_tokens", len(resp_text.split()))

                resp_payload = {
                    "response_text": resp_text,
                    "input_tokens": in_tok,
                    "output_tokens": out_tok,
                    "raw_json": data,
                }

                self.logger.log_event(
                    conversation_id=conversation_id,
                    event_type="LLM",
                    invoker=f"Custom Endpoint ({endpoint})",
                    target=invoker,
                    short_description=f"Response from custom endpoint ({out_tok} tokens)",
                    payload=resp_payload,
                    elapsed_ms=elapsed_ms,
                )

                self.telemetry.record_invocation(
                    model="custom_model",
                    input_tokens=in_tok,
                    output_tokens=out_tok,
                    elapsed_ms=elapsed_ms,
                    is_error=False,
                )

                return {
                    "text": resp_text,
                    "input_tokens": in_tok,
                    "output_tokens": out_tok,
                    "elapsed_ms": elapsed_ms,
                    "model": "custom_model",
                    "status": "success",
                }
            else:
                elapsed_ms = (time.time() - start_time) * 1000
                self.logger.log_event(
                    conversation_id=conversation_id,
                    event_type="LLM",
                    invoker=f"Custom Endpoint ({endpoint})",
                    target=invoker,
                    short_description=f"Custom endpoint failed with HTTP {resp.status_code}",
                    payload={"status_code": resp.status_code, "body": resp.text},
                    elapsed_ms=elapsed_ms,
                    is_error=True,
                )
                self.telemetry.record_invocation(
                    model="custom_model",
                    input_tokens=len(prompt.split()),
                    output_tokens=0,
                    elapsed_ms=elapsed_ms,
                    is_error=True,
                )
                raise RuntimeError(f"Custom endpoint returned HTTP {resp.status_code}: {resp.text}")

        except Exception as e:
            elapsed_ms = (time.time() - start_time) * 1000
            self.logger.log_event(
                conversation_id=conversation_id,
                event_type="LLM",
                invoker=f"Custom Endpoint ({endpoint})",
                target=invoker,
                short_description=f"Custom endpoint request failed: {str(e)}",
                payload={"error": str(e)},
                elapsed_ms=elapsed_ms,
                is_error=True,
            )
            self.telemetry.record_invocation(
                model="custom_model",
                input_tokens=len(prompt.split()),
                output_tokens=0,
                elapsed_ms=elapsed_ms,
                is_error=True,
            )
            raise

# Singleton instance
_LLM_SERVICE: Optional[LLMService] = None

def get_llm_service() -> LLMService:
    global _LLM_SERVICE
    if _LLM_SERVICE is None:
        _LLM_SERVICE = LLMService()
    return _LLM_SERVICE
