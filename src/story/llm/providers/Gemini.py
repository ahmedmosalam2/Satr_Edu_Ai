import logging
import google.generativeai as genai
from src.story.llm.LLMinfernce import LLMInference
from src.story.llm.LLMEnums import LLMEnums


class GeminiProvider(LLMInference):
    """Google Gemini provider for text generation."""

    def __init__(self, api_key: str,
                 default_input_max_characters: int = 4000,
                 default_generation_max_output_tokens: int = 1000,
                 default_generation_temperature: float = 0.1):

        self.api_key = api_key
        self.default_input_max_characters = default_input_max_characters
        self.default_generation_max_output_tokens = default_generation_max_output_tokens
        self.default_generation_temperature = default_generation_temperature

        self.generation_model_id = None
        self.embedding_model_id = None
        self.embedding_size = None

        genai.configure(api_key=api_key)
        self.logger = logging.getLogger(__name__)

    def set_generate_model(self, model_id: str):
        self.generation_model_id = model_id

    def set_embedding_model(self, model_id: str, embedding_size: int):
        self.embedding_model_id = model_id
        self.embedding_size = embedding_size

    def process_text(self, text: str):
        return text[:self.default_input_max_characters].strip()

    def generate_text(self, prompt: str, max_tokens: int = None,
                      temperature: float = None, chat_history: list = None) -> str:
        if not self.generation_model_id:
            self.logger.error("Gemini: generation model not set")
            return None

        max_tokens = max_tokens or self.default_generation_max_output_tokens
        temperature = temperature if temperature is not None else self.default_generation_temperature

        # Build system instruction from history (if any)
        system_instruction = None
        messages_for_gemini = []

        if chat_history:
            for msg in chat_history:
                role = msg.get("role", "")
                content = msg.get("content", "")
                if role == LLMEnums.OpenAiEnums.SYSTEM.value:
                    system_instruction = content
                elif role == LLMEnums.OpenAiEnums.USER.value:
                    messages_for_gemini.append({"role": "user", "parts": [content]})
                elif role == LLMEnums.OpenAiEnums.ASSISTANT.value:
                    messages_for_gemini.append({"role": "model", "parts": [content]})

        try:
            model = genai.GenerativeModel(
                model_name=self.generation_model_id,
                system_instruction=system_instruction,
                generation_config=genai.GenerationConfig(
                    max_output_tokens=max_tokens,
                    temperature=temperature,
                )
            )

            if messages_for_gemini:
                # Multi-turn conversation
                chat = model.start_chat(history=messages_for_gemini)
                response = chat.send_message(prompt)
            else:
                response = model.generate_content(prompt)

            return response.text

        except Exception as e:
            self.logger.error(f"Gemini generation error: {e}")
            return None

    # Alias for compatibility
    def generate_story(self, prompt: str, max_tokens: int = None,
                       temperature: float = None, chat_history: list = None) -> str:
        return self.generate_text(prompt, max_tokens, temperature, chat_history)

    def stream_generate_text(self, prompt: str):
        raise NotImplementedError("Streaming not yet implemented for Gemini provider")

    def embed_text(self, text, document_type=None):
        """Embed text using Gemini embedding model."""
        if not self.embedding_model_id:
            self.logger.error("Gemini: embedding model not set")
            return None
        try:
            task_type = "retrieval_document" if document_type == LLMEnums.DocumentTypeEnum.DOCUMENT.value else "retrieval_query"
            if isinstance(text, list):
                results = []
                for t in text:
                    r = genai.embed_content(
                        model=self.embedding_model_id,
                        content=t,
                        task_type=task_type,
                    )
                    results.append(r["embedding"])
                return results
            else:
                r = genai.embed_content(
                    model=self.embedding_model_id,
                    content=text,
                    task_type=task_type,
                )
                return [r["embedding"]]
        except Exception as e:
            self.logger.error(f"Gemini embedding error: {e}")
            return None

    def generate_embedding(self, text: str):
        result = self.embed_text(text)
        return result[0] if result else None

    def construct_prompt(self, prompt: str, role: str):
        return {
            "role": role,
            "content": self.process_text(prompt)
        }
