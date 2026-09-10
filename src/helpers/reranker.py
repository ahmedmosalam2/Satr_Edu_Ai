import logging
from typing import List, Any

logger = logging.getLogger("uvicorn.error")


class RerankerHelper:
    """
    Reranker using sentence-transformers CrossEncoder.

    الفكرة:
    - Qdrant بيجيب أفضل N نتيجة بناءً على Vector Similarity
    - الـ Reranker بيراجع كل نتيجة ويسأل نفسه:
      "هل الـ DOCUMENT ده فعلاً بيجاوب على السؤال ده؟"
    - بيرتب النتائج ويرجع أفضل top_k منها
    """

    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        self.model_name = model_name
        self._model = None  # Lazy load — مش بنحمل الموديل غير لما نحتاجه

    def _load_model(self):
        """تحميل الموديل أول مرة بس."""
        if self._model is None:
            try:
                from sentence_transformers import CrossEncoder
                logger.info(f"Loading reranker model: {self.model_name}")
                self._model = CrossEncoder(self.model_name)
                logger.info("Reranker model loaded successfully ✅")
            except Exception as e:
                logger.error(f"Failed to load reranker model: {e}")
                self._model = None
        return self._model

    def rerank(self, query: str, documents: List[Any], top_k: int = 3) -> List[Any]:
        """
        إعادة ترتيب النتائج بناءً على مدى صلتها بالسؤال.

        الـ parameters:
        - query: السؤال اللي المستخدم بعته
        - documents: النتائج اللي Qdrant رجعها (Qdrant ScoredPoint objects)
        - top_k: عايز ترجع كام نتيجة بعد الترتيب

        الـ return:
        - نفس الـ documents بس مرتبة ومفلترة (أحسن top_k بس)
        """
        if not documents:
            return documents

        model = self._load_model()

        # لو الموديل مش موجود → رجّع النتائج كما هي بدون reranking
        if model is None:
            logger.warning("Reranker not available, returning original results")
            return documents[:top_k]

        try:
            # استخرج النص من كل نتيجة
            texts = []
            for doc in documents:
                # كل نتيجة من Qdrant عندها payload فيه النص
                payload = doc.payload if hasattr(doc, "payload") else {}
                text = payload.get("text", "")
                texts.append(text)

            # الـ CrossEncoder بياخد pairs من (سؤال, نص) ويدي كل واحد score
            pairs = [(query, text) for text in texts]
            scores = model.predict(pairs)

            # ندمج الـ scores مع الـ documents ونرتب تنازلياً
            scored_docs = sorted(
                zip(scores, documents),
                key=lambda x: x[0],
                reverse=True  # الأعلى score الأول
            )

            # ناخد أحسن top_k فقط
            top_docs = [doc for _, doc in scored_docs[:top_k]]

            logger.info(
                f"Reranking: {len(documents)} results → top {len(top_docs)} "
                f"(scores range: {min(scores):.3f} → {max(scores):.3f})"
            )

            return top_docs

        except Exception as e:
            logger.error(f"Reranking failed: {e}. Returning original results.")
            return documents[:top_k]


# ── Singleton ──────────────────────────────────────────────────────────────
_reranker_instance = None


def get_reranker(model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2") -> RerankerHelper:
    """رجع نفس الـ instance دايماً عشان منحملش الموديل أكتر من مرة."""
    global _reranker_instance
    if _reranker_instance is None:
        _reranker_instance = RerankerHelper(model_name=model_name)
    return _reranker_instance
