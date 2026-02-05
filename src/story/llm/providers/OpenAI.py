from ..LLMInference import LLMInference
from openai import OpenAI
import logging
from ..enums import LLMEnums
from ..LLMResponse import LLMResponse




class OpenAIProvider(LLMInference):
    def __init__(self,api_key:str,api_url:str,default_input_max_charaters:int=1000
    ,default_generation_max_output_tokens:int=1000
    ,default_embedding_max_output_tokens:int=1000
    ,default_embedding_temperature:float=0.1):

        self.api_key=api_key
        self.api_url=api_url

        self.default_generation_temperature=default_generation_temperature
        self.default_embedding_temperature=default_embedding_temperature
        self.default_input_max_charaters=default_input_max_charaters
        self.generate_model=None
        self.embedding_model=None
        self.embedding_size=None
        self.construct_prompt=self.construct_prompt()




        self.client=OpenAI(
            api_key=api_key,
            api_url=api_url
            )
        self.logger=logging.getLogger(__name__)

        

    def set_generate_model(self,model_id:str):
        self.generate_model=model_id

    def set_embedding_model(self,model_id:str,embedding_size:int):
        self.embedding_model=model_id
        self.embedding_size=embedding_size

    def generate_text(self,prompt:str,max_tokens:int=None,temperature:float=None,chat_history:list[dict]=None)->str:
        if not self.client:
            self.logger.error("client is not initialized") 
            return None 
        if not self.generate_model:
            self.logger.error("generate model is not initialized") 
            return None 
        
        max_tokens=max_tokens if max_tokens else self.default_generation_max_output_tokens
        temperature=temperature if temperature else self.default_generation_temperature
        chat_history.append(
            self.construct_prompt(
                prompt=prompt,
                role=LLMEnums.OpenAiEnums.USER.value
            )
        )
        response=self.client.chat.completions.create(
            model=self.generate_model,
            messages=chat_history,
            max_tokens=max_tokens,
            temperature=temperature
            )
        return LLMResponse(
            text=response.choices[0].message.content,
            model=self.generate_model,
            prompt_tokens=response.usage.prompt_tokens,
            completion_tokens=response.usage.completion_tokens,
            total_tokens=response.usage.total_tokens
        )
    if not response or not response.choices or len(response.choices)==0 or not response.choices[0].message or not response.choices[0].message.content:
        self.logger.error("response is None")
        return None

def process_text(self,text:str):
    return text[:self.default_input_max_charaters].strip()
        

    def embedd_text(self,text:str,document_type:str):
        if not self.client:
            self.logger.error("client is not initialized") 
            return None 
        if not self.embedding_model:
            self.logger.error("embedding model is not initialized") 
            return None 
        response=self.client.embeddings.create(
            model=self. embedding_model,
            input=[text]
            )
        if not response or not response.data or len(response.data)==0 or not response.data[0].embedding:
            self.logger.error("embedding response is None") 
            return None 
        return response.data[0].embedding
      
    def generate_embedding(self,text:str)->list[float]:
        pass

    def construct_prompt(self,prompt:str,role:str):
        return {
            "role":role,
            "content":prompt
        }
    def stream_generate_text(self,prompt:str):
        stream=self.client.chat.completions.create(
            model=self.generate_model,
            messages=self.construct_prompt(prompt=prompt,role=LLMEnums.OpenAiEnums.USER.value),
            stream=True
            )
        for chunk in stream:
            yield chunk.choices[0].delta.content