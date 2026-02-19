from src.story.vectordb.VectorDBinferance import VectorDBinferance
from qdrant_client import QdrantClient
import logging
from src.story.vectordb.VectorEnums import VectorEnums,DistanceMethodEnums


class Qdrant(VectorDBinferance):
    def __init__(self,db_path: str,distance_method: str):
        self.client=None
        self.db_path=db_path
        self.distance_method=None
        if distance_method ==DistanceMethodEnums.Cosine.value:
            self.distance_method=DistanceMethodEnums.Cosine.value
        elif distance_method ==DistanceMethodEnums.Dot.value:
            self.distance_method=DistanceMethodEnums.Dot.value
        self.logger=logging.getLogger(__name__)
    
    

    def connect(self):
        self.client=QdrantClient(url=self.db_path,api_key=self.api_key)


    def disconnect(self):
        self.client =None

    def is_collection_existed(self,collection_name:str)->bool:
        return self.client.is_collection_exists(collection_name=collection_name)
    def list_all_collections(self)->list[str]:
        return self.client.get_collections()
    def get_collection(self,collection_name:str)->bool:
        return self.client.get_collection(collection_name=collection_name)
    def create_collection(self,collection_name:str,
                              embedding_size: int,
                              do_reset:bool=False)->bool:
          if do_reset and self.is_collection_existed(collection_name):
            self.delete_collection(collection_name)
        self.client.create_collection(collection_name=collection_name,
                            embedding_size=embedding_size,
                            distance=self.distance_method)
    def delete_collection(self,collection_name:str)->bool:
        if self.is_collection_existed(collection_name):
            self.client.delete_collection(collection_name=collection_name)
    def insert_one(self,collection_name:str,vector:list[float]
                   ,metadata:dict,text:str,record_id:str)->bool:
        if not self.is_collection_existed(collection_name):
            self.logger.error(f"Collection {collection_name} does not exist")
            return False
        try:
            _ =self.client.upload_records(collection_name=collection_name,
                   records=[
                       models.Record(
                           id=record_id,
                           vector=vector,
                           payload=metadata,
                           text=text
                       )
                   ])
            return True
        except Exception as e:
            self.logger.error(f"Error inserting record: {e}")
            return False

                
            
    def insert_many(self,collection_name:str,vectors:list[list[float]]
                    ,metadata:list[dict],texts:list[str],record_ids:list[str])->bool:
        if metadata is None:
            metadata=[None]*len(texts)
        if record_ids is None:
            record_ids=[None]*len(texts)

        for i in range(len(texts),batch_size):
            batch_end= i+batch_size
            batch_text=texts[i:batch_end]
            batch_metadata=metadata[i:batch_end]
            batch_vectors=vectors[i:batch_end]
            batch_record_ids=record_ids[i:batch_end]
            
            batch_records=[
                models.Record(
                    id=record_id,
                    vector=batch_vector,
                    payload=batch_metadata,
                    text=batch_text
                )
            ]
            try:
                _ =self.client.upload_records(collection_name=collection_name,
                   records=batch_records)
            except Exception as e:
                self.logger.error(f"Error uploading records: {e}")
                return False
        return True
    def search_by_vector(self,collection_name:str,vector:list[float],limit:int):
        if not self.is_collection_existed(collection_name):
            self.logger.error(f"Collection {collection_name} does not exist")
            return False    
        return self.client.search(collection_name=collection_name,
                   vector=vector,
                   limit=limit)