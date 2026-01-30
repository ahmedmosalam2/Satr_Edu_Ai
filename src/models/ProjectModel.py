from .BaseDataModel import BaseDataModel
from src.models.enums.DataBaseEnumProject import DataBaseEnumProject
from src.models.scheme_db import project
class ProjectModel(BaseDataModel):
    def __init__(self, project_id: str = None):
        super().__init__()
        self.project_id = project_id
        self.collection=self.db[DataBaseEnumProject.PROJECT.value]
        self.chunk_collection=self.db[DataBaseEnumProject.CHUNK.value]
    async def create_project(self,project:project):
        result= await self.collection.insert_one(project.dict())
        return result.inserted_id

    async def get_project(self,project_id:str):
        result= await self.collection.find_one(
            filter={"project_id":project_id})
        if result is None:
            project=project(project_id=project_id)
            await self.create_project(project)
            result= await self.collection.find_one(
                filter={"project_id":project_id})
        return project(**result)
    async def update_project(self,project_id:str,project:project):
        result= await self.collection.update_one(
            filter={"project_id":project_id},
            update={"$set":project.dict()})
        return result
    async def delete_project(self,project_id:str):
        result= await self.collection.delete_one( {"project_id":project_id})
        return result

    async def get_all_projects(self):
        result= await self.collection.find()
        return result

 

    