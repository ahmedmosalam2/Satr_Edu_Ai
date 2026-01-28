from .BaseController import BaseController
from src.models.enums.Response import Response
from fastapi import HTTPException,UploadFile
from .ProjectController import ProjectController
import re
import os

class DataController(BaseController):
    def __init__(self):
        super().__init__()
        self.file_max_size=self.settings.FILE_MAX_SIZE
    
    def valied_upload(self,project_id:str, file:UploadFile):
        if file.content_type not in self.settings.FILE_ALLOWED_EXTION:
            raise HTTPException(status_code=400,detail=Response.FILE_TYPE_NOT_ALLOWED.value)
        if file.size > self.file_max_size:
            raise HTTPException(status_code=400,detail=Response.FILE_SIZE_TOO_LARGE.value)

        return True
    
    def generate_file_name(self,file_name:str,project_id:str):
        random_filename=self.generate_random_string()
        project_path=ProjectController().get_project_path(project_id=project_id)
        
        cleaned_file_name=self.get_clean_file_name(
            orig_file_name=file_name,

        )
        while os.path.exists(os.path.join(project_path,
                                        random_filename+"_"+cleaned_file_name)):
            random_filename=self.generate_random_string()   
        new_file_name=os.path.join(project_path,
                                    random_filename+"_"+cleaned_file_name)

        return new_file_name
        
        
    def get_clean_file_name(self, orig_file_name: str):

        cleaned_file_name = re.sub(r'[^\w.]', '', orig_file_name.strip())

        cleaned_file_name = cleaned_file_name.replace(" ", "_")
        return cleaned_file_name

