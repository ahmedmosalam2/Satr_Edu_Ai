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
                 chunk_model=None):
        super().__init__()
        self.vectordb_client = vectordb_client
        self.generation_client = generation_client
        self.embedding_client = embedding_client
        self.template_parser = template_parser
        self.chunk_model = chunk_model

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

        if not texts:
            return True

        # embed_text always returns a 2D list: [[vec1], [vec2], ...]
        vectors = await self.embedding_client.embed_text(
            text=texts,
            document_type=LLMEnums.DocumentTypeEnum.DOCUMENT.value
        )

        if not vectors:
            raise RuntimeError("Embedding backend returned no vectors for the requested chunks.")
        if len(vectors) != len(texts):
            raise RuntimeError(
                f"Embedding/vector size mismatch: got {len(vectors)} vectors for {len(texts)} chunks."
            )

        created = await self.vectordb_client.create_collection(
            collection_name=collection_name,
            embedding_size=self.embedding_client.embedding_size,
            do_reset=do_reset,
        )
        if created is False:
            raise RuntimeError(f"Failed to create or access vector collection '{collection_name}'.")

        inserted = await self.vectordb_client.insert_many(
            collection_name=collection_name,
            texts=texts,
            metadata=metadata,
            vectors=vectors,
            record_ids=chunks_ids,
        )
        if inserted is False:
            raise RuntimeError(f"Failed to insert vectors into collection '{collection_name}'.")

        return True

    async def search_vector_db_collection(self, project: Project, text: str, limit: int = 10):
        """Search for similar vectors. Always returns a list (empty if none found)."""
        collection_name = self.create_collection_name(project_id=project.project_id)

        # embed_text with a single string returns [[vector]]
        vectors = await self.embedding_client.embed_text(
            text=text,
            document_type=LLMEnums.DocumentTypeEnum.QUERY.value
        )

        if not vectors:
            logger.warning(f"Search: embedding returned nothing for text: {text[:50]}")
            return []

        # Always take the first vector from the 2D list
        query_vector = vectors[0]

        if not query_vector:
            return []

        results = await self.vectordb_client.search_by_vector(
            collection_name=collection_name,
            vector=query_vector,
            limit=limit
        )

        return results if results else []

    async def answer_rag_question(self, project: Project, query: str, limit: int = 10):
        """Generate a RAG answer with source citations."""
        answer, full_prompt, chat_history, sources = None, None, None, []
        settings = get_settings()

        # Get query embedding
        vectors = await self.embedding_client.embed_text(
            text=query,
            document_type=LLMEnums.DocumentTypeEnum.QUERY.value
        )
        if not vectors:
            return answer, full_prompt, chat_history, sources

        query_vector = vectors[0]
        if not query_vector:
            return answer, full_prompt, chat_history, sources

        collection_name = self.create_collection_name(project_id=project.project_id)

        # Retrieval
        retrieved_documents = []
        if settings.MULTI_RETRIEVAL_ENABLED and self.chunk_model is not None:
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
                ) or []
        else:
            retrieved_documents = await self.vectordb_client.search_by_vector(
                collection_name=collection_name,
                vector=query_vector,
                limit=limit,
            ) or []
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

        if not retrieved_documents:
            return answer, full_prompt, chat_history, sources

        # Build sources
        sources = []
        for idx, doc in enumerate(retrieved_documents):
            payload = doc.payload if hasattr(doc, "payload") else {}
            sources.append({
                "doc_num": idx + 1,
                "chunk_id": payload.get("chunk_id", ""),
                "source_file": payload.get("source", payload.get("source_file", "")),
                "chunk_order": payload.get("chunk_order", payload.get("page", idx)),
                "score": round(doc.score, 4) if hasattr(doc, "score") else None,
                "snippet": (payload.get("text", ""))[:200],
            })

        # Build prompt
        system_prompt = self.template_parser.get("rag", "system_prompt")

        documents_prompts = "\n".join([
            self.template_parser.get("rag", "document_prompt", {
                "doc_num": idx + 1,
                "chunk_text": self.generation_client.process_text(doc.payload.get("text", "")),
            })
            for idx, doc in enumerate(retrieved_documents)
        ])

        footer_prompt = self.template_parser.get("rag", "footer_prompt", {"query": query})

        chat_history = [
            self.generation_client.construct_prompt(
                prompt=system_prompt,
                role=self.generation_client.enums.SYSTEM.value,
            )
        ]

        full_prompt = "\n\n".join([documents_prompts, footer_prompt])

        answer = await self.generation_client.generate_text(
            prompt=full_prompt,
            chat_history=chat_history
        )

        return answer, full_prompt, chat_history, sources
