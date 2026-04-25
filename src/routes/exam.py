import uuid
import logging
from datetime import datetime
from typing import List

from fastapi import APIRouter, Request, HTTPException, Depends, status
from fastapi.responses import JSONResponse

from src.models.ExamModel import ExamModel
from src.models.ExamResultModel import ExamResultModel
from src.models.scheme_db.exam import Exam
from src.models.scheme_db.question import Question
from src.models.scheme_db.student_answer import StudentAnswer
from src.models.scheme_db.exam_result import ExamResult
from src.models.enums.ExamStatus import ExamStatus
from src.models.enums.QuestionType import QuestionType
from src.controllers.AIController import AIController
from src.helpers.auth import get_current_user, require_roles
from src.models.enums.UserRole import UserRole
from src.routes.schemes.exam import (
    ExamCreateRequest,
    ExamCreateResponse,
    ExamInfoResponse,
    QuestionResponse,
    ApproveExamResponse,
    SubmitExamRequest,
    SubmitExamResponse,
    AnswerFeedback,
    StudentResultResponse,
)

logger = logging.getLogger("uvicorn.error")

exam_router = APIRouter(
    prefix="/api/v1/exam",
    tags=["Exam"],
)

_ai_controller = None

def get_ai_controller() -> AIController:
    global _ai_controller
    if _ai_controller is None:
        _ai_controller = AIController()
    return _ai_controller


# ─── Helper ───────────────────────────────────────────────────────────────────

async def _fetch_project_content(request: Request, project_id: str) -> str:
    """Fetch all chunks from MongoDB for a project and concatenate."""
    try:
        from src.models.ChunkModel import ChunkModel
        chunk_model = ChunkModel(client=request.app.client, project_id=project_id)
        all_text = []
        page = 1
        while True:
            chunks = await chunk_model.get_project_chunks(
                project_id=project_id, page=page, page_size=100
            )
            if not chunks:
                break
            all_text.extend([c.chunk_text for c in chunks if c.chunk_text])
            page += 1
        return "\n\n".join(all_text)
    except Exception as e:
        logger.error(f"Error fetching project chunks: {e}")
        return ""


def _parse_ai_questions(ai_result: dict, exam_id: str) -> List[Question]:
    """Convert raw AI output to Question objects."""
    questions = []
    for q in ai_result.get("questions", []):
        q_id = str(uuid.uuid4())
        questions.append(Question(
            question_id=q_id,
            exam_id=exam_id,
            question_text=q.get("question_text", ""),
            question_type=q.get("question_type", QuestionType.MCQ.value),
            options=q.get("options") or None,
            correct_answer=q.get("correct_answer", ""),
            points=1.0,
            chunk_ref=q.get("chunk_ref", None),
        ))
    return questions


# ─── 1. Teacher: Create Exam (Draft) ─────────────────────────────────────────

@exam_router.post("/create", response_model=ExamCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_exam(
    request: Request,
    body: ExamCreateRequest,
    current_user: dict = Depends(require_roles(UserRole.TEACHER.value)),
):
    """
    Teacher generates an AI exam from project content.
    Exam is saved as DRAFT — not visible to students yet.
    """
    # 1. Fetch content from MongoDB chunks
    content = await _fetch_project_content(request, body.project_id)
    if not content or len(content.strip()) < 50:
        raise HTTPException(
            status_code=400,
            detail="No content found for this project. Upload and process files first."
        )

    # 2. Generate questions via AI
    ai = get_ai_controller()
    ai_result = await ai.generate_exam_questions(
        content=content,
        num_questions=body.num_questions,
        difficulty=body.difficulty,
        question_types=body.question_types,
    )

    if not ai_result.get("questions"):
        raise HTTPException(status_code=500, detail=ai_result.get("error", "AI failed to generate questions"))

    # 3. Save exam to MongoDB
    exam_id = str(uuid.uuid4())
    questions = _parse_ai_questions(ai_result, exam_id)
    question_ids = [q.question_id for q in questions]

    exam = Exam(
        exam_id=exam_id,
        exam_title=body.exam_title,
        project_id=body.project_id,
        teacher_id=current_user["user_id"],
        status=ExamStatus.DRAFT.value,
        question_ids=question_ids,
        difficulty=body.difficulty,
        num_questions=len(questions),
        created_at=datetime.now(),
    )

    exam_model = ExamModel(client=request.app.client)
    await exam_model.create_exam(exam)
    await exam_model.insert_questions(questions)

    logger.info(f"Exam created: {exam_id} by teacher {current_user['user_id']} with {len(questions)} questions")

    return ExamCreateResponse(
        exam_id=exam_id,
        exam_title=body.exam_title,
        status=ExamStatus.DRAFT.value,
        questions=[
            QuestionResponse(
                question_id=q.question_id,
                question_text=q.question_text,
                question_type=q.question_type,
                options=q.options,
                points=q.points,
            ) for q in questions
        ],
        message=f"تم إنشاء الامتحان كمسودة بنجاح ({len(questions)} سؤال). راجع الأسئلة ثم اعتمده.",
    )


# ─── 2. Get Exam Info ─────────────────────────────────────────────────────────

@exam_router.get("/{exam_id}", response_model=ExamInfoResponse)
async def get_exam(
    exam_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """
    Get exam details.
    - Students can only see APPROVED exams (correct_answer hidden).
    - Teachers can see their own drafts and approved exams.
    """
    exam_model = ExamModel(client=request.app.client)
    exam = await exam_model.get_exam(exam_id)

    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")

    is_student = current_user.get("user_role") == UserRole.STUDENT.value
    is_teacher = current_user.get("user_role") == UserRole.TEACHER.value

    # Students can only see approved exams
    if is_student and exam.status != ExamStatus.APPROVED.value:
        raise HTTPException(status_code=403, detail="This exam is not available yet")

    # Teachers can only see their own exams
    if is_teacher and exam.teacher_id != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="Access denied")

    questions = await exam_model.get_questions_by_exam(exam_id)

    # Hide correct answers from students
    question_responses = []
    for q in questions:
        question_responses.append(QuestionResponse(
            question_id=q.question_id,
            question_text=q.question_text,
            question_type=q.question_type,
            options=q.options,
            points=q.points,
        ))

    return ExamInfoResponse(
        exam_id=exam.exam_id,
        exam_title=exam.exam_title,
        project_id=exam.project_id,
        teacher_id=exam.teacher_id,
        status=exam.status,
        difficulty=exam.difficulty,
        num_questions=exam.num_questions,
        questions=question_responses,
    )


# ─── 6. Student: List Available Exams for a Project ─────────────────────────

@exam_router.get("/student/project/{project_id}")
async def student_list_exams(
    project_id: str,
    request: Request,
    current_user: dict = Depends(require_roles(UserRole.STUDENT.value)),
):
    """Student: عرض الامتحانات المتاحة (Approved فقط) لمشروع معين."""
    exam_model = ExamModel(client=request.app.client)
    exams = await exam_model.list_approved_exams_by_project(project_id)

    return JSONResponse(content={
        "status": "success",
        "count": len(exams),
        "exams": [
            {
                "exam_id": e.exam_id,
                "exam_title": e.exam_title,
                "difficulty": e.difficulty,
                "num_questions": e.num_questions,
                "approved_at": e.approved_at.isoformat() if e.approved_at else None,
            }
            for e in exams
        ]
    })


# ─── 7. Student: My Results History ──────────────────────────────────────────

@exam_router.get("/student/results")
async def student_my_results(
    request: Request,
    current_user: dict = Depends(require_roles(UserRole.STUDENT.value)),
):
    """Student: عرض كل نتائجه في كل الامتحانات."""
    student_id = current_user["user_id"]
    db = request.app.client["Satr-Edu"]
    cursor = db["exam_results"].find({"student_id": student_id})
    results = []
    async for doc in cursor:
        doc.pop("_id", None)
        if "submitted_at" in doc and hasattr(doc["submitted_at"], "isoformat"):
            doc["submitted_at"] = doc["submitted_at"].isoformat()
        results.append(doc)

    return JSONResponse(content={
        "status": "success",
        "student_id": student_id,
        "total_exams": len(results),
        "results": results
    })


# ─── 8. Teacher: Delete Exam ──────────────────────────────────────────────────

@exam_router.delete("/{exam_id}")
async def delete_exam(
    exam_id: str,
    request: Request,
    current_user: dict = Depends(require_roles(UserRole.TEACHER.value)),
):
    """Teacher: حذف امتحان مسودة. لا يمكن حذف الامتحانات المعتمدة."""
    exam_model = ExamModel(client=request.app.client)
    exam = await exam_model.get_exam(exam_id)

    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")

    if exam.teacher_id != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="Only the exam creator can delete it")

    if exam.status == ExamStatus.APPROVED.value:
        raise HTTPException(status_code=400, detail="Cannot delete an approved exam. It may have student submissions.")

    # Delete questions first
    db = request.app.client["Satr-Edu"]
    await db["questions"].delete_many({"exam_id": exam_id})
    await db["exams"].delete_one({"exam_id": exam_id})

    logger.info(f"Exam {exam_id} deleted by teacher {current_user['user_id']}")

    return JSONResponse(content={
        "status": "success",
        "message": f"Exam '{exam.exam_title}' deleted successfully",
        "exam_id": exam_id
    })


# ─── 3. Teacher: List Exams by Project ───────────────────────────────────────

@exam_router.get("/project/{project_id}")
async def list_exams_by_project(
    project_id: str,
    request: Request,
    current_user: dict = Depends(require_roles(UserRole.TEACHER.value)),
):
    """Teacher: List all exams (draft + approved) for a project."""
    exam_model = ExamModel(client=request.app.client)
    exams = await exam_model.list_exams_by_project(project_id)

    return JSONResponse(content={
        "status": "success",
        "count": len(exams),
        "exams": [
            {
                "exam_id": e.exam_id,
                "exam_title": e.exam_title,
                "status": e.status,
                "difficulty": e.difficulty,
                "num_questions": e.num_questions,
                "created_at": e.created_at.isoformat(),
                "approved_at": e.approved_at.isoformat() if e.approved_at else None,
            }
            for e in exams
        ]
    })


# ─── 4. Teacher: Approve Exam ─────────────────────────────────────────────────

@exam_router.put("/{exam_id}/approve", response_model=ApproveExamResponse)
async def approve_exam(
    exam_id: str,
    request: Request,
    current_user: dict = Depends(require_roles(UserRole.TEACHER.value)),
):
    """
    Teacher approves a DRAFT exam → becomes visible to students.
    Only the teacher who created the exam can approve it.
    """
    exam_model = ExamModel(client=request.app.client)
    exam = await exam_model.get_exam(exam_id)

    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")

    if exam.teacher_id != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="Only the exam creator can approve it")

    if exam.status == ExamStatus.APPROVED.value:
        raise HTTPException(status_code=400, detail="Exam is already approved")

    success = await exam_model.approve_exam(exam_id, current_user["user_id"])
    if not success:
        raise HTTPException(status_code=500, detail="Failed to approve exam")

    logger.info(f"Exam {exam_id} approved by teacher {current_user['user_id']}")

    return ApproveExamResponse(
        exam_id=exam_id,
        status=ExamStatus.APPROVED.value,
        message="تم اعتماد الامتحان. أصبح متاحاً للطلاب الآن.",
    )


# ─── 5. Student: Submit Exam + Auto-Grade ────────────────────────────────────

@exam_router.post("/{exam_id}/submit", response_model=SubmitExamResponse)
async def submit_exam(
    exam_id: str,
    request: Request,
    body: SubmitExamRequest,
    current_user: dict = Depends(require_roles(UserRole.STUDENT.value)),
):
    """
    Student submits answers → system auto-grades:
    - MCQ / TRUE_FALSE: exact match
    - ESSAY: AI-based grading via existing AIController.grade_essay()
    Returns score, feedback, and weak_chunks for lecture highlighting.
    """
    student_id = current_user["user_id"]

    exam_model = ExamModel(client=request.app.client)
    result_model = ExamResultModel(client=request.app.client)

    # 1. Check exam exists and is approved
    exam = await exam_model.get_exam(exam_id)
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
    if exam.status != ExamStatus.APPROVED.value:
        raise HTTPException(status_code=403, detail="This exam is not available")

    # 2. Prevent double submission
    if await result_model.already_submitted(exam_id, student_id):
        raise HTTPException(status_code=409, detail="You have already submitted this exam")

    # 3. Get all questions
    questions = await exam_model.get_questions_by_exam(exam_id)
    questions_map = {q.question_id: q for q in questions}

    # 4. Grade each answer
    ai = get_ai_controller()
    student_answers: List[StudentAnswer] = []
    feedbacks: List[AnswerFeedback] = []
    total_score = 0.0
    max_score = 0.0
    weak_chunks: List[str] = []

    for answer_item in body.answers:
        q = questions_map.get(answer_item.question_id)
        if not q:
            continue

        max_score += q.points
        is_correct = None
        score = 0.0
        ai_feedback = None

        q_type = q.question_type.upper()

        if q_type in [QuestionType.MCQ.value, QuestionType.TRUE_FALSE.value]:
            # Exact match (case-insensitive, stripped)
            is_correct = answer_item.student_answer.strip().upper() == q.correct_answer.strip().upper()
            score = q.points if is_correct else 0.0

        elif q_type == QuestionType.ESSAY.value:
            # AI grading
            grading = await ai.grade_essay(
                question=q.question_text,
                model_answer=q.correct_answer,
                student_answer=answer_item.student_answer,
                max_score=q.points,
            )
            score = grading.get("score", 0.0)
            ai_feedback = grading.get("feedback", "")
            is_correct = score >= (q.points * 0.5)   # نجح لو حصل على 50%+

        total_score += score

        # Track weak chunks (wrong answers with a chunk reference)
        if not is_correct and q.chunk_ref:
            weak_chunks.append(q.chunk_ref)

        # Save individual answer
        student_answers.append(StudentAnswer(
            answer_id=str(uuid.uuid4()),
            exam_id=exam_id,
            student_id=student_id,
            question_id=q.question_id,
            student_answer=answer_item.student_answer,
            is_correct=is_correct,
            score=score,
            feedback=ai_feedback,
            submitted_at=datetime.now(),
        ))

        feedbacks.append(AnswerFeedback(
            question_id=q.question_id,
            question_text=q.question_text,
            student_answer=answer_item.student_answer,
            correct_answer=q.correct_answer,
            is_correct=is_correct,
            score=score,
            feedback=ai_feedback,
        ))

    # 5. Calculate percentage
    percentage = round((total_score / max_score * 100), 2) if max_score > 0 else 0.0

    # 6. Save answers + result to MongoDB
    await result_model.save_answers(student_answers)
    exam_result = ExamResult(
        result_id=str(uuid.uuid4()),
        exam_id=exam_id,
        student_id=student_id,
        total_score=total_score,
        max_score=max_score,
        percentage=percentage,
        weak_chunks=list(set(weak_chunks)),
        submitted_at=datetime.now(),
    )
    await result_model.save_result(exam_result)

    logger.info(f"Student {student_id} submitted exam {exam_id}: {percentage}%")

    return SubmitExamResponse(
        exam_id=exam_id,
        student_id=student_id,
        total_score=total_score,
        max_score=max_score,
        percentage=percentage,
        per_question=feedbacks,
        weak_chunks=exam_result.weak_chunks,
        message=f"تم تسليم الامتحان! حصلت على {total_score}/{max_score} ({percentage}%)",
    )


# ─── 6. Get Student Result ────────────────────────────────────────────────────

@exam_router.get("/{exam_id}/results/{student_id}", response_model=StudentResultResponse)
async def get_student_result(
    exam_id: str,
    student_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """
    Get a student's exam result.
    Students can only see their own result.
    Teachers can see any student's result.
    """
    role = current_user.get("user_role")
    uid = current_user.get("user_id")

    if role == UserRole.STUDENT.value and uid != student_id:
        raise HTTPException(status_code=403, detail="You can only view your own results")

    result_model = ExamResultModel(client=request.app.client)
    result = await result_model.get_result(exam_id, student_id)

    if not result:
        raise HTTPException(status_code=404, detail="Result not found. Student may not have submitted yet.")

    return StudentResultResponse(
        student_id=result.student_id,
        total_score=result.total_score,
        max_score=result.max_score,
        percentage=result.percentage,
        weak_chunks=result.weak_chunks,
        submitted_at=result.submitted_at.isoformat(),
    )


# ─── 7. Teacher: All Results for an Exam ───────────────────────────────────

@exam_router.get("/{exam_id}/results")
async def get_all_results(
    exam_id: str,
    request: Request,
    current_user: dict = Depends(require_roles(UserRole.TEACHER.value)),
):
    """Teacher: Get all student results for an exam."""
    exam_model = ExamModel(client=request.app.client)
    exam = await exam_model.get_exam(exam_id)

    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")

    if exam.teacher_id != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="Access denied")

    result_model = ExamResultModel(client=request.app.client)
    results = await result_model.get_all_results(exam_id)

    return JSONResponse(content={
        "status": "success",
        "exam_id": exam_id,
        "exam_title": exam.exam_title,
        "total_submissions": len(results),
        "results": [
            {
                "student_id": r.student_id,
                "total_score": r.total_score,
                "max_score": r.max_score,
                "percentage": r.percentage,
                "weak_chunks": r.weak_chunks,
                "submitted_at": r.submitted_at.isoformat(),
            }
            for r in results
        ]
    })
