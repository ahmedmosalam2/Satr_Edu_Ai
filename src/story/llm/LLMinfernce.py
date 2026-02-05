from abc import ABC,abstractmethod


class LLMInference(ABC):

    @abstractmethod
    def set_generate_model(self,model_id:str):
        pass

    @abstractmethod
    def set_embedding_model(self,model_id:str):
        pass

    @abstractmethod
    def generate_story(self,prompt:str,max_tokens:int=None,temperature:float=None,chat_history:list[dict]=None)->str:
        pass

    @abstractmethod
    def generate_embedding(self,text:str)->list[float]:
        pass

    @abstractmethod
    def construct_prompt(self,prompt:str,role:str):
        pass
    @abstractmethod
    def stream_generate_text(self,prompt:str):
        pass