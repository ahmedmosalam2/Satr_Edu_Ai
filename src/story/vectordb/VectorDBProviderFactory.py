from src.story.vectordb.provider.Qdrant import Qdrant
from src.story.vectordb.VectorEnums import VectorEnums


class VectorDBProviderFactory:
    def __init__(self, config):
        self.config = config

    def create(self, provider: str = None):
        backend = provider or self.config.VECTOR_DB_BACKEND

        if backend.upper() == VectorEnums.QDRANT.value.upper():
            return Qdrant(
                db_path=self.config.VECTOR_DB_PATH,
                distance_method=self.config.VECTOR_DB_DISTANCE_METHOD,
            )
        raise ValueError(f"Unknown vector DB provider: {backend}")
