import logging
from src.story.llm.LLMEnums import LLMEnums
from src.story.llm.LLMinfernce import LLMInference
from src.story.llm.providers.OpenAI import OpenAIProvider
from src.helpers.config import get_settings

class LLMProviderFactory:
    def __init__(self,config: dict):
        self.config=config
        self.logger=logging.getLogger(__name__)
        self.logger.info("LLMProviderFactory initialized")
    def create_provider(self,provider_type:LLMEnums.ProviderType)->LLMInference:
        if provider_type==LLMEnums.ProviderType.OPENAI:
            return OpenAIProvider(
                api_key=self.config.OPENAI_API_KEY,
                api_url=self.config.OPENAI_API_URL,
                default_input_max_characters=self.config.INPUT_DAFAULT_MAX_CHARACTERS,
                default_generation_max_output_tokens=self.config.GENERATION_DAFAULT_MAX_TOKENS,
                default_generation_temperature=self.config.GENERATION_DAFAULT_TEMPERATURE
            )
        return None
 
