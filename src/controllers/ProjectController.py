from src.models.ProjectModel import ProjectModel
from src.models.enums.Response import Response
from src.controllers.BaseController import BaseController
import os
class ProjectController(BaseController):
    def __init__(self, db_client=None):
        super().__init__()
        self.project_model = ProjectModel(client=db_client)
    
    async def add_file_to_project(self, project_id: str, file_name: str):
        print(f"DEBUG: add_file_to_project called for {project_id}, file: {file_name}")
        project = await self.project_model.get_project(project_id=project_id)
        print(f"DEBUG: Project loaded: {project.project_id}, files: {project.project_files}")
        if file_name not in project.project_files:
            project.project_files.append(file_name)
            print(f"DEBUG: Appended file using append. New files: {project.project_files}")
            await self.project_model.update_project(project_id=project_id, project=project)
        else:
            print("DEBUG: File already exists in project.")
    def get_project_path(self,project_id:str):
        project_path=os.path.join(self.base_path,project_id)
        if not os.path.exists(project_path):
            os.makedirs(project_path)
        return project_path

    