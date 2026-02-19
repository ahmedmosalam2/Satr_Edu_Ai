from enum import Enum

class VectorEnums(Enum):
    CHROMA = "chroma"
    FAISS = "faiss"
    MILVUS = "milvus"
    PINECONE = "pinecone"
    WEAVIATE = "weaviate"
    QDRANT = "qdrant"

class DistanceMethodEnums(Enum):
    dot="DOT"
    cosine="Cosine"
    
    
    
    
