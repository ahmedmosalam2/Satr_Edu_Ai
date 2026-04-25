import logging
from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import JSONResponse
from src.models.ExamResultModel import ExamResultModel
from src.models.ExamModel import ExamModel
from src.controllers.AnalyticsController import AnalyticsController
from src.helpers.auth import get_current_user, require_roles
from src.models.enums.UserRole import UserRole

logger = logging.getLogger("uvicorn.error")

analytics_router = APIRouter(
    prefix="/api/v1/analytics",
    tags=["Analytics"],
)

_analytics_controller = None

def get_analytics_controller() -> AnalyticsController:
    global _analytics_controller
    if _analytics_controller is None:
        _analytics_controller = AnalyticsController()
    return _analytics_controller


# ─── 1. Student Performance Summary ──────────────────────────────────────────

@analytics_router.get("/student/{student_id}")
async def get_student_analytics(
    student_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """
    AI-powered analysis of a student's performance across ALL their exam results.

    - Students can only view their own analytics
    - Teachers and Operations can view any student
    """
    student_id = student_id.strip()
    role = current_user.get("user_role")
    uid  = current_user.get("user_id")

    if role == UserRole.STUDENT.value and uid != student_id:
        raise HTTPException(status_code=403, detail="يمكنك عرض تحليل أدائك الشخصي فقط")

    result_model = ExamResultModel(client=request.app.client)

    # Gather all exam results for this student across all exams
    # We search by student_id — collect from all exam collections
    from src.models.BaseDataModel import BaseDataModel
    db = request.app.client["Satr-Edu"]
    cursor = db["exam_results"].find({"student_id": student_id})
    raw_results = []
    async for doc in cursor:
        doc.pop("_id", None)
        # Convert datetime to string for JSON
        if "submitted_at" in doc and hasattr(doc["submitted_at"], "isoformat"):
            doc["submitted_at"] = doc["submitted_at"].isoformat()
        raw_results.append(doc)

    if not raw_results:
        return JSONResponse(content={
            "status": "no_data",
            "student_id": student_id,
            "message": "لا توجد نتائج امتحانات لهذا الطالب بعد",
            "total_exams": 0,
        })

    # Run AI analysis
    analytics = get_analytics_controller()
    analysis = analytics.analyze_student_performance(raw_results)

    return JSONResponse(content={
        "status": "success",
        "student_id": student_id,
        "total_exams": len(raw_results),
        "analysis": analysis,
    })


# ─── 2. Exam-Level Analytics (Teacher) ───────────────────────────────────────

@analytics_router.get("/exam/{exam_id}")
async def get_exam_analytics(
    exam_id: str,
    request: Request,
    current_user: dict = Depends(require_roles(UserRole.TEACHER.value)),
):

    exam_model  = ExamModel(client=request.app.client)
    result_model = ExamResultModel(client=request.app.client)

    exam = await exam_model.get_exam(exam_id)
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")

    if exam.teacher_id != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="Access denied")

    all_results = await result_model.get_all_results(exam_id)

    if not all_results:
        return JSONResponse(content={
            "status": "no_data",
            "exam_id": exam_id,
            "exam_title": exam.exam_title,
            "message": "لم يتقدم أي طالب لهذا الامتحان بعد",
            "total_submissions": 0,
        })

    # Serialize results for the analytics controller
    raw_results = [
        {
            "student_id": r.student_id,
            "total_score": r.total_score,
            "max_score": r.max_score,
            "percentage": r.percentage,
            "weak_chunks": r.weak_chunks,
            "submitted_at": r.submitted_at.isoformat(),
        }
        for r in all_results
    ]

    analytics = get_analytics_controller()
    analysis = analytics.analyze_exam_performance(raw_results, exam_title=exam.exam_title)

    return JSONResponse(content={
        "status": "success",
        "exam_id": exam_id,
        "exam_title": exam.exam_title,
        "total_submissions": len(all_results),
        "analysis": analysis,
    }
)
