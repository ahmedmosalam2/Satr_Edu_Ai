"""
src/tasks/attendance_tasks.py
─────────────────────────────
Celery Tasks لأتمتة إشعارات الغياب عبر WhatsApp.

الـ Tasks:
  1. check_and_notify_absent_students  — بيشتغل كل يوم الساعة 8 مساءً
     - بيجيب كل الطلاب اللي غابوا 3 مرات أو أكتر
     - بيتحقق إننا ما بعتناش إشعار في آخر 7 أيام
     - بيبعت WhatsApp للطالب ولولي الأمر
     - بيسجل في MongoDB عشان نتحاشى الـ spam

  2. send_absence_notification  — بيبعت إشعار لطالب واحد بالذات (on-demand)

الـ Celery Beat Schedule:
  يُضاف في celeryconfig.py أو في الـ celery app config
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional

from src.tasks.process_tasks import celery_app

logger = logging.getLogger(__name__)


# ─── Helper: run async code in Celery sync context ───────────────────────────

def _run(coro):
    """تشغيل async code داخل Celery worker (sync context)."""
    return asyncio.run(coro)


# ─── Core Logic (async) ───────────────────────────────────────────────────────

async def _do_check_and_notify(mongodb_url: str = None, mongodb_database: str = None):
    """
    الـ logic الأساسي — بيشتغل async.
    مفصول عن الـ Celery task عشان نقدر نختبره مستقلين.
    """
    from motor.motor_asyncio import AsyncIOMotorClient
    from src.helpers.config import get_settings
    from src.helpers.whatsapp_client import WhatsAppClient
    from src.models.AttendanceModel import AttendanceModel
    from src.models.UserModel import UserModel
    from src.models.ProjectModel import ProjectModel
    from src.models.scheme_db.attendance import AbsenceNotificationLog

    settings = get_settings()
    mongo_url = mongodb_url or settings.MONGODB_URL
    mongo_db  = mongodb_database or settings.MONGODB_DATABASE
    threshold = settings.ABSENCE_THRESHOLD
    cooldown  = settings.ABSENCE_COOLDOWN_DAYS

    client = AsyncIOMotorClient(mongo_url, serverSelectionTimeoutMS=5000)
    try:
        await client.admin.command("ping")
        logger.info("[AbsenceTask] ✅ MongoDB connected")

        attendance_model = AttendanceModel(client)
        user_model       = UserModel(client)
        project_model    = await ProjectModel.create_index(client)
        whatsapp         = WhatsAppClient()

        # 1. جيب كل الطلاب اللي غابوا فوق الـ threshold
        absent_summaries = await attendance_model.get_all_projects_absent_students(
            min_absences=threshold
        )

        logger.info(f"[AbsenceTask] Found {len(absent_summaries)} student-project pairs above threshold={threshold}")

        notified_count    = 0
        skipped_cooldown  = 0
        failed_count      = 0

        for summary in absent_summaries:
            student_id   = summary["student_id"]
            project_id   = summary["project_id"]
            absence_count = summary["absence_count"]

            # 2. فحص الـ cooldown — هل بعتنا إشعار في آخر N أيام؟
            already_notified = await attendance_model.was_notified_recently(
                student_id=student_id,
                project_id=project_id,
                cooldown_days=cooldown,
            )
            if already_notified:
                skipped_cooldown += 1
                logger.debug(f"[AbsenceTask] Skipping {student_id} — notified within {cooldown} days")
                continue

            # 3. جيب بيانات الطالب
            student = await user_model.get_user_by_id(student_id)
            if not student:
                logger.warning(f"[AbsenceTask] Student {student_id} not found in users collection")
                continue

            # 4. جيب اسم المشروع
            try:
                project = await project_model.get_project(project_id)
                project_name = project.project_name if project else project_id
            except Exception:
                project_name = project_id

            # 5. بعت WhatsApp للطالب
            student_msg_id   = None
            guardian_msg_id  = None
            student_sent     = False
            guardian_sent    = False
            error_msg        = None

            if student.phone:
                student_msg_id = await whatsapp.send_absence_alert_student(
                    phone=student.phone,
                    student_name=student.user_name,
                    absence_count=absence_count,
                    project_name=project_name,
                )
                student_sent = student_msg_id is not None
            else:
                logger.info(f"[AbsenceTask] Student {student_id} has no phone number")

            # 6. بعت WhatsApp لولي الأمر
            if student.guardian_phone:
                guardian_msg_id = await whatsapp.send_absence_alert_guardian(
                    phone=student.guardian_phone,
                    student_name=student.user_name,
                    guardian_name=student.guardian_name or "ولي الأمر",
                    absence_count=absence_count,
                    project_name=project_name,
                )
                guardian_sent = guardian_msg_id is not None
            else:
                logger.info(f"[AbsenceTask] Student {student_id} has no guardian phone")

            # 7. سجّل الإشعار في MongoDB
            log = AbsenceNotificationLog(
                student_id=student_id,
                project_id=project_id,
                absence_count=absence_count,
                student_phone=student.phone,
                guardian_phone=student.guardian_phone,
                student_message_id=student_msg_id,
                guardian_message_id=guardian_msg_id,
                student_sent=student_sent,
                guardian_sent=guardian_sent,
                error=error_msg,
            )
            await attendance_model.log_notification(log)

            if student_sent or guardian_sent:
                notified_count += 1
                logger.info(
                    f"[AbsenceTask] ✅ Notified: student={student_id} "
                    f"(student_sent={student_sent}, guardian_sent={guardian_sent}) "
                    f"absences={absence_count}"
                )
            else:
                failed_count += 1
                logger.warning(
                    f"[AbsenceTask] ⚠️ No notification sent for {student_id} "
                    f"(no phone numbers or API error)"
                )

        summary_result = {
            "status": "completed",
            "timestamp": datetime.now().isoformat(),
            "total_checked": len(absent_summaries),
            "notified": notified_count,
            "skipped_cooldown": skipped_cooldown,
            "failed_or_no_phone": failed_count,
        }
        logger.info(f"[AbsenceTask] Done: {summary_result}")
        return summary_result

    finally:
        client.close()


async def _do_send_single_notification(
    student_id: str,
    project_id: str,
    mongodb_url: str = None,
    force: bool = False,
):
    """
    بعت إشعار لطالب واحد بالذات (on-demand).
    force=True يتجاهل الـ cooldown.
    """
    from motor.motor_asyncio import AsyncIOMotorClient
    from src.helpers.config import get_settings
    from src.helpers.whatsapp_client import WhatsAppClient
    from src.models.AttendanceModel import AttendanceModel
    from src.models.UserModel import UserModel
    from src.models.ProjectModel import ProjectModel
    from src.models.scheme_db.attendance import AbsenceNotificationLog

    settings = get_settings()
    mongo_url = mongodb_url or settings.MONGODB_URL
    cooldown  = settings.ABSENCE_COOLDOWN_DAYS

    client = AsyncIOMotorClient(mongo_url, serverSelectionTimeoutMS=5000)
    try:
        await client.admin.command("ping")

        attendance_model = AttendanceModel(client)
        user_model       = UserModel(client)
        project_model    = await ProjectModel.create_index(client)
        whatsapp         = WhatsAppClient()

        # Cooldown check (unless force=True)
        if not force:
            already = await attendance_model.was_notified_recently(
                student_id=student_id,
                project_id=project_id,
                cooldown_days=cooldown,
            )
            if already:
                return {"status": "skipped", "reason": f"already notified within {cooldown} days"}

        student = await user_model.get_user_by_id(student_id)
        if not student:
            return {"status": "error", "reason": "student not found"}

        absence_count = await attendance_model.count_absences(student_id, project_id)

        try:
            project = await project_model.get_project(project_id)
            project_name = project.project_name if project else project_id
        except Exception:
            project_name = project_id

        student_msg_id  = None
        guardian_msg_id = None

        if student.phone:
            student_msg_id = await whatsapp.send_absence_alert_student(
                phone=student.phone,
                student_name=student.user_name,
                absence_count=absence_count,
                project_name=project_name,
            )

        if student.guardian_phone:
            guardian_msg_id = await whatsapp.send_absence_alert_guardian(
                phone=student.guardian_phone,
                student_name=student.user_name,
                guardian_name=student.guardian_name or "ولي الأمر",
                absence_count=absence_count,
                project_name=project_name,
            )

        log = AbsenceNotificationLog(
            student_id=student_id,
            project_id=project_id,
            absence_count=absence_count,
            student_phone=student.phone,
            guardian_phone=student.guardian_phone,
            student_message_id=student_msg_id,
            guardian_message_id=guardian_msg_id,
            student_sent=student_msg_id is not None,
            guardian_sent=guardian_msg_id is not None,
        )
        await attendance_model.log_notification(log)

        return {
            "status": "success",
            "student_id": student_id,
            "absence_count": absence_count,
            "student_sent": student_msg_id is not None,
            "guardian_sent": guardian_msg_id is not None,
        }
    finally:
        client.close()


# ─── Celery Tasks ─────────────────────────────────────────────────────────────

@celery_app.task(bind=True, name="check_absent_students")
def check_and_notify_absent_students(
    self,
    mongodb_url: str = None,
    mongodb_database: str = None,
):
    """
    📅 Scheduled Task — بيشتغل تلقائياً كل يوم الساعة 8 مساءً.

    يكتشف الطلاب الغائبين ويبعت WhatsApp للطالب ولولي الأمر.
    """
    logger.info(f"[Task {self.request.id}] Starting absence check...")
    self.update_state(state="PROCESSING", meta={"status": "جاري فحص الغيابات..."})

    try:
        result = _run(_do_check_and_notify(
            mongodb_url=mongodb_url,
            mongodb_database=mongodb_database,
        ))
        logger.info(f"[Task {self.request.id}] Absence check done: {result}")
        return result
    except Exception as exc:
        logger.exception(f"[Task {self.request.id}] Absence check FAILED")
        raise exc


@celery_app.task(bind=True, name="send_absence_notification")
def send_absence_notification_task(
    self,
    student_id: str,
    project_id: str,
    mongodb_url: str = None,
    force: bool = False,
):
    """
    🔔 On-Demand Task — بعت إشعار لطالب بالذات فوراً.
    يمكن استدعاؤها من الـ API أو من الـ Dashboard.
    """
    logger.info(f"[Task {self.request.id}] Sending absence notification to student={student_id}")
    try:
        return _run(_do_send_single_notification(
            student_id=student_id,
            project_id=project_id,
            mongodb_url=mongodb_url,
            force=force,
        ))
    except Exception as exc:
        logger.exception(f"[Task {self.request.id}] Notification FAILED")
        raise exc


# ─── Celery Beat Schedule ─────────────────────────────────────────────────────
# أضف ده في celery_app.conf.beat_schedule في make_celery_app()
# أو في ملف celeryconfig.py مستقل

BEAT_SCHEDULE = {
    "daily-absence-check": {
        "task": "check_absent_students",
        "schedule": {
            # كل يوم الساعة 8 مساءً بتوقيت القاهرة
            "crontab": {"hour": "20", "minute": "0"}
        },
        "options": {"expires": 3600},  # تنتهي صلاحية المهمة لو ما اتنفذتش في ساعة
    }
}
