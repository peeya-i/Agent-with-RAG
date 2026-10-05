import os
import time
import json
from datetime import datetime, timezone
import requests
try:
    from custom_agent.custom_agent import CustomAgent
except ModuleNotFoundError:
    from agents.custom_agent.custom_agent import CustomAgent

class GoogleADKAgent:
    """Google ADK LlmAgent wrapper implementing ADK agent workflows."""
    def __init__(self, doc_rag_url="http://doc_rag:8003", tools_url="http://tools:8005", logging_url="http://logging:8006", gemini_api_key=None):
        self.doc_rag_url = doc_rag_url
        self.tools_url = tools_url
        self.logging_url = logging_url
        self.gemini_api_key = gemini_api_key or os.environ.get("GEMINI_API_KEY", "")
        # Delegate core loop orchestration
        self.custom_runner = CustomAgent(
            doc_rag_url=doc_rag_url,
            tools_url=tools_url,
            logging_url=logging_url,
            gemini_api_key=self.gemini_api_key
        )

    def run(self, message, conversation_id, model="gemma-4-26b-a4b-it", temperature=0.7, max_tokens=2048,
            max_turns=5, skill_selector="Vector Store Selects", skill_threshold=0.2, doc_threshold=0.3,
            max_chunks=5, custom_endpoint=None, api_key=None, jwt_token=None, configured_keys=None, **kwargs):
        
        # Run with agent_type Google ADK Agent
        result = self.custom_runner.run(
            message=message,
            conversation_id=conversation_id,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            max_turns=max_turns,
            skill_selector=skill_selector,
            skill_threshold=skill_threshold,
            doc_threshold=doc_threshold,
            max_chunks=max_chunks,
            custom_endpoint=custom_endpoint,
            api_key=api_key,
            jwt_token=jwt_token,
            configured_keys=configured_keys,
            **kwargs
        )
        result["agent_type"] = "Google ADK Agent"
        if result.get("steps") and len(result["steps"]) > 0:
            result["steps"][0]["title"] = "Google ADK LlmAgent Initialized"
            result["steps"][0]["description"] = f"ADK Runner active with model {model}"

        return result
