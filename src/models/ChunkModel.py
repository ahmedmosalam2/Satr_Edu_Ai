from .BaseDataModel import BaseDataModel
from src.models.enums.DataBaseEnumProject import DataBaseEnumProject
from src.models.scheme_db import DataChunk
from bson import ObjectId
from pymongo import InsertOne


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

    async def create_chunk(self,chunk:DataChunk):
        result= await self.collection.insert_one(chunk.dict())
        return result.inserted_id

    async def get_chunks(self,project_id:str):
        result = await self.collection.find_one({"chunk_project_id":ObjectId(project_id)})
        if result is None:
            return None
        return DataChunk(**result)

    async def insert_many_chunks(self,project_id:str,chunks:list[DataChunk],batch_size:int=100):
        for i in range(0,len(chunks),batch_size):
            batch_chunks=chunks[i:i+batch_size]
            operations=[
                InsertOne(chunk.dict())
                 for chunk in batch_chunks
                 ]
            await self.collection.bulk_write(operations)

            
    
    async def update_chunk(self,chunk:DataChunk):
        result= await self.collection.update_one({"chunk_id":chunk.chunk_id},
        update={"$set":chunk.dict()})
        return result
    
    async def delete_chunk(self,chunk_id:str):
        result= await self.collection.delete_one({"chunk_id":chunk_id})
        return result
    