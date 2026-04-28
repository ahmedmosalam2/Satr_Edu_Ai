import asyncio
import inspect

from src.helpers.config import get_settings
from src.story.llm.LLMEnums import LLMEnums


class DummyTemplateParser:
    def get(self, domain, name, kwargs=None):
        if name == "system_prompt":
            return (
                "You are a smart and direct educational assistant. You must always follow these rules:\n"
                "1. Answer briefly and clearly – do not write more than the question requires.\n"
                "2. Speak in the user's language (Arabic if asked in Arabic, English if asked in English).\n"
                "3. Use only the information from the documents. If you don't find an answer, say so clearly.\n"
                "4. Do not repeat the question or give long introductions – start directly with the answer.\n"
                "5. If the question is simple, answer in one or two sentences only."
            )
        elif name == "document_prompt":
            kwargs = kwargs or {}
            return f"[Reference {kwargs.get('doc_num', '')}]: {kwargs.get('chunk_text', '')}"
        elif name == "footer_prompt":
            kwargs = kwargs or {}
            return (
                f"Based only on the above references, answer this question briefly:\n"
                f"Question: {kwargs.get('query', '')}\n\n"
                f"Direct answer:"
            )
        return ""


class LLMWrapper:
    """Wraps any LLM provider to expose embed_text / generate_text / construct_prompt."""

    def __init__(self, provider):
        self.provider = provider
        # Use OpenAiEnums because role strings (system/user/assistant) are universal across all providers we use
        self.enums = LLMEnums.OpenAiEnums

    @property
    def embedding_size(self):
        return getattr(self.provider, 'embedding_size', None)

    def process_text(self, text):
        return self.provider.process_text(text)

    async def _call_maybe_async(self, fn, *args, **kwargs):
        """
        Support both async providers (e.g. Cohere) and sync providers
        (e.g. Ollama/OpenAI) without incorrectly awaiting plain return values.
        """
        if inspect.iscoroutinefunction(fn):
            return await fn(*args, **kwargs)

        result = await asyncio.to_thread(fn, *args, **kwargs)
        if inspect.isawaitable(result):
            return await result
        return result

    async def embed_text(self, text, document_type=None):
        """
        Always returns a list of vectors (1 per input text).
        - If text is a str  -> returns [vector]
        - If text is a list -> returns [vector1, vector2, ...]
        """
        result = await self._call_maybe_async(
            self.provider.embed_text,
            text,
            document_type,
        )

        if result is None:
            return None

        # Normalize output to always be a 2D list (list of vectors)
        # Ollama /api/embed returns [[...], ...] — already 2D
        # Ollama /api/embeddings returns [[...]] wrapped — already handled
        # Cohere returns [[...], ...] for list or [...]  for single string
        if isinstance(result, list):
            # Check if it's already 2D (list of lists)
            if result and isinstance(result[0], list):
                return result  # Already [[vec1], [vec2], ...]
            else:
                # It's a flat 1D vector — wrap it
                return [result]

        return [result]

    async def generate_text(self, prompt, chat_history=None, max_tokens: int = None, temperature: float = None):
        if hasattr(self.provider, "generate_text"):
            return await self._call_maybe_async(
                self.provider.generate_text,
                prompt,
                chat_history=chat_history,
                max_tokens=max_tokens,
                temperature=temperature,
            )
        return await self._call_maybe_async(
            self.provider.generate_story,
            prompt,
            chat_history=chat_history,
            max_tokens=max_tokens,
            temperature=temperature,
        )

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
    elif backend == "GEMINI":
        provider = factory.create_provider(LLMEnums.ProviderType.GEMINI)
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
