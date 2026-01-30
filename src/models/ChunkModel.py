from .BaseDataModel import BaseDataModel
from src.models.enums.DataBaseEnumProject import DataBaseEnumProject
from src.models.scheme_db import data_chunk
from bson import ObjectId
from pymongo import InsertOne


class ChunkModel(BaseDataModel):
    def __init__(self, client: object = None, project_id: str = None):
        super().__init__(client)
        self.project_id = project_id
        self.collection = self.db[DataBaseEnumProject.CHUNK.value] if self.db is not None else None

    async def create_chunk(self,chunk:data_chunk):
        result= await self.collection.insert_one(chunk.dict())
        return result.inserted_id

    async def get_chunks(self,project_id:str):
        result = await self.collection.find_one({"chunk_project_id":ObjectId(project_id)})
        if result is None:
            return None
        return data_chunk(**result)

    async def insert_many_chunks(self,project_id:str,chunks:list[data_chunk],batch_size:int=100):
        for i in range(0,len(chunks),batch_size):
            batch_size=chunks[i:i+batch_size]
            operations=[
                InsertOne(chunk.dict())
                 for chunk in batch_size
                 ]
            await self.collection.bulk_write(operations)
        

            
    
    async def update_chunk(self,chunk:data_chunk):
        result= await self.collection.update_one({"chunk_id":chunk.chunk_id},
        update={"$set":chunk.dict()})
        return result
    
    async def delete_chunk(self,chunk_id:str):
        result= await self.collection.delete_one({"chunk_id":chunk_id})
        return result
    