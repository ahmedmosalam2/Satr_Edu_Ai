from abc import ABC ,abstractmethod


class VectorDBinferance(ABC):
    @abstractmethod
    def connect(self):
        pass
    @abstractmethod
    def disconnect(self):
        pass
    @abstractmethod
    def is_collection_existed(self,collection_name:str)->bool:
        pass
    @abstractmethod
    def create_collection(self,collection_name:str)->bool:
        pass
    @abstractmethod
    def list_all_collections(self)->list[str]:
        pass
    @abstractmethod
    def get_collection(self,collection_name:str)->bool:
        pass

    @abstractmethod
    def create_collection(self,collection_name:str,
                              embedding_size: int,
                              do_reset:bool=False)->bool:
        pass
    @abstractmethod
    def delete_collection(self,collection_name:str)->bool:
        pass
    @abstractmethod
    def insert_one(self,collection_name:str,vector:list[float]
                   ,metadata:dict,text:str,record_id:str)->bool:
        pass
    @abstractmethod
    def insert_many(self,collection_name:str,vectors:list[list[float]]
                    ,metadata:list[dict],texts:list[str],record_ids:list[str])->bool:
        pass
    @abstractmethod
    def search_by_vector(self,collection_name:str,vector:list[float],limit:int):
        pass
