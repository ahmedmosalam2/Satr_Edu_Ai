"""
src/evaluation/arabic_rag_benchmark.py
───────────────────────────────────────
Arabic RAG Benchmark — أول benchmark للـ RAG على المحتوى التعليمي العربي.

الفكرة:
  - قارن 3 strategies مختلفة على نفس الأسئلة
  - وثّق النتائج في JSON جاهز للـ academic paper
  - استخدمه في مناقشة التخرج كـ proof of concept

Strategies:
  1. No RAG     — LLM بدون استرجاع
  2. Vector RAG — الـ system الحالي
  3. Adaptive   — vector RAG + reranking + chunking improvements
"""

import logging
import json
import time
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional
from datetime import datetime

logger = logging.getLogger("uvicorn.error")


@dataclass
class BenchmarkQuestion:
    """سؤال في الـ benchmark مع الإجابة الصحيحة."""
    question_id: str
    question_text: str
    expected_answer: str              # الإجابة المرجعية (ground truth)
    topic: str = ""
    difficulty: str = "medium"
    source_document: str = ""         # الكتاب/المستند المصدر


@dataclass
class StrategyResult:
    """نتيجة strategy معينة على سؤال واحد."""
    strategy_name: str
    question_id: str
    answer: str
    latency_ms: float
    sources_count: int
    faithfulness_score: float = 0.0
    relevancy_score: float = 0.0
    has_answer: bool = True
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class BenchmarkReport:
    """تقرير كامل للـ benchmark."""
    benchmark_id: str
    project_id: str
    run_date: str
    total_questions: int
    strategies_compared: List[str]
    results_per_strategy: Dict[str, dict] = field(default_factory=dict)
    per_question_results: List[dict] = field(default_factory=list)
    winner: str = ""
    summary: str = ""

    def to_dict(self) -> dict:
        return {
            "benchmark_id": self.benchmark_id,
            "project_id": self.project_id,
            "run_date": self.run_date,
            "total_questions": self.total_questions,
            "strategies_compared": self.strategies_compared,
            "results_per_strategy": self.results_per_strategy,
            "per_question_results": self.per_question_results,
            "winner": self.winner,
            "summary": self.summary,
        }


class ArabicRAGBenchmark:
    """
    Benchmark tool يقارن RAG strategies على المحتوى التعليمي العربي.

    Usage:
      benchmark = ArabicRAGBenchmark(nlp_controller, llm)
      questions = [BenchmarkQuestion(...), ...]
      report = await benchmark.run(project, questions)
    """

    def __init__(self, nlp_controller, llm_provider):
        self.nlp_controller = nlp_controller
        self.llm_provider = llm_provider

    async def run(
        self,
        project,
        questions: List[BenchmarkQuestion],
        strategies: List[str] = None,
    ) -> BenchmarkReport:
        """
        شغّل الـ benchmark على كل الأسئلة.

        Parameters:
          - project: الـ project المراد اختباره
          - questions: أسئلة الاختبار
          - strategies: ["no_rag", "vector_rag"] — default: كلهم

        Returns:
          - BenchmarkReport جاهز للنشر
        """
        if strategies is None:
            strategies = ["no_rag", "vector_rag"]

        benchmark_id = f"bench_{int(time.time())}"
        run_date = datetime.utcnow().isoformat()

        logger.info(
            f"[Benchmark] Starting {benchmark_id} | "
            f"{len(questions)} questions | strategies: {strategies}"
        )

        all_results: List[List[StrategyResult]] = []   # [question_idx][strategy_idx]

        for q in questions:
            question_results = []

            for strategy in strategies:
                result = await self._run_strategy(project, q, strategy)
                question_results.append(result)
                logger.info(
                    f"[Benchmark] Q{q.question_id} | {strategy} | "
                    f"latency={result.latency_ms:.0f}ms | "
                    f"faithfulness={result.faithfulness_score:.2f}"
                )

            all_results.append(question_results)

        # ── Aggregate Results ─────────────────────────────────────────────────
        strategy_aggregates = {}
        for s in strategies:
            strategy_results = [
                q_results[strategies.index(s)]
                for q_results in all_results
                if strategies.index(s) < len(q_results)
            ]

            n = len(strategy_results) or 1
            faithfulness_avg = sum(r.faithfulness_score for r in strategy_results) / n
            relevancy_avg    = sum(r.relevancy_score for r in strategy_results) / n
            latency_avg      = sum(r.latency_ms for r in strategy_results) / n
            error_rate       = sum(1 for r in strategy_results if r.error) / n

            strategy_aggregates[s] = {
                "faithfulness_avg": round(faithfulness_avg, 3),
                "relevancy_avg": round(relevancy_avg, 3),
                "latency_avg_ms": round(latency_avg, 1),
                "error_rate": round(error_rate, 3),
                "composite_score": round(
                    (faithfulness_avg * 0.5) + (relevancy_avg * 0.3) + ((1 - error_rate) * 0.2),
                    3
                ),
            }

        # ── Per-question results ──────────────────────────────────────────────
        per_question = []
        for q, q_results in zip(questions, all_results):
            per_question.append({
                "question_id": q.question_id,
                "question_text": q.question_text,
                "topic": q.topic,
                "difficulty": q.difficulty,
                "results": {r.strategy_name: r.to_dict() for r in q_results},
            })

        # ── Winner ───────────────────────────────────────────────────────────
        winner = max(
            strategy_aggregates,
            key=lambda s: strategy_aggregates[s]["composite_score"],
            default="",
        )

        # ── Summary text ─────────────────────────────────────────────────────
        summary = self._generate_summary(strategy_aggregates, winner, len(questions))

        report = BenchmarkReport(
            benchmark_id=benchmark_id,
            project_id=str(project.project_id),
            run_date=run_date,
            total_questions=len(questions),
            strategies_compared=strategies,
            results_per_strategy=strategy_aggregates,
            per_question_results=per_question,
            winner=winner,
            summary=summary,
        )

        logger.info(f"[Benchmark] Completed. Winner: {winner}")
        return report

    # ── Strategy Runners ──────────────────────────────────────────────────────

    async def _run_strategy(
        self,
        project,
        question: BenchmarkQuestion,
        strategy: str,
    ) -> StrategyResult:
        """شغّل strategy معينة على سؤال واحد."""
        t0 = time.time()

        try:
            if strategy == "no_rag":
                answer, sources_count = await self._run_no_rag(question.question_text)
            elif strategy == "vector_rag":
                answer, sources_count = await self._run_vector_rag(project, question.question_text)
            else:
                answer, sources_count = "", 0

            latency_ms = (time.time() - t0) * 1000

            # قياس الجودة
            faithfulness = self._estimate_faithfulness(answer, question.expected_answer)
            relevancy    = self._estimate_relevancy(answer, question.question_text)

            return StrategyResult(
                strategy_name=strategy,
                question_id=question.question_id,
                answer=answer,
                latency_ms=latency_ms,
                sources_count=sources_count,
                faithfulness_score=faithfulness,
                relevancy_score=relevancy,
                has_answer=bool(answer and answer.strip()),
            )

        except Exception as e:
            latency_ms = (time.time() - t0) * 1000
            logger.error(f"[Benchmark] Strategy {strategy} failed for Q{question.question_id}: {e}")
            return StrategyResult(
                strategy_name=strategy,
                question_id=question.question_id,
                answer="",
                latency_ms=latency_ms,
                sources_count=0,
                error=str(e),
            )

    async def _run_no_rag(self, query: str):
        """LLM بدون retrieval."""
        import inspect
        prompt = f"أجب على السؤال التالي من معرفتك العامة:\n\n{query}"
        result = self.llm_provider.generate_text(prompt=prompt, max_tokens=500)
        if inspect.isawaitable(result):
            answer = await result
        else:
            answer = result
        return answer or "", 0

    async def _run_vector_rag(self, project, query: str):
        """Vector RAG — النظام الحالي."""
        docs = await self.nlp_controller.search_vector_db_collection(
            project=project,
            text=query,
            limit=5,
        )
        if not docs:
            return "", 0

        context = "\n\n".join([
            doc.payload.get("text", "")[:500]
            for doc in docs
            if hasattr(doc, "payload")
        ])

        import inspect
        prompt = (
            f"أنت مساعد تعليمي. استخدم المعلومات التالية للإجابة:\n\n"
            f"{context}\n\nالسؤال: {query}"
        )
        result = self.llm_provider.generate_text(prompt=prompt, max_tokens=500)
        if inspect.isawaitable(result):
            answer = await result
        else:
            answer = result
        return answer or "", len(docs)

    # ── Quality Estimators ────────────────────────────────────────────────────

    @staticmethod
    def _estimate_faithfulness(answer: str, expected: str) -> float:
        """
        قياس مدى تطابق الإجابة مع الإجابة المرجعية.
        Lexical overlap (Jaccard similarity) — بدون LLM.
        """
        if not answer or not expected:
            return 0.0

        stop_words = {"في", "من", "على", "هو", "هي", "أن", "إن", "the", "is", "a", "of", "to"}
        answer_words  = set(answer.lower().split()) - stop_words
        expected_words = set(expected.lower().split()) - stop_words

        if not answer_words or not expected_words:
            return 0.0

        intersection = answer_words & expected_words
        union = answer_words | expected_words
        return round(len(intersection) / len(union), 4) if union else 0.0

    @staticmethod
    def _estimate_relevancy(answer: str, question: str) -> float:
        """
        قياس مدى صلة الإجابة بالسؤال.
        """
        if not answer or not question:
            return 0.0

        q_words = set(question.lower().split())
        a_words  = set(answer.lower().split())
        overlap  = q_words & a_words

        # نسبة كلمات السؤال الموجودة في الإجابة
        return round(len(overlap) / len(q_words), 4) if q_words else 0.0

    # ── Summary Generator ─────────────────────────────────────────────────────

    @staticmethod
    def _generate_summary(aggregates: Dict, winner: str, num_questions: int) -> str:
        lines = [
            f"Benchmark completed on {num_questions} questions.",
            "",
        ]
        for strategy, metrics in aggregates.items():
            lines.append(
                f"{strategy}: faithfulness={metrics['faithfulness_avg']:.3f}, "
                f"relevancy={metrics['relevancy_avg']:.3f}, "
                f"latency={metrics['latency_avg_ms']:.0f}ms, "
                f"composite={metrics['composite_score']:.3f}"
            )

        if winner:
            winner_score = aggregates.get(winner, {}).get("composite_score", 0)
            lines.append(f"\nWinner: {winner} (score={winner_score:.3f})")

        return "\n".join(lines)
