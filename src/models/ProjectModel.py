from .BaseDataModel import BaseDataModel
from src.models.enums.DataBaseEnumProject import DataBaseEnumProject
from src.models.scheme_db import Project
import math
class ProjectModel(BaseDataModel):
    def __init__(self, client: object = None, project_id: str = None):
        super().__init__(client)
        self.project_id = project_id
        # Only set collections if db is available (MongoDB connected)
        self.collection = self.db[DataBaseEnumProject.PROJECT.value] if self.db is not None else None
        self.chunk_collection = self.db[DataBaseEnumProject.CHUNK.value] if self.db is not None else None
    async def create_project(self,project:Project):
        result= await self.collection.insert_one(project.dict())
        return result.inserted_id

    async def get_project(self,project_id:str):
        result= await self.collection.find_one(
            filter={"project_id":project_id})
        if result is None:
            project=Project(project_id=project_id)
            await self.create_project(project)
            result= await self.collection.find_one(
                filter={"project_id":project_id})
        return Project(**result)
    async def update_project(self,project_id:str,project:Project):
        result= await self.collection.update_one(
            filter={"project_id":project_id},
            update={"$set":project.dict()})
        return result
    async def delete_project(self,project_id:str):
        result= await self.collection.delete_one( {"project_id":project_id})
        return result   

    async def get_all_projects(self,page:int=1,page_size:int=10):
        total_document=await self.collection.count_documents({})
        total_page=math.ceil(total_document/page_size)
        projects=await self.collection.find().skip((page-1)*page_size).limit(page_size)
        return {
            "total_document":total_document,
            "total_page":total_page,
            "projects":[Project(**project) async for project in projects]
        }
       

 

    