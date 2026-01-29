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
        file_ext = os.path.splitext(file.filename)[1].lower()
        if file_ext not in self.settings.FILE_ALLOWED_EXTION and file_ext not in self.settings.IMAGE_ALLOWED_EXTION: # Assuming check both or just FILE based on your logic, let's fix the basic check first
             # Fallback to checking just extension if configured that way
             if file_ext not in self.settings.FILE_ALLOWED_EXTION:
                raise HTTPException(status_code=400,detail=Response.FILE_TYPE_NOT_SUPPORTED.value)

        if file.size > self.file_max_size:
            raise HTTPException(status_code=400,detail=Response.FILE_SIZE_EXCEEDED.value)

        return True
    
    def generate_file_name(self,file_name:str,project_id:str):
        random_filename=self.generate_random_string(10)
        project_path=ProjectController().get_project_path(project_id=project_id)
        
        cleaned_file_name=self.get_clean_file_name(
            orig_file_name=file_name,

        )
        while os.path.exists(os.path.join(project_path,
                                        random_filename+"_"+cleaned_file_name)):
            random_filename=self.generate_random_string(10)   
        new_file_name=os.path.join(project_path,
                                    random_filename+"_"+cleaned_file_name)

        return new_file_name
        
        
    def get_clean_file_name(self, orig_file_name: str):

        cleaned_file_name = re.sub(r'[^\w.]', '', orig_file_name.strip())

        cleaned_file_name = cleaned_file_name.replace(" ", "_")
        return cleaned_file_name

