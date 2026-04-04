import logging
import requests
from src.story.llm.LLMinfernce import LLMInference


class OllamaProvider(LLMInference):
    """
    Ollama local LLM provider - free, runs on your machine.
    Supports text generation (/api/chat) and embeddings (/api/embeddings).
    """

    def __init__(self, base_url: str = "http://localhost:11434",
                 default_input_max_characters: int = 1000,
                 default_generation_max_output_tokens: int = 1000,
                 default_generation_temperature: float = 0.1):

        self.base_url = base_url.rstrip("/")
        self.default_input_max_characters = default_input_max_characters
        self.default_generation_max_output_tokens = default_generation_max_output_tokens
        self.default_generation_temperature = default_generation_temperature

        self.generation_model_id = None
        self.embedding_model_id = None
        self.embedding_size = None

        self.logger = logging.getLogger(__name__)

    # ─── Required by LLMInference abstract class ───────────────────────────────

    def set_generate_model(self, model_id: str):
        self.generation_model_id = model_id

    def set_embedding_model(self, model_id: str, embedding_size: int = None):
        self.embedding_model_id = model_id
        self.embedding_size = embedding_size

    def process_text(self, text: str) -> str:
        return text[:self.default_input_max_characters].strip()

    def construct_prompt(self, prompt: str, role: str) -> dict:
        return {"role": role, "content": self.process_text(prompt)}

    def generate_story(self, prompt: str, max_tokens: int = None,
                       temperature: float = None, chat_history: list = None) -> str:
        """Alias for generate_text - required by LLMInference."""
        return self.generate_text(prompt, chat_history=chat_history,
                                  max_tokens=max_tokens, temperature=temperature)

    def stream_generate_text(self, prompt: str):
        raise NotImplementedError("Streaming not yet implemented for Ollama")

    # ─── Generation ────────────────────────────────────────────────────────────

    def generate_text(self, prompt: str, chat_history: list = None,
                      max_tokens: int = None, temperature: float = None) -> str:
        if not self.generation_model_id:
            self.logger.error("Ollama: generation model not set")
            return None

        messages = list(chat_history or [])
        # \u0646\u0628\u0639\u062a \u0627\u0644\u0640 prompt \u0643\u0627\u0645\u0644\u0627\u064b \u2014 \u0627\u0644\u062a\u0642\u0637\u064a\u0639 \u0628\u064a\u0643\u0648\u0646 \u0641\u0642\u0637 \u0641\u064a \u0627\u0644\u0640 RAG chunk previews \u0639\u0628\u0631 process_text()
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.generation_model_id,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature or self.default_generation_temperature,
                "num_predict": max_tokens or self.default_generation_max_output_tokens,
            }
        }

        try:
            resp = requests.post(f"{self.base_url}/api/chat", json=payload, timeout=120)
            resp.raise_for_status()
            return resp.json().get("message", {}).get("content", None)
        except Exception as e:
            self.logger.error(f"Ollama generation error: {e}")
            return None

    # ─── Embedding ─────────────────────────────────────────────────────────────

    def generate_embedding(self, text: str) -> list:
        if not self.embedding_model_id:
            self.logger.error("Ollama: embedding model not set")
            return None
        # Try new API first (/api/embed), then fall back to old (/api/embeddings)
        for endpoint, key in [("/api/embed", "embeddings"), ("/api/embeddings", "embedding")]:
            try:
                payload = {"model": self.embedding_model_id}
                if endpoint == "/api/embed":
                    payload["input"] = self.process_text(text)
                else:
                    payload["prompt"] = self.process_text(text)
                resp = requests.post(f"{self.base_url}{endpoint}", json=payload, timeout=60)
                if resp.status_code == 200:
                    data = resp.json()
                    result = data.get(key)
                    if result:
                        # /api/embed returns list of embeddings, take first
                        if isinstance(result, list) and isinstance(result[0], list):
                            return result[0]
                        return result
            except Exception as e:
                self.logger.warning(f"Ollama {endpoint} failed: {e}")
        self.logger.error(f"Ollama: all embedding endpoints failed for model '{self.embedding_model_id}'. "
                          f"Run: ollama pull {self.embedding_model_id}")
        return None

    def embed_text(self, text, document_type=None):
        """Supports both single string and list of strings."""
        if isinstance(text, list):
            return [self.generate_embedding(t) for t in text]
        return [self.generate_embedding(text)]