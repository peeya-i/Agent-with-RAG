import os
import json
import logging

logger = logging.getLogger("mem0_config")

DEFAULT_CHAT_CONFIG = {
    "temperature": 0.7,
    "max_tokens": 2048,
    "model": "gemma-4-26b-a4b-it",
    "agent": "Custom Agent",
    "max_turns": 5,
    "rag_chunks": 5,
    "doc_threshold": 0.3,
    "skill_mode": "Vector Store Selects",
    "skill_threshold": 0.2,
    "custom_endpoint": None
}

class Mem0ChatConfigStore:
    """Manages per-user chat configuration preferences using mem0.
    Stores and retrieves user-customized settings:
    - Temperature
    - Max Tokens
    - Model Choice
    - Custom Endpoint
    - Agent Choice
    - Max Turns
    - RAG Chunks
    - Doc Threshold
    - Skill Selector Mode
    - Skill Threshold
    """
    def __init__(self, storage_dir=None):
        if storage_dir is None:
            secrets_dir = os.environ.get("SECRETS_DIR", os.path.join(os.path.dirname(__file__), "secrets"))
            storage_dir = os.path.join(secrets_dir, "mem0")
        
        self.storage_dir = storage_dir
        os.makedirs(self.storage_dir, exist_ok=True)
        self.json_backup_path = os.path.join(self.storage_dir, "user_chat_configs.json")
        self.memory = None
        self._init_mem0()

    def _init_mem0(self):
        try:
            from mem0 import Memory
            qdrant_path = os.path.join(self.storage_dir, "qdrant")
            os.makedirs(qdrant_path, exist_ok=True)
            api_key = os.environ.get("GEMINI_API_KEY", "")

            # If Gemini API key is available, use Gemini LLM & Gemini Embeddings
            # Otherwise, use mock/fallback or local embedder
            cfg = {
                "vector_store": {
                    "provider": "qdrant",
                    "config": {
                        "path": qdrant_path,
                        "embedding_model_dims": 3072,
                    }
                },
                "llm": {
                    "provider": "gemini",
                    "config": {
                        "model": "gemini-3.8-flash",
                        "api_key": api_key
                    }
                },
                "embedder": {
                    "provider": "gemini",
                    "config": {
                        "model": "gemini-embedding-001",
                        "embedding_dims": 3072,
                        "api_key": api_key
                    }
                }
            }
            self.memory = Memory.from_config(cfg)
            logger.info("mem0 Memory initialized successfully for chat configuration store")
        except Exception as e:
            logger.warning(f"mem0 Memory initialization note (falling back to JSON store): {e}")
            self.memory = None

    def _clean_user_id(self, user_id):
        if not user_id:
            return "default_user"
        return str(user_id).strip().lower()

    def save_config(self, user_id: str, config: dict) -> dict:
        uid = self._clean_user_id(user_id)
        clean = {
            "temperature": float(config.get("temperature", DEFAULT_CHAT_CONFIG["temperature"])),
            "max_tokens": int(config.get("max_tokens", DEFAULT_CHAT_CONFIG["max_tokens"])),
            "model": str(config.get("model", DEFAULT_CHAT_CONFIG["model"])),
            "agent": str(config.get("agent", DEFAULT_CHAT_CONFIG["agent"])),
            "max_turns": int(config.get("max_turns", DEFAULT_CHAT_CONFIG["max_turns"])),
            "rag_chunks": int(config.get("rag_chunks", DEFAULT_CHAT_CONFIG["rag_chunks"])),
            "doc_threshold": float(config.get("doc_threshold", DEFAULT_CHAT_CONFIG["doc_threshold"])),
            "skill_mode": str(config.get("skill_mode", DEFAULT_CHAT_CONFIG["skill_mode"])),
            "skill_threshold": float(config.get("skill_threshold", DEFAULT_CHAT_CONFIG["skill_threshold"])),
            "custom_endpoint": config.get("custom_endpoint") or None
        }

        # 1. Store in mem0
        if self.memory:
            try:
                # Remove prior chat configuration memories for this user
                try:
                    prior = self.memory.get_all(filters={"user_id": uid})
                    for item in prior.get("results", []):
                        if isinstance(item, dict) and "id" in item:
                            self.memory.delete(item["id"])
                except Exception:
                    pass

                prompt = (
                    f"User {uid} preferred chat configuration: "
                    f"model='{clean['model']}', temperature={clean['temperature']}, "
                    f"max_tokens={clean['max_tokens']}, agent='{clean['agent']}', "
                    f"max_turns={clean['max_turns']}, rag_chunks={clean['rag_chunks']}, "
                    f"doc_threshold={clean['doc_threshold']}, skill_mode='{clean['skill_mode']}', "
                    f"skill_threshold={clean['skill_threshold']}"
                )
                self.memory.add(prompt, user_id=uid, metadata=clean, infer=False)
            except Exception as e:
                logger.warning(f"Error persisting to mem0 for user {uid}: {e}")

        # 2. Store in JSON backup
        data = {}
        if os.path.exists(self.json_backup_path):
            try:
                with open(self.json_backup_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                pass
        data[uid] = clean
        try:
            with open(self.json_backup_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.warning(f"Error writing json backup for {uid}: {e}")

        return clean

    def get_config(self, user_id: str) -> dict:
        uid = self._clean_user_id(user_id)
        # 1. Try mem0 retrieval
        if self.memory:
            try:
                mems = self.memory.get_all(filters={"user_id": uid})
                results = mems.get("results", [])
                if results and isinstance(results[0], dict) and "metadata" in results[0]:
                    meta = results[0]["metadata"]
                    merged = dict(DEFAULT_CHAT_CONFIG)
                    merged.update(meta)
                    return merged
            except Exception as e:
                logger.warning(f"Error fetching from mem0 for user {uid}: {e}")

        # 2. Try JSON backup
        if os.path.exists(self.json_backup_path):
            try:
                with open(self.json_backup_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if uid in data:
                        merged = dict(DEFAULT_CHAT_CONFIG)
                        merged.update(data[uid])
                        return merged
            except Exception:
                pass

        return dict(DEFAULT_CHAT_CONFIG)

    def reset_config(self, user_id: str) -> dict:
        uid = self._clean_user_id(user_id)
        if self.memory:
            try:
                prior = self.memory.get_all(filters={"user_id": uid})
                for item in prior.get("results", []):
                    if isinstance(item, dict) and "id" in item:
                        self.memory.delete(item["id"])
            except Exception:
                pass

        if os.path.exists(self.json_backup_path):
            try:
                with open(self.json_backup_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if uid in data:
                    del data[uid]
                    with open(self.json_backup_path, "w", encoding="utf-8") as f:
                        json.dump(data, f, indent=2)
            except Exception:
                pass

        return dict(DEFAULT_CHAT_CONFIG)

# Global singleton instance
chat_config_store = Mem0ChatConfigStore()
