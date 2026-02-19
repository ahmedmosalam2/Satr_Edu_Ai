import logging
from ..enums import LLMEnums
from ..LLMInference import LLMInference
from ..providers.OpenAI import OpenAIProvider

LLMProviderFactory:
    def __init__(self,config: dict):
        self.config=config
        self.logger=logging.getLogger(__name__)
        self.logger.info("LLMProviderFactory initialized")
    def create_provider(self,provider_type:LLMEnums.ProviderType)->LLMInference:
        if provider==LLMEnums.ProviderType.OPENAI:
            return OpenAIProvider(
                api_key=self.config.get("OPENAI_API_KEY"),
                api_url=self.config.get("OPENAI_API_URL"),
                default_input_max_charaters=get_settings().INPUT_DEFAULT_MAX_CHARACTERS,
                default_generation_max_output_tokens=get_settings().GENERATION_DEFAULT_MAX_OUTPUT_TOKENS,
                default_generation_temperature=get_settings().GENERATION_DEFAULT_TEMPERATURE,
                default_embedding_model_id=get_settings().EMBEDDING_MODEL_ID,
                default_embedding_model_size=get_settings().EMBEDDING_MODEL_SIZE
            )
        return None
        
