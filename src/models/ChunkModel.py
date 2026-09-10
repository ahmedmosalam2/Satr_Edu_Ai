from .BaseDataModel import BaseDataModel
from src.models.enums.DataBaseEnumProject import DataBaseEnumProject
from src.models.scheme_db import DataChunk
from bson import ObjectId
from pymongo import InsertOne, TEXT


class ChunkModel(BaseDataModel):
    def __init__(self, client: object = None, project_id: str = None):
        super().__init__(client)
        self.project_id = project_id
        self.collection = self.db[DataBaseEnumProject.CHUNK.value] if self.db is not None else None

    @classmethod
    async def create_index(cls,db_client:object):
        instance=cls(client=db_client)
        await instance.init_collection()
        return instance
    

    async def init_collection(self):
        all_collections= await self.db.list_collection_names()
        if DataBaseEnumProject.CHUNK.value not in all_collections:
            self.collection=self.db[DataBaseEnumProject.CHUNK.value]
            indexes=DataChunk.get_indexes()

            for index in indexes:
                await self.collection.create_index(
                    index["key"],
                    unique=index["unique"],
                    name=index["name"]
                    )

        # Text index for keyword search (idempotent)
        try:
            await self.collection.create_index(
                [("chunk_text", TEXT)],
                name="chunk_text_search",
                default_language="none",  # يدعم العربي والإنجليزي
            )
        except Exception:
            pass  # Index already exists

    async def create_chunk(self,chunk:DataChunk):
        result= await self.collection.insert_one(chunk.dict())
        return result.inserted_id

    async def get_chunks(self,project_id:str):
        from bson import ObjectId
        result = await self.collection.find_one({"chunk_project_id":ObjectId(project_id)})
        if result is None:
            return None
        return DataChunk(**result)

    async def insert_many_chunks(self,project_id:str,chunks:list[DataChunk],batch_size:int=100):
        for i in range(0,len(chunks),batch_size):
            batch_chunks=chunks[i:i+batch_size]
            operations=[
                InsertOne(chunk.dict(exclude_none=True))
                 for chunk in batch_chunks
                 ]
            try:
                await self.collection.bulk_write(operations)
            except Exception as e:
                import logging
                logging.getLogger('uvicorn.error').error(f"insert_many_chunks error: {e}")

            
    
    async def update_chunk(self,chunk:DataChunk):
        result= await self.collection.update_one({"chunk_id":chunk.chunk_id},
        update={"$set":chunk.dict()})
        return result
    
    async def delete_chunk(self,chunk_id:str):
        result= await self.collection.delete_one({"chunk_id":chunk_id})
        return result 

    async def get_project_chunks(self,project_id:str ,page:int=1,page_size:int=10,):
        result= await self.collection.find({"chunk_project_id":project_id}).skip((page-1)*page_size).limit(page_size).to_list(length=page_size)
        return [DataChunk(**chunk) for chunk in result]

    async def search_by_keyword(
        self,
        project_id: str,
        query: str,
        limit: int = 10,
    ) -> list:
        """
        بحث بالكلمات بـ MongoDB $text index.
        يرجع list من dicts، كل dict عنده payload + score
        عشان يكون compatible مع نتائج Qdrant.
        """
        if self.collection is None:
            return []
        try:
            cursor = self.collection.find(
                {
                    "$text": {"$search": query},
                    "chunk_project_id": project_id,
                },
                {
                    "score": {"$meta": "textScore"},
                    "chunk_id": 1,
                    "chunk_text": 1,
                    "chunk_metadata": 1,
                    "chunk_order": 1,
                }
            ).sort([("score", {"$meta": "textScore"})]).limit(limit)

            results = []
            async for doc in cursor:
                doc.pop("_id", None)
                score = doc.pop("score", 0.0)
                # نبني object بنفس شكل Qdrant ScoredPoint عشان الـ Reranker يشتغل عليه
                results.append(_KeywordResult(
                    payload={
                        "text": doc.get("chunk_text", ""),
                        "chunk_id": doc.get("chunk_id", ""),
                        "chunk_order": doc.get("chunk_order", 0),
                        **(doc.get("chunk_metadata") or {}),
                    },
                    score=score,
                ))
            return results
        except Exception as e:
            import logging
            logging.getLogger("uvicorn.error").warning(f"Keyword search failed: {e}")
            return []


class _KeywordResult:
    """Wrapper عشان نتائج MongoDB تبقى compatible مع Qdrant ScoredPoint."""
    def __init__(self, payload: dict, score: float):
        self.payload = payload
        self.score = score