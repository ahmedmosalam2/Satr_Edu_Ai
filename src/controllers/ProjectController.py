from src.models.ProjectModel import ProjectModel
from src.models.enums.Response import Response
from src.controllers.BaseController import BaseController
import os
class ProjectController(BaseController):
    def __init__(self):
        super().__init__()
        self.project_model=ProjectModel()
    
    def get_project_path(self,project_id:str):
        project_path=os.path.join(self.base_path,project_id)
        if not os.path.exists(project_path):
            os.makedirs(project_path)
        return project_path

    