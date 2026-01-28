from .BaseDataModel import BaseDataModel

class ProjectModel(BaseDataModel):
    def __init__(self, project_id: str = None):
        super().__init__()
        self.project_id = project_id
