from .BaseController import BaseController
from src.models.scheme_db.project import Project
from src.models.scheme_db.data_chunk import DataChunk
from src.story.llm.LLMEnums import LLMEnums
from typing import List
import json
import logging
from src.helpers.config import get_settings

logger = logging.getLogger("uvicorn.error")

class NLPController(BaseController):

    def __init__(self, vectordb_client, generation_client,
                 embedding_client, template_parser,
                 chunk_model=None):   # chunk_model للـ keyword search
        super().__init__()

        self.vectordb_client = vectordb_client
        self.generation_client = generation_client
        self.embedding_client = embedding_client
        self.template_parser = template_parser
        self.chunk_model = chunk_model  # optional — لو None بيشتغل بـ Qdrant فقط

    def create_collection_name(self, project_id: str):
        return f"collection_{self.vectordb_client.default_vector_size}_{project_id}".strip()
    
    async def reset_vector_db_collection(self, project: Project):
        collection_name = self.create_collection_name(project_id=project.project_id)
        return await self.vectordb_client.delete_collection(collection_name=collection_name)
    
    async def get_vector_db_collection_info(self, project: Project):
        collection_name = self.create_collection_name(project_id=project.project_id)
        collection_info = await self.vectordb_client.get_collection_info(collection_name=collection_name)
        return json.loads(
            json.dumps(collection_info, default=lambda x: x.__dict__ if hasattr(x, '__dict__') else str(x))
        )
    
    async def index_into_vector_db(self, project: Project, chunks: List[DataChunk],
                                   chunks_ids: List[int], 
                                   do_reset: bool = False):
        
        collection_name = self.create_collection_name(project_id=project.project_id)

        texts = [c.chunk_text for c in chunks]
        metadata = [c.chunk_metadata for c in chunks]
        vectors = self.embedding_client.embed_text(
            text=texts,
            document_type=LLMEnums.DocumentTypeEnum.DOCUMENT.value
        )

        _ = await self.vectordb_client.create_collection(
            collection_name=collection_name,
            embedding_size=self.embedding_client.embedding_size,
            do_reset=do_reset,
        )

        _ = await self.vectordb_client.insert_many(
            collection_name=collection_name,
            texts=texts,
            metadata=metadata,
            vectors=vectors,
            record_ids=chunks_ids,
        )

        return True

    async def search_vector_db_collection(self, project: Project, text: str, limit: int = 10):

        query_vector = None
        collection_name = self.create_collection_name(project_id=project.project_id)

        vectors = self.embedding_client.embed_text(
            text=text,
            document_type=LLMEnums.DocumentTypeEnum.QUERY.value
        )

        if not vectors or len(vectors) == 0:
            return False
        
        if isinstance(vectors, list) and len(vectors) > 0:
            query_vector = vectors[0]

        if not query_vector:
            return False

        results = await self.vectordb_client.search_by_vector(
            collection_name=collection_name,
            vector=query_vector,
            limit=limit
        )

        if not results:
            return False

        return results
    
    async def answer_rag_question(self, project: Project, query: str, limit: int = 10):
        """
        RAG answer with source citations.
        لو MULTI_RETRIEVAL_ENABLED → يستخدم Qdrant + MongoDB keyword merged + Reranked.
        لو لأ → يستخدم Qdrant + Reranker بس (السلوك القديم).
        Returns: (answer, full_prompt, chat_history, sources)
        """
        answer, full_prompt, chat_history, sources = None, None, None, []
        settings = get_settings()

        # ── Get query vector (مشترك بين الحالتين) ───────────────────────────
        vectors = self.embedding_client.embed_text(
            text=query,
            document_type=LLMEnums.DocumentTypeEnum.QUERY.value
        )
        if not vectors or len(vectors) == 0:
            return answer, full_prompt, chat_history, sources
        query_vector = vectors[0] if isinstance(vectors, list) else vectors
        if not query_vector:
            return answer, full_prompt, chat_history, sources

        collection_name = self.create_collection_name(project_id=project.project_id)

        # ── Retrieval ────────────────────────────────────────────────────────
        if settings.MULTI_RETRIEVAL_ENABLED and self.chunk_model is not None:
            # Multi-Retrieval: Qdrant + MongoDB keyword + Reranker
            try:
                from src.helpers.multi_retriever import MultiRetriever
                from src.helpers.reranker import get_reranker

                reranker = get_reranker(settings.RERANKER_MODEL) if settings.RERANKER_ENABLED else None
                retriever = MultiRetriever(
                    vectordb_client=self.vectordb_client,
                    chunk_model=self.chunk_model,
                    reranker=reranker,
                    vector_limit=settings.VECTOR_SEARCH_LIMIT,
                    keyword_limit=settings.KEYWORD_SEARCH_LIMIT,
                    final_top_k=settings.RERANKER_TOP_K,
                )
                retrieved_documents = await retriever.retrieve(
                    query=query,
                    query_vector=query_vector,
                    collection_name=collection_name,
                    project_id=project.project_id,
                )
                logger.info(f"[MultiRetrieval] Final results: {len(retrieved_documents)}")
            except Exception as e:
                logger.warning(f"[MultiRetrieval] Failed, falling back to Qdrant only: {e}")
                retrieved_documents = await self.vectordb_client.search_by_vector(
                    collection_name=collection_name,
                    vector=query_vector,
                    limit=limit,
                )
        else:
            # Single-Retrieval (Qdrant only) — السلوك القديم
            retrieved_documents = await self.vectordb_client.search_by_vector(
                collection_name=collection_name,
                vector=query_vector,
                limit=limit,
            )
            if retrieved_documents and settings.RERANKER_ENABLED:
                try:
                    from src.helpers.reranker import get_reranker
                    reranker = get_reranker(model_name=settings.RERANKER_MODEL)
                    retrieved_documents = reranker.rerank(
                        query=query,
                        documents=retrieved_documents,
                        top_k=settings.RERANKER_TOP_K,
                    )
                except Exception as e:
                    logger.warning(f"Reranker step failed: {e}")

        sources = []
        for idx, doc in enumerate(retrieved_documents):
            payload = doc.payload if hasattr(doc, "payload") else {}
            sources.append({
                "doc_num": idx + 1,
                "chunk_id":    payload.get("chunk_id", ""),
                "source_file": payload.get("source", payload.get("source_file", "")),
                "chunk_order": payload.get("chunk_order", payload.get("page", idx)),
                "score":       round(doc.score, 4) if hasattr(doc, "score") else None,
                "snippet":     (payload.get("text", ""))[:200],  # first 200 chars preview
            })

        system_prompt = self.template_parser.get("rag", "system_prompt")

        documents_prompts = "\n".join([
            self.template_parser.get("rag", "document_prompt", {
                    "doc_num": idx + 1,
                    "chunk_text": self.generation_client.process_text(doc.payload.get("text", "")),
            })
            for idx, doc in enumerate(retrieved_documents)
        ])

        footer_prompt = self.template_parser.get("rag", "footer_prompt", {
            "query": query
        })

        chat_history = [
            self.generation_client.construct_prompt(
                prompt=system_prompt,
                role=self.generation_client.enums.SYSTEM.value,
            )
        ]

        full_prompt = "\n\n".join([documents_prompts, footer_prompt])

        answer = self.generation_client.generate_text(
            prompt=full_prompt,
            chat_history=chat_history
        )

        return answer, full_prompt, chat_history, sources