from src.helpers.config import get_settings
from src.story.llm.LLMEnums import LLMEnums


class DummyTemplateParser:
    def get(self, domain, name, kwargs=None):
        if name == "system_prompt":
            return "You are a helpful assistant."
        elif name == "document_prompt":
            kwargs = kwargs or {}
            return f"Document {kwargs.get('doc_num', '')}:\n{kwargs.get('chunk_text', '')}"
        elif name == "footer_prompt":
            kwargs = kwargs or {}
            return f"Answer the query: {kwargs.get('query', '')}"
        return ""


class LLMWrapper:
    """Wraps any LLM provider to expose embed_text / generate_text / construct_prompt."""

    def __init__(self, provider):
        self.provider = provider
        self.enums = getattr(LLMEnums, 'OpenAiEnums', None)

    @property
    def embedding_size(self):
        return getattr(self.provider, 'embedding_size', None)

    def process_text(self, text):
        return self.provider.process_text(text)

    def embed_text(self, text, document_type=None):
        # Cohere provider has its own embed_text
        if hasattr(self.provider, "embed_text"):
            if isinstance(text, list):
                return self.provider.embed_text(text, document_type)
            return self.provider.embed_text(text, document_type)
        # OpenAI: generate_embedding works per-text
        if isinstance(text, list):
            return [self.provider.generate_embedding(t) for t in text]
        return [self.provider.generate_embedding(text)]

    def generate_text(self, prompt, chat_history=None):
        if hasattr(self.provider, "generate_text"):
            return self.provider.generate_text(prompt, chat_history=chat_history)
        return self.provider.generate_story(prompt, chat_history=chat_history)

    def construct_prompt(self, prompt, role):
        return self.provider.construct_prompt(prompt, role)


def get_embedding_client():
    """Returns a wrapped embedding client based on EMBEDDING_BACKEND in settings."""
    settings = get_settings()
    from src.story.llm.LLMproviderfactory import LLMProviderFactory
    factory = LLMProviderFactory(settings)

    backend = settings.EMBEDDING_BACKEND.upper()
    if backend == "COHERE":
        provider = factory.create_provider(LLMEnums.ProviderType.COHERE)
    elif backend == "OLLAMA":
        provider = factory.create_provider(LLMEnums.ProviderType.OLLAMA)
    else:  # default: OPENAI
        provider = factory.create_provider(LLMEnums.ProviderType.OPENAI)

    provider.set_embedding_model(settings.EMBEDDING_MODEL_ID, settings.EMBEDDING_MODEL_SIZE)
    return LLMWrapper(provider)


def get_generation_client():
    """Returns a wrapped generation client based on GENERATION_BACKEND in settings."""
    settings = get_settings()
    from src.story.llm.LLMproviderfactory import LLMProviderFactory
    factory = LLMProviderFactory(settings)

    backend = settings.GENERATION_BACKEND.upper()
    if backend == "OLLAMA":
        provider = factory.create_provider(LLMEnums.ProviderType.OLLAMA)
    elif backend == "COHERE":
        provider = factory.create_provider(LLMEnums.ProviderType.COHERE)
    else:  # default: OPENAI
        provider = factory.create_provider(LLMEnums.ProviderType.OPENAI)

    provider.set_generate_model(settings.GENERATION_MODEL_ID)
    return LLMWrapper(provider)


def get_vectordb_client():
    settings = get_settings()
    from src.story.vectordb.VectorDBProviderFactory import VectorDBProviderFactory
    factory = VectorDBProviderFactory(settings)
    return factory.create(settings.VECTOR_DB_BACKEND)


template_parser = DummyTemplateParser()
