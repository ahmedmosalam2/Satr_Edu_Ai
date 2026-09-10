"""
src/chunking/qa_chunker.py
──────────────────────────
QA (Question-Answer) Chunker — متخصص للتعليم! 🎓

الفكرة:
  بدل ما يقسم النص لـ chunks عادية,
  بيحوّل كل chunk لزوج (سؤال + إجابة):
    Q: ما هو قانون نيوتن الثاني؟
    A: ينص على أن القوة تساوي الكتلة مضروبة في التسارع (F = ma)

كده الـ RAG بيبقى أدق لأن الـ embedding بتاع السؤال أقرب للـ query.
"""

import logging
import re
from typing import List, Optional
from .base_chunker import BaseChunker, Chunk

logger = logging.getLogger("uvicorn.error")


class QAChunker(BaseChunker):
    """
    يحوّل النص لأزواج سؤال-جواب باستخدام LLM.

    لو مفيش generation_client → بيعمل fallback على structure chunker
    مع إضافة "pseudo questions" من العناوين.
    """

    def __init__(self, generation_client=None, language: str = "ar"):
        """
        Parameters:
        - generation_client: أي LLM provider عنده generate_text method
        - language: "ar" للعربي, "en" للإنجليزي
        """
        self.generation_client = generation_client
        self.language = language

    @property
    def name(self) -> str:
        return "qa"

    def chunk(
        self,
        pages: list,
        chunk_size: int = 800,
        chunk_overlap: int = 0,
        **kwargs
    ) -> List[Chunk]:
        # If no LLM, use pseudo-QA from structure
        if self.generation_client is None:
            logger.info("[QAChunker] No LLM — using pseudo-QA from structure")
            return self._pseudo_qa_chunks(pages, chunk_size)

        # With LLM: generate actual Q&A pairs
        return self._llm_qa_chunks(pages, chunk_size)

    def _pseudo_qa_chunks(self, pages: list, chunk_size: int) -> List[Chunk]:
        """
        بدون LLM: يستخرج أسئلة من العناوين والهيكل.

        Heading: "قانون نيوتن الثاني"
        → Q: ما هو قانون نيوتن الثاني؟
        → A: [النص تحت العنوان]
        """
        all_chunks = []
        question_prefixes_ar = ["ما هو", "ما هي", "اشرح", "ما المقصود بـ", "وضّح"]
        question_prefixes_en = ["What is", "Explain", "Describe", "What does", "Define"]
        prefixes = question_prefixes_ar if self.language == "ar" else question_prefixes_en

        for page in pages:
            text = page.page_content if hasattr(page, "page_content") else str(page)
            meta = page.metadata if hasattr(page, "metadata") else {}

            if not text or not text.strip():
                continue

            heading = meta.get("heading", "")
            title = meta.get("title", "")

            # Try to generate a question from heading
            question = ""
            if heading:
                prefix = prefixes[hash(heading) % len(prefixes)]
                if self.language == "ar":
                    question = f"{prefix} {heading}؟"
                else:
                    question = f"{prefix} {heading}?"

            if question:
                qa_text = f"Q: {question}\nA: {text.strip()}"
            else:
                # No heading — use the text as-is with a generic question
                first_line = text.strip().split("\n")[0][:100]
                if self.language == "ar":
                    question = f"ما المقصود بالنص التالي: {first_line}؟"
                else:
                    question = f"What is the following about: {first_line}?"
                qa_text = f"Q: {question}\nA: {text.strip()}"

            # Split if too long
            if len(qa_text) > chunk_size:
                # Split the answer part
                answer_parts = self._split_text(text.strip(), chunk_size - len(question) - 10)
                for i, part in enumerate(answer_parts):
                    all_chunks.append(Chunk(
                        chunk_text=f"Q: {question}\nA: {part}",
                        chunk_metadata={
                            **meta,
                            "chunk_type": "qa",
                            "question": question,
                            "qa_method": "pseudo",
                            "part": i,
                        }
                    ))
            else:
                all_chunks.append(Chunk(
                    chunk_text=qa_text,
                    chunk_metadata={
                        **meta,
                        "chunk_type": "qa",
                        "question": question,
                        "qa_method": "pseudo",
                    }
                ))

        logger.info(f"[QAChunker] Generated {len(all_chunks)} pseudo-QA chunks")
        return all_chunks

    def _llm_qa_chunks(self, pages: list, chunk_size: int) -> List[Chunk]:
        """
        مع LLM: يولّد أسئلة فعلية من النص.
        """
        import asyncio
        all_chunks = []

        # First, do structure-based chunking to get manageable pieces
        from .structure_chunker import StructureChunker
        structure = StructureChunker()
        base_chunks = structure.chunk(pages, chunk_size=chunk_size)

        for chunk in base_chunks:
            text = chunk.chunk_text
            if len(text) < 50:  # Too short for QA
                all_chunks.append(chunk)
                continue

            try:
                # Generate question using LLM
                if self.language == "ar":
                    prompt = (
                        f"من النص التالي، اكتب سؤال واحد مهم يمكن الإجابة عليه من النص. "
                        f"اكتب السؤال فقط بدون أي شيء آخر.\n\nالنص: {text[:500]}"
                    )
                else:
                    prompt = (
                        f"From the following text, write one important question that can be answered from the text. "
                        f"Write only the question, nothing else.\n\nText: {text[:500]}"
                    )

                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        import concurrent.futures
                        with concurrent.futures.ThreadPoolExecutor() as executor:
                            question = executor.submit(
                                asyncio.run,
                                self.generation_client.generate_text(prompt=prompt)
                            ).result()
                    else:
                        question = asyncio.run(
                            self.generation_client.generate_text(prompt=prompt)
                        )
                except Exception:
                    question = None

                if question and question.strip():
                    question = question.strip()
                    qa_text = f"Q: {question}\nA: {text}"
                    all_chunks.append(Chunk(
                        chunk_text=qa_text,
                        chunk_metadata={
                            **chunk.chunk_metadata,
                            "chunk_type": "qa",
                            "question": question,
                            "qa_method": "llm",
                        }
                    ))
                else:
                    all_chunks.append(chunk)

            except Exception as e:
                logger.warning(f"[QAChunker] LLM QA generation failed: {e}")
                all_chunks.append(chunk)

        logger.info(f"[QAChunker] Generated {len(all_chunks)} QA chunks (LLM-assisted)")
        return all_chunks

    @staticmethod
    def _split_text(text: str, max_size: int) -> List[str]:
        """Simple text splitter."""
        if len(text) <= max_size:
            return [text]
        parts = []
        start = 0
        while start < len(text):
            end = min(start + max_size, len(text))
            if end < len(text):
                idx = text.rfind(". ", start, end)
                if idx > start + max_size // 2:
                    end = idx + 2
            parts.append(text[start:end].strip())
            start = end
        return [p for p in parts if p]
