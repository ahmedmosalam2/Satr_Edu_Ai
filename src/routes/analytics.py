import logging
from fastapi import APIRouter, Request, HTTPException, Depends, Query
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


@analytics_router.get("/student/{student_id}")
async def get_student_analytics(
    student_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    student_id = student_id.strip()
    role = current_user.get("user_role")
    uid  = current_user.get("user_id")

    if role == UserRole.STUDENT.value and uid != student_id:
        raise HTTPException(status_code=403, detail="يمكنك عرض تحليل أدائك الشخصي فقط")

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
            "message": "لا توجد نتائج امتحانات لهذا الطالب بعد",
            "total_exams": 0,
        })

    analytics = get_analytics_controller()
    analysis = analytics.analyze_student_performance(raw_results)

    return JSONResponse(content={
        "status": "success",
        "student_id": student_id,
        "total_exams": len(raw_results),
        "analysis": analysis,
    })


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
    })


@analytics_router.get("/leaderboard/{project_id}")
async def get_project_leaderboard(
    project_id: str,
    request: Request,
    top_n: int = Query(10, ge=1, le=50),
    current_user: dict = Depends(get_current_user),
):
    db = request.app.client["Satr-Edu"]

    exam_model = ExamModel(client=request.app.client)
    exams = await exam_model.list_approved_exams_by_project(project_id)
    if not exams:
        return JSONResponse(content={
            "status": "no_data",
            "project_id": project_id,
            "message": "لا توجد امتحانات معتمدة لهذا المشروع بعد",
            "leaderboard": []
        })

    exam_ids = [e.exam_id for e in exams]

    pipeline = [
        {"$match": {"exam_id": {"$in": exam_ids}}},
        {"$group": {
            "_id": "$student_id",
            "avg_percentage": {"$avg": "$percentage"},
            "total_exams": {"$sum": 1},
            "best_score": {"$max": "$percentage"},
            "total_score": {"$sum": "$total_score"},
            "total_max": {"$sum": "$max_score"},
        }},
        {"$sort": {"avg_percentage": -1}},
        {"$limit": top_n}
    ]

    leaderboard = []
    async for doc in db["exam_results"].aggregate(pipeline):
        leaderboard.append({
            "rank": len(leaderboard) + 1,
            "student_id": doc["_id"],
            "avg_percentage": round(doc["avg_percentage"], 2),
            "total_exams_taken": doc["total_exams"],
            "best_score": round(doc["best_score"], 2),
        })

    return JSONResponse(content={
        "status": "success",
        "project_id": project_id,
        "total_exams_in_project": len(exams),
        "leaderboard": leaderboard
    })


@analytics_router.get("/teacher/{teacher_id}/overview")
async def get_teacher_overview(
    teacher_id: str,
    request: Request,
    current_user: dict = Depends(require_roles(UserRole.TEACHER.value, UserRole.OPERATIONS.value)),
):
    role = current_user.get("user_role")
    uid = current_user.get("user_id")

    if role == UserRole.TEACHER.value and uid != teacher_id:
        raise HTTPException(status_code=403, detail="يمكنك عرض إحصائياتك الشخصية فقط")

    db = request.app.client["Satr-Edu"]

    exams_cursor = db["exams"].find({"teacher_id": teacher_id}, {"_id": 0})
    exams = []
    async for doc in exams_cursor:
        exams.append(doc)

    total_exams = len(exams)
    approved_count = sum(1 for e in exams if e.get("status") == "approved")
    draft_count = total_exams - approved_count

    exam_ids = [e["exam_id"] for e in exams]
    total_submissions = 0
    avg_score_all = 0.0

    if exam_ids:
        pipeline = [
            {"$match": {"exam_id": {"$in": exam_ids}}},
            {"$group": {
                "_id": None,
                "total": {"$sum": 1},
                "avg_pct": {"$avg": "$percentage"}
            }}
        ]
        async for doc in db["exam_results"].aggregate(pipeline):
            total_submissions = doc.get("total", 0)
            avg_score_all = round(doc.get("avg_pct", 0), 2)

    return JSONResponse(content={
        "status": "success",
        "teacher_id": teacher_id,
        "overview": {
            "total_exams_created": total_exams,
            "approved_exams": approved_count,
            "draft_exams": draft_count,
            "total_student_submissions": total_submissions,
            "average_student_score": avg_score_all,
        }
    })


# ───────────────────────────────────────────────────────────────────────────────
# 📢 Attendance & Absence Endpoints
# ───────────────────────────────────────────────────────────────────────────────


@analytics_router.post("/attendance/record")
async def record_attendance(
    request: Request,
    project_id: str,
    session_id: str,
    session_title: str = "",
    source: str = "session",
    student_ids: list = None,
    present_student_ids: list = None,
    current_user: dict = Depends(require_roles(UserRole.TEACHER.value)),
):
    """
    تسجيل حضور وغياب سيشن/امتحان.

    student_ids       : كل الطلاب المسجلين
    present_student_ids: الطلاب الحاضرين فعلاً
    الباقي = غائبون
    """
    from src.models.AttendanceModel import AttendanceModel
    from src.models.scheme_db.attendance import SessionAttendance
    from datetime import datetime

    attendance_model = AttendanceModel(request.app.client)
    student_ids      = student_ids or []
    present_set      = set(present_student_ids or [])

    recorded = 0
    for sid in student_ids:
        status = "present" if sid in present_set else "absent"
        record = SessionAttendance(
            project_id=project_id,
            student_id=sid,
            session_id=session_id,
            session_title=session_title,
            source=source,
            status=status,
            attended_at=datetime.now() if status == "present" else None,
        )
        if await attendance_model.record_attendance(record):
            recorded += 1

    return JSONResponse(content={
        "status": "success",
        "session_id": session_id,
        "total_students": len(student_ids),
        "present": len(present_set),
        "absent": len(student_ids) - len(present_set),
        "recorded": recorded,
    })


@analytics_router.get("/absence/report/{project_id}")
async def get_absence_report(
    project_id: str,
    request: Request,
    min_absences: int = Query(3, ge=1, le=50),
    current_user: dict = Depends(require_roles(UserRole.TEACHER.value, UserRole.OPERATIONS.value)),
):
    """
    تقرير الغياب للمشروع — كل الطلاب اللي غابوا min_absences مرات أو أكتر.
    """
    from src.models.AttendanceModel import AttendanceModel

    attendance_model = AttendanceModel(request.app.client)
    absent_students  = await attendance_model.get_absent_students_summary(
        project_id=project_id,
        min_absences=min_absences,
    )

    return JSONResponse(content={
        "status": "success",
        "project_id": project_id,
        "absence_threshold": min_absences,
        "total_at_risk": len(absent_students),
        "students": absent_students,
    })


@analytics_router.post("/absence/notify/{student_id}")
async def send_absence_notification(
    student_id: str,
    request: Request,
    project_id: str,
    force: bool = False,
    current_user: dict = Depends(require_roles(UserRole.TEACHER.value, UserRole.OPERATIONS.value)),
):
    """
    إرسال إشعار WhatsApp فوري لطالب بعينه.
    force=True يتجاهل الـ cooldown.
    """
    from src.tasks.attendance_tasks import send_absence_notification_task
    from src.helpers.config import get_settings

    settings = get_settings()
    task = send_absence_notification_task.delay(
        student_id=student_id,
        project_id=project_id,
        mongodb_url=settings.MONGODB_URL,
        force=force,
    )

    return JSONResponse(content={
        "status": "queued",
        "task_id": task.id,
        "student_id": student_id,
        "message": "تم إضافة مهمة الإشعار للطابور",
    })


@analytics_router.post("/absence/notify-all/{project_id}")
async def trigger_absence_check(
    project_id: str,
    request: Request,
    current_user: dict = Depends(require_roles(UserRole.OPERATIONS.value)),
):
    """
    تشغيل فحص الغياب يدوياً لكل المشاريع (للمدير فقط).
    """
    from src.tasks.attendance_tasks import check_and_notify_absent_students
    from src.helpers.config import get_settings

    settings = get_settings()
    task = check_and_notify_absent_students.delay(
        mongodb_url=settings.MONGODB_URL,
        mongodb_database=settings.MONGODB_DATABASE,
    )

    return JSONResponse(content={
        "status": "queued",
        "task_id": task.id,
        "message": "تم تشغيل فحص الغياب الشامل — سيتم إرسال الإشعارات تلقائياً",
    })
