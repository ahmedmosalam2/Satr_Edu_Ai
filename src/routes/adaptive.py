from fastapi import APIRouter, Request, HTTPException, Depends, Query
from fastapi.responses import JSONResponse
import logging
from src.helpers.auth import get_current_user, require_roles
from src.models.enums.UserRole import UserRole
from src.models.ExamResultModel import ExamResultModel
from src.models.ExamModel import ExamModel
from src.helpers.nlp_clients import get_generation_client

logger = logging.getLogger("uvicorn.error")

adaptive_router = APIRouter(
    prefix="/api/v1/adaptive",
    tags=["Adaptive Learning"],
)

EXPLAIN_QUESTIONS_PROMPT = """You are an expert, friendly AI tutor.
A student recently took an exam and answered the following questions incorrectly.
For each question, explain WHY their answer was wrong and WHY the correct answer is right. Keep it encouraging and easy to understand.

QUESTIONS THEY GOT WRONG:
{wrong_questions_text}

Provide your response in clear markdown format.
Language: Reply in the same language the questions are written in.
"""

RECOMMENDATIONS_PROMPT = """You are an expert educational AI advisor.
A student has the following performance data across their exams:

PERFORMANCE DATA:
{performance_data}

Based on this data:
1. Identify their top 3 weak areas
2. Recommend 3-5 specific study actions they should take
3. Suggest resources or practice strategies for each weak area
4. Give an encouraging closing message

Reply in clear markdown. Match the language of the content (Arabic or English).
"""

STUDY_PLAN_PROMPT = """You are an expert educational AI coach.
A student needs a personalized study plan based on their exam history:

STUDENT PERFORMANCE SUMMARY:
{summary}

Create a structured 2-week study plan that:
1. Prioritizes their weakest topics
2. Allocates realistic daily study time (30-90 min/day)
3. Includes review sessions for topics they did well in
4. Ends with a mock review day

Format as a clear weekly schedule in markdown. Match the language of the content.
"""


@adaptive_router.get("/explain/{exam_id}")
async def explain_weaknesses(
    exam_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    student_id = current_user["user_id"]

    result_model = ExamResultModel(client=request.app.client)
    exam_model = ExamModel(client=request.app.client)

    result = await result_model.get_result(exam_id, student_id)
    if not result:
        raise HTTPException(status_code=404, detail="Exam result not found. You need to take and submit the exam first.")

    questions = await exam_model.get_questions_by_exam(exam_id)
    questions_map = {q.question_id: q for q in questions}

    db = request.app.client["Satr-Edu"]
    answers_cursor = db["student_answers"].find({
        "exam_id": exam_id,
        "student_id": student_id,
        "is_correct": False
    })

    wrong_answers = []
    async for doc in answers_cursor:
        wrong_answers.append(doc)

    if not wrong_answers:
        return JSONResponse(content={
            "status": "success",
            "message": "You got a perfect score! No explanations needed.",
            "explanation": "Excellent job! You answered all questions correctly."
        })

    wrong_questions_text = ""
    for i, ans in enumerate(wrong_answers, 1):
        q = questions_map.get(ans["question_id"])
        if q:
            wrong_questions_text += f"Question {i}: {q.question_text}\n"
            wrong_questions_text += f"Options: {', '.join(q.options) if q.options else 'None'}\n"
            wrong_questions_text += f"Student's Answer: {ans.get('student_answer', 'No answer')}\n"
            wrong_questions_text += f"Correct Answer: {q.correct_answer}\n\n"

    prompt = EXPLAIN_QUESTIONS_PROMPT.format(wrong_questions_text=wrong_questions_text)

    try:
        generation_client = get_generation_client()
        explanation = await generation_client.generate_text(
            prompt=prompt,
            max_tokens=1500
        )
    except Exception as e:
        logger.error(f"Error generating explanation: {e}")
        explanation = "عذراً، حدث خطأ أثناء محاولة إنشاء الشرح. يرجى المحاولة لاحقاً."

    return JSONResponse(content={
        "status": "success",
        "exam_id": exam_id,
        "wrong_answers_count": len(wrong_answers),
        "explanation": explanation
    })


@adaptive_router.get("/recommendations/{student_id}")
async def get_recommendations(
    student_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    role = current_user.get("user_role")
    uid = current_user.get("user_id")

    if role == UserRole.STUDENT.value and uid != student_id:
        raise HTTPException(status_code=403, detail="يمكنك عرض توصياتك الشخصية فقط")

    db = request.app.client["Satr-Edu"]
    cursor = db["exam_results"].find({"student_id": student_id})

    raw_results = []
    async for doc in cursor:
        doc.pop("_id", None)
        if "submitted_at" in doc and hasattr(doc["submitted_at"], "isoformat"):
            doc["submitted_at"] = doc["submitted_at"].isoformat()
        raw_results.append(doc)

    if not raw_results:
        return JSONResponse(content={
            "status": "no_data",
            "student_id": student_id,
            "message": "لا توجد نتائج امتحانات بعد. أكمل بعض الامتحانات أولاً.",
            "recommendations": None
        })

    avg_score = sum(r.get("percentage", 0) for r in raw_results) / len(raw_results)
    weak_chunks = []
    for r in raw_results:
        weak_chunks.extend(r.get("weak_chunks", []))

    performance_data = f"Total Exams Taken: {len(raw_results)}\n"
    performance_data += f"Average Score: {avg_score:.1f}%\n"
    performance_data += f"Best Score: {max(r.get('percentage', 0) for r in raw_results):.1f}%\n"
    performance_data += f"Lowest Score: {min(r.get('percentage', 0) for r in raw_results):.1f}%\n"
    if weak_chunks:
        unique_weak = list(set(weak_chunks))[:10]
        performance_data += f"Recurring Weak Topics (chunk refs): {', '.join(unique_weak)}\n"

    prompt = RECOMMENDATIONS_PROMPT.format(performance_data=performance_data)

    try:
        generation_client = get_generation_client()
        recommendations = await generation_client.generate_text(
            prompt=prompt,
            max_tokens=1200
        )
    except Exception as e:
        logger.error(f"Error generating recommendations: {e}")
        recommendations = "عذراً، حدث خطأ أثناء إنشاء التوصيات. يرجى المحاولة لاحقاً."

    return JSONResponse(content={
        "status": "success",
        "student_id": student_id,
        "total_exams": len(raw_results),
        "average_score": round(avg_score, 2),
        "recommendations": recommendations
    })


@adaptive_router.get("/study-plan/{student_id}")
async def get_study_plan(
    student_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    role = current_user.get("user_role")
    uid = current_user.get("user_id")

    if role == UserRole.STUDENT.value and uid != student_id:
        raise HTTPException(status_code=403, detail="يمكنك عرض خطتك الدراسية الشخصية فقط")

    db = request.app.client["Satr-Edu"]
    cursor = db["exam_results"].find({"student_id": student_id})

    raw_results = []
    async for doc in cursor:
        doc.pop("_id", None)
        if "submitted_at" in doc and hasattr(doc["submitted_at"], "isoformat"):
            doc["submitted_at"] = doc["submitted_at"].isoformat()
        raw_results.append(doc)

    if not raw_results:
        return JSONResponse(content={
            "status": "no_data",
            "student_id": student_id,
            "message": "لا توجد بيانات كافية لإنشاء خطة دراسية. أكمل بعض الامتحانات أولاً.",
            "study_plan": None
        })

    avg_score = sum(r.get("percentage", 0) for r in raw_results) / len(raw_results)
    weak_chunks = []
    for r in raw_results:
        weak_chunks.extend(r.get("weak_chunks", []))

    summary = f"Exams completed: {len(raw_results)}\n"
    summary += f"Average performance: {avg_score:.1f}%\n"
    summary += f"Performance trend: {'Improving' if len(raw_results) > 1 and raw_results[-1].get('percentage', 0) > raw_results[0].get('percentage', 0) else 'Needs focus'}\n"
    if weak_chunks:
        summary += f"Weak areas to focus on: {', '.join(list(set(weak_chunks))[:8])}\n"
    if avg_score >= 80:
        summary += "Overall status: Strong performer — needs maintenance and challenge\n"
    elif avg_score >= 60:
        summary += "Overall status: Average performer — needs targeted improvement\n"
    else:
        summary += "Overall status: Needs significant support — focus on fundamentals\n"

    prompt = STUDY_PLAN_PROMPT.format(summary=summary)

    try:
        generation_client = get_generation_client()
        study_plan = await generation_client.generate_text(
            prompt=prompt,
            max_tokens=1500
        )
    except Exception as e:
        logger.error(f"Error generating study plan: {e}")
        study_plan = "عذراً، حدث خطأ أثناء إنشاء الخطة الدراسية. يرجى المحاولة لاحقاً."

    return JSONResponse(content={
        "status": "success",
        "student_id": student_id,
        "total_exams": len(raw_results),
        "average_score": round(avg_score, 2),
        "study_plan": study_plan
    })


@adaptive_router.get("/progress/{student_id}")
async def get_student_progress(
    student_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    role = current_user.get("user_role")
    uid = current_user.get("user_id")

    if role == UserRole.STUDENT.value and uid != student_id:
        raise HTTPException(status_code=403, detail="يمكنك عرض تقدمك الشخصي فقط")

    db = request.app.client["Satr-Edu"]
    cursor = db["exam_results"].find(
        {"student_id": student_id},
        sort=[("submitted_at", 1)]
    )

    raw_results = []
    async for doc in cursor:
        doc.pop("_id", None)
        if "submitted_at" in doc and hasattr(doc["submitted_at"], "isoformat"):
            doc["submitted_at"] = doc["submitted_at"].isoformat()
        raw_results.append(doc)

    if not raw_results:
        return JSONResponse(content={
            "status": "no_data",
            "student_id": student_id,
            "message": "لا توجد نتائج بعد.",
            "progress": None
        })

    scores = [r.get("percentage", 0) for r in raw_results]
    avg = sum(scores) / len(scores)
    trend = "stable"
    if len(scores) >= 2:
        recent_avg = sum(scores[-3:]) / len(scores[-3:])
        old_avg = sum(scores[:3]) / len(scores[:3])
        if recent_avg > old_avg + 5:
            trend = "improving"
        elif recent_avg < old_avg - 5:
            trend = "declining"

    all_weak = []
    for r in raw_results:
        all_weak.extend(r.get("weak_chunks", []))

    from collections import Counter
    weak_freq = Counter(all_weak).most_common(5)

    progress_timeline = [
        {
            "exam_id": r.get("exam_id"),
            "percentage": r.get("percentage"),
            "submitted_at": r.get("submitted_at"),
        }
        for r in raw_results
    ]

    return JSONResponse(content={
        "status": "success",
        "student_id": student_id,
        "summary": {
            "total_exams": len(raw_results),
            "average_score": round(avg, 2),
            "best_score": round(max(scores), 2),
            "lowest_score": round(min(scores), 2),
            "trend": trend,
            "top_weak_areas": [{"topic": k, "frequency": v} for k, v in weak_freq],
        },
        "timeline": progress_timeline
    })


# ── [NEW] Adaptive Difficulty Engine endpoints ────────────────────────────────

from pydantic import BaseModel
from typing import Optional as OptType


class AttemptRequest(BaseModel):
    student_id: str
    question_id: str
    topic: str
    difficulty: str = "medium"    # easy / medium / hard
    is_correct: bool
    time_taken_sec: float = 0.0


class NextQuestionRequest(BaseModel):
    student_id: str
    topic: str


@adaptive_router.post("/engine/record-attempt")
async def record_attempt(body: AttemptRequest):
    """
    سجّل إجابة الطالب وحدّث مستوى إتقانه في الموضوع.

    يرجع:
      - next_difficulty: الصعوبة التالية للطالب في نفس الموضوع
      - mastery_score: مستوى الإتقان الحالي (0 → 1)
      - reasoning: تفسير إنساني لقرار الـ engine
    """
    from src.engine.adaptive_difficulty import get_adaptive_engine, QuestionAttempt

    engine = get_adaptive_engine()

    attempt = QuestionAttempt(
        question_id=body.question_id,
        topic=body.topic,
        difficulty=body.difficulty,
        is_correct=body.is_correct,
        time_taken_sec=body.time_taken_sec,
    )

    updated_mastery = engine.process_attempt(body.student_id, attempt)

    return {
        "status": "success",
        "student_id": body.student_id,
        "topic": body.topic,
        "result": "correct" if body.is_correct else "incorrect",
        "mastery": updated_mastery.to_dict(),
        "next_difficulty": updated_mastery.current_difficulty,
        "reasoning": updated_mastery.mastery_level,
    }


@adaptive_router.post("/engine/next-question")
async def get_next_question_difficulty(body: NextQuestionRequest):
    """
    اجيب الصعوبة المناسبة للسؤال التالي للطالب في موضوع معين.

    يُستخدم قبل توليد السؤال لتحديد مستوى الصعوبة.
    """
    from src.engine.adaptive_difficulty import get_adaptive_engine

    engine = get_adaptive_engine()
    params = engine.get_next_question_params(body.student_id, body.topic)

    return {
        "status": "success",
        "student_id": body.student_id,
        "topic": body.topic,
        **params,
    }


@adaptive_router.get("/engine/dashboard/{student_id}")
async def get_adaptive_dashboard(
    student_id: str,
    request: Request,
):
    """
    لوحة التحكم الكاملة لمستوى الطالب في كل المواضيع.

    يرجع:
      - overall_mastery: مستوى إتقان إجمالي
      - weakest_topics: أضعف 3 مواضيع
      - strongest_topics: أقوى 3 مواضيع
      - due_for_review: مواضيع حان وقت مراجعتها (Spaced Repetition)
      - topics: تفاصيل كل موضوع
    """
    from src.engine.adaptive_difficulty import get_adaptive_engine

    # تحميل بيانات الطالب من DB أول مرة
    db = request.app.client["Satr-Edu"]
    cursor = db["exam_results"].find({"student_id": student_id})

    raw_results = []
    async for doc in cursor:
        doc.pop("_id", None)
        raw_results.append(doc)

    engine = get_adaptive_engine()

    # بناء الـ profile لو مش موجود
    if raw_results and student_id not in engine._student_profiles:
        engine.load_from_exam_results(student_id, raw_results)

    dashboard = engine.get_student_dashboard(student_id)

    return {
        "status": "success",
        **dashboard,
    }
