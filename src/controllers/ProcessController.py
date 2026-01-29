from .BaseController import BaseController
from .ProjectController import ProjectController
from src.models.enums.Processing import Processing
from src.models.enums.Response import Response
from src.utils.content_processor import DirectPDFLoader, RecursiveTextSplitter
import os


class ProcessController(BaseController):
    def __init__(self,project_id:str):
        super().__init__()


        self.project_id=project_id
        self.project_path=ProjectController().get_project_path(project_id=project_id)

    def get_file_extention(self,file_id:str):
        return os.path.splitext(file_id)[-1]
    def get_file_loader(self,file_id:str):
        file_path=os.path.join(self.project_path,file_id)
        file_extention=self.get_file_extention(file_path)
        if file_extention==Processing.TXT.value:
            from langchain_community.document_loaders import TextLoader
            return TextLoader(file_path)
        elif file_extention==Processing.PDF.value:
            # Using custom direct loader to avoid hanging issues with LangChain's wrapper
            return DirectPDFLoader(file_path)
        elif file_extention==Processing.MARKDOWN.value:
            from langchain_community.document_loaders import UnstructuredMarkdownLoader
            return UnstructuredMarkdownLoader(file_path)
        elif file_extention==Processing.HTML.value:
            from langchain_community.document_loaders import UnstructuredHTMLLoader
            return UnstructuredHTMLLoader(file_path)
        elif file_extention==Processing.WORD.value:
            from langchain_community.document_loaders import UnstructuredWordDocumentLoader
            return UnstructuredWordDocumentLoader(file_path)
        elif file_extention==Processing.POWERPOINT.value:
            from langchain_community.document_loaders import UnstructuredPowerPointLoader
            return UnstructuredPowerPointLoader(file_path)
        elif file_extention==Processing.CSV.value:
            from langchain_community.document_loaders import UnstructuredCSVLoader
            return UnstructuredCSVLoader(file_path)
        elif file_extention==Processing.JSON.value:
            from langchain_community.document_loaders import UnstructuredJSONLoader
            return UnstructuredJSONLoader(file_path)
        else:
            raise ValueError(Response.FILE_TYPE_NOT_SUPPORTED.value)
    
    def get_file_content(self,file_id:str):
        print(f"🔄 Loading file content for: {file_id}")
        loader=self.get_file_loader(file_id=file_id)
        content = loader.load()
        print(f"File loaded successfully. Content length: {len(content)}")
        return content
         


    def process_file_content(self,file_content:list,chunk_size:int,chunk_overlap:int):
        # Reverting to Smart RecursiveTextSplitter due to stability issues with Semantic/ML libs
        text_splitter = RecursiveTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)

        print("✂️ Splitting text into chunks (Smart Recursive Splitter)...")
        file_content_text=[
            rec.page_content
            for rec in file_content
        ]
        file_meta_data=[
            rec.metadata
            for rec in file_content
        ]
        chunks=text_splitter.create_documents(file_content_text,
        metadatas=file_meta_data)

        return chunks
        
        
        