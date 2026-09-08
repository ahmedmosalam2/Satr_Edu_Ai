from src.story.vectordb.VectorDBinferance import VectorDBinferance
from qdrant_client import QdrantClient, models
import logging
from src.story.vectordb.VectorEnums import VectorEnums, DistanceMethodEnums


class Qdrant(VectorDBinferance):
    def __init__(self, db_path: str, distance_method: str, api_key: str = None, default_vector_size: int = 384):
        self.client = None
        self.db_path = db_path
        self.api_key = api_key
        self.default_vector_size = default_vector_size
        self.distance_method = None
        if distance_method.lower() == DistanceMethodEnums.cosine.value.lower():
            self.distance_method = models.Distance.COSINE
        elif distance_method.lower() == DistanceMethodEnums.dot.value.lower():
            self.distance_method = models.Distance.DOT
        else:
            self.distance_method = models.Distance.COSINE
        self.logger = logging.getLogger(__name__)
        self.connect()  # auto-connect on init

    def connect(self):
        if self.db_path.startswith("http"):
            self.client = QdrantClient(url=self.db_path, api_key=self.api_key, timeout=60.0)
        else:
            self.client = QdrantClient(path=self.db_path, timeout=60.0)

    def disconnect(self):
        self.client = None

    def is_collection_existed(self, collection_name: str) -> bool:
        return self.client.collection_exists(collection_name=collection_name)

    def list_all_collections(self) -> list:
        collections = self.client.get_collections().collections
        return [c.name for c in collections]

    def get_collection(self, collection_name: str):
        return self.client.get_collection(collection_name=collection_name)

    def insert_one(self, collection_name: str, vector, metadata: dict, text: str, record_id: str) -> bool:
        if not self.is_collection_existed(collection_name):
            self.logger.error(f"Collection {collection_name} does not exist")
            return False
        try:
            payload = metadata or {}
            payload["text"] = text
            self.client.upsert(
                collection_name=collection_name,
                points=[models.PointStruct(id=record_id, vector=vector, payload=payload)]
            )
            return True
        except Exception as e:
            self.logger.error(f"Error inserting record: {e}")
            return False

    # === async versions used by NLPController ===

    async def create_collection(self, collection_name: str, embedding_size: int, do_reset: bool = False):
        if do_reset and self.is_collection_existed(collection_name):
            self.client.delete_collection(collection_name=collection_name)
        if not self.is_collection_existed(collection_name):
            self.client.create_collection(
                collection_name=collection_name,
                vectors_config=models.VectorParams(
                    size=embedding_size,
                    distance=self.distance_method
                )
            )
        return True

    async def insert_many(self, collection_name: str, vectors, metadata, texts, record_ids, batch_size: int = 100):
        if metadata is None:
            metadata = [None] * len(texts)
        if record_ids is None:
            record_ids = [None] * len(texts)
        for i in range(0, len(texts), batch_size):
            batch_end = i + batch_size
            points = []
            for j, (text, meta, vec, rid) in enumerate(zip(
                texts[i:batch_end], metadata[i:batch_end],
                vectors[i:batch_end], record_ids[i:batch_end]
            )):
                if vec is None:
                    self.logger.warning(f"Skipping chunk {i+j}: embedding is None (Ollama model may not be available)")
                    continue
                payload = meta or {}
                payload["text"] = text
                points.append(models.PointStruct(
                    id=rid if rid is not None else i + j,
                    vector=vec,
                    payload=payload
                ))
            if not points:
                continue
            try:
                self.client.upsert(collection_name=collection_name, points=points)
            except Exception as e:
                self.logger.error(f"Error uploading records: {e}")
                return False
        return True

    async def get_collection_info(self, collection_name: str):
        if not self.is_collection_existed(collection_name):
            return {}
        return self.client.get_collection(collection_name=collection_name)

    async def delete_collection(self, collection_name: str):
        if self.is_collection_existed(collection_name):
            self.client.delete_collection(collection_name=collection_name)
        return True

    async def search_by_vector(self, collection_name: str, vector, limit: int):
        if not self.is_collection_existed(collection_name):
            return []
        result = self.client.query_points(
            collection_name=collection_name,
            query=vector,
            limit=limit
        )
        return result.points
