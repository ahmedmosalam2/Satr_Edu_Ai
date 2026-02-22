from src.story.vectordb.VectorDBinferance import VectorDBinferance
from qdrant_client import QdrantClient
import logging
from src.story.vectordb.VectorEnums import VectorEnums,DistanceMethodEnums


from src.story.vectordb.VectorDBinferance import VectorDBinferance
from qdrant_client import QdrantClient, models
import logging
from src.story.vectordb.VectorEnums import VectorEnums, DistanceMethodEnums


class Qdrant(VectorDBinferance):
    def __init__(self, db_path: str, distance_method: str, api_key: str = None):
        self.client = None
        self.db_path = db_path
        self.api_key = api_key
        self.distance_method = None
        if distance_method.lower() == DistanceMethodEnums.cosine.value.lower():
            self.distance_method = models.Distance.COSINE
        elif distance_method.lower() == DistanceMethodEnums.dot.value.lower():
            self.distance_method = models.Distance.DOT
        else:
            self.distance_method = models.Distance.COSINE # Default
        self.logger = logging.getLogger(__name__)

    def connect(self):
        if self.db_path.startswith("http"):
             self.client = QdrantClient(url=self.db_path, api_key=self.api_key)
        else:
             self.client = QdrantClient(path=self.db_path)

    def disconnect(self):
        self.client = None

    def is_collection_existed(self, collection_name: str) -> bool:
        return self.client.collection_exists(collection_name=collection_name)

    def list_all_collections(self) -> list[str]:
        collections = self.client.get_collections().collections
        return [c.name for c in collections]

    def get_collection(self, collection_name: str):
        return self.client.get_collection(collection_name=collection_name)

    def create_collection(self, collection_name: str,
                          embedding_size: int,
                          do_reset: bool = False) -> bool:
        if do_reset and self.is_collection_existed(collection_name):
            self.delete_collection(collection_name)
        
        if not self.is_collection_existed(collection_name):
            self.client.create_collection(
                collection_name=collection_name,
                vectors_config=models.VectorParams(
                    size=embedding_size,
                    distance=self.distance_method
                )
            )
            return True
        return False

    def delete_collection(self, collection_name: str) -> bool:
        if self.is_collection_existed(collection_name):
            self.client.delete_collection(collection_name=collection_name)
            return True
        return False

    def insert_one(self, collection_name: str, vector: list[float],
                   metadata: dict, text: str, record_id: str) -> bool:
        if not self.is_collection_existed(collection_name):
            self.logger.error(f"Collection {collection_name} does not exist")
            return False
        try:
            payload = metadata or {}
            payload["text"] = text
            self.client.upsert(
                collection_name=collection_name,
                points=[
                    models.PointStruct(
                        id=record_id,
                        vector=vector,
                        payload=payload
                    )
                ]
            )
            return True
        except Exception as e:
            self.logger.error(f"Error inserting record: {e}")
            return False

    def insert_many(self, collection_name: str, vectors: list[list[float]],
                    metadata: list[dict], texts: list[str], record_ids: list[str], batch_size: int = 100) -> bool:
        if metadata is None:
            metadata = [None] * len(texts)
        if record_ids is None:
            record_ids = [None] * len(texts)

        for i in range(0, len(texts), batch_size):
            batch_end = i + batch_size
            batch_texts = texts[i:batch_end]
            batch_metadata = metadata[i:batch_end]
            batch_vectors = vectors[i:batch_end]
            batch_record_ids = record_ids[i:batch_end]

            points = []
            for j in range(len(batch_texts)):
                payload = batch_metadata[j] or {}
                payload["text"] = batch_texts[j]
                points.append(
                    models.PointStruct(
                        id=batch_record_ids[j] or str(i + j),
                        vector=batch_vectors[j],
                        payload=payload
                    )
                )

            try:
                self.client.upsert(
                    collection_name=collection_name,
                    points=points
                )
            except Exception as e:
                self.logger.error(f"Error uploading records: {e}")
                return False
        return True

    def search_by_vector(self, collection_name: str, vector: list[float], limit: int):
        if not self.is_collection_existed(collection_name):
            self.logger.error(f"Collection {collection_name} does not exist")
            return []
        return self.client.search(
            collection_name=collection_name,
            query_vector=vector,
            limit=limit
        )
