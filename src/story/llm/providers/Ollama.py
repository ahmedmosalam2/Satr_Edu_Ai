import logging
from ..LLMResponse import LLMResponse
from ..LLMEnums import LLMEnums
from ..LLMInference import LLMInference
from ollama import Ollama

class OllamaProvider(LLMInference):
    def __init__(self, default_input_max_characters=1000,
                 default_generation_max_output_tokens=1000,
                 default_generation_temperature=0.7):
        self.default_input_max_characters = default_input_max_characters
        self.default_generation_max_output_tokens = default_generation_max_output_tokens
        self.default_generation_temperature = default_generation_temperature
        self.generate_model = None
        self.client = Ollama()
        self.logger = logging.getLogger(__name__)

    def set_generate_model(self, model_id: str):
        self.generate_model = model_id

    def generate_text(self, prompt: str, max_tokens: int=None, temperature: float=None):
        if not self.client:
            self.logger.error("Ollama client is not initialized")
            return None
        if not self.generate_model:
            self.logger.error("generate model is not initialized")
            return None

        max_tokens = max_tokens if max_tokens else self.default_generation_max_output_tokens
        temperature = temperature if temperature else self.default_generation_temperature

        response = self.client.chat(
            model=self.generate_model,
            prompt=prompt,
            max_tokens=max_tokens,
            temperature=temperature
        )

        return LLMResponse(
            text=response.text,
            model=self.generate_model,
            prompt_tokens=0,  # Ollama local لا يعطي usage tokens
            completion_tokens=0,
            total_tokens=0
        )

    def construct_prompt(self,prompt:str,role:str):
        return {
            "role":role,
            "content":prompt
        }
    def stream_generate_text(self,prompt:str):
        stream=self.client.chat.completions.create(
            model=self.generate_model,
            messages=self.construct_prompt(prompt=prompt,role=LLMEnums.OpenAiEnums.USER.value),
            stream=True
            )
        for chunk in stream:
            yield chunk.choices[0].delta.content