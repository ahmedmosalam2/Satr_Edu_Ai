"""
src/models/AttendanceModel.py
─────────────────────────────
MongoDB ODM لإدارة الحضور والغياب وسجلات الإشعارات.

Collections:
  - session_attendance   : حضور/غياب الطلاب في كل سيشن/امتحان
  - absence_notifications: سجل إشعارات الواتساب المبعوتة
"""

from motor.motor_asyncio import AsyncIOMotorClient
from typing import Optional, List
from datetime import datetime, timedelta
import logging

from src.models.scheme_db.attendance import SessionAttendance, AbsenceNotificationLog

logger = logging.getLogger("uvicorn.error")


class AttendanceModel:

    def __init__(self, client: AsyncIOMotorClient):
        self.client = client
        self.db = client["Satr-Edu"]
        self.attendance = self.db["session_attendance"]
        self.notifications = self.db["absence_notifications"]

    # ── Session Attendance ────────────────────────────────────────────────────

    async def record_attendance(self, record: SessionAttendance) -> bool:
        """سجّل حضور أو غياب طالب في سيشن/امتحان."""
        try:
            await self.attendance.insert_one(record.dict())
            return True
        except Exception as e:
            # Duplicate key = الطالب ده اتسجل قبل كده
            logger.warning(f"[Attendance] Duplicate or error: {e}")
            return False

    async def mark_present(self, student_id: str, session_id: str, source: str = "session") -> bool:
        """تحديث حالة الطالب لـ present."""
        result = await self.attendance.update_one(
            {"student_id": student_id, "session_id": session_id, "source": source},
            {"$set": {"status": "present", "attended_at": datetime.now()}},
        )
        return result.modified_count > 0

    async def get_student_absences(
        self,
        student_id: str,
        project_id: str,
        source: Optional[str] = None,   # None = كل المصادر
    ) -> List[SessionAttendance]:
        """جيب كل غيابات طالب في مشروع معين."""
        query: dict = {"student_id": student_id, "project_id": project_id, "status": "absent"}
        if source:
            query["source"] = source
        cursor = self.attendance.find(query).sort("created_at", -1)
        records = []
        async for doc in cursor:
            doc.pop("_id", None)
            records.append(SessionAttendance(**doc))
        return records

    async def count_absences(self, student_id: str, project_id: str) -> int:
        """عد غيابات الطالب (امتحانات + سيشنات)."""
        return await self.attendance.count_documents(
            {"student_id": student_id, "project_id": project_id, "status": "absent"}
        )

    async def get_absent_students_summary(self, project_id: str, min_absences: int = 3) -> List[dict]:
        """
        جيب ملخص الطلاب اللي غابوا `min_absences` مرات أو أكتر.
        بيستخدم MongoDB Aggregation Pipeline.
        """
        pipeline = [
            {"$match": {"project_id": project_id, "status": "absent"}},
            {"$group": {
                "_id": "$student_id",
                "absence_count": {"$sum": 1},
                "last_absence": {"$max": "$created_at"},
                "sessions": {"$push": "$session_title"},
            }},
            {"$match": {"absence_count": {"$gte": min_absences}}},
            {"$sort": {"absence_count": -1}},
        ]
        results = []
        async for doc in self.attendance.aggregate(pipeline):
            results.append({
                "student_id": doc["_id"],
                "absence_count": doc["absence_count"],
                "last_absence": doc["last_absence"].isoformat() if doc["last_absence"] else None,
                "absent_sessions": doc["sessions"][-5:],  # آخر 5 سيشنات غاب فيهم
            })
        return results

    async def get_all_projects_absent_students(self, min_absences: int = 3) -> List[dict]:
        """جيب كل الطلاب اللي غابوا في أي مشروع (للـ Celery scheduled task)."""
        pipeline = [
            {"$match": {"status": "absent"}},
            {"$group": {
                "_id": {"student_id": "$student_id", "project_id": "$project_id"},
                "absence_count": {"$sum": 1},
                "last_absence": {"$max": "$created_at"},
            }},
            {"$match": {"absence_count": {"$gte": min_absences}}},
            {"$sort": {"absence_count": -1}},
        ]
        results = []
        async for doc in self.attendance.aggregate(pipeline):
            results.append({
                "student_id": doc["_id"]["student_id"],
                "project_id": doc["_id"]["project_id"],
                "absence_count": doc["absence_count"],
                "last_absence": doc["last_absence"],
            })
        return results

    # ── Notification Log ──────────────────────────────────────────────────────

    async def log_notification(self, log: AbsenceNotificationLog) -> bool:
        """سجّل إشعار تم إرساله."""
        try:
            await self.notifications.insert_one(log.dict())
            return True
        except Exception as e:
            logger.error(f"[AttendanceModel] Failed to log notification: {e}")
            return False

    async def was_notified_recently(
        self,
        student_id: str,
        project_id: str,
        cooldown_days: int = 7,
    ) -> bool:
        """
        هل بعتنا إشعار لهذا الطالب في آخر `cooldown_days` أيام؟
        عشان نتجنب spam الإشعارات.
        """
        since = datetime.now() - timedelta(days=cooldown_days)
        doc = await self.notifications.find_one({
            "student_id": student_id,
            "project_id": project_id,
            "sent_at": {"$gte": since},
        })
        return doc is not None

    async def get_notification_history(self, student_id: str, limit: int = 10) -> List[dict]:
        """سجل إشعارات طالب معين."""
        cursor = self.notifications.find(
            {"student_id": student_id},
            {"_id": 0}
        ).sort("sent_at", -1).limit(limit)
        result = []
        async for doc in cursor:
            if "sent_at" in doc and hasattr(doc["sent_at"], "isoformat"):
                doc["sent_at"] = doc["sent_at"].isoformat()
            result.append(doc)
        return result

    # ── Index Creation ────────────────────────────────────────────────────────

    @classmethod
    async def create_indexes(cls, client: AsyncIOMotorClient):
        db = client["Satr-Edu"]
        for idx in SessionAttendance.get_indexes():
            await db["session_attendance"].create_index(
                idx["key"], name=idx["name"], unique=idx.get("unique", False)
            )
        for idx in AbsenceNotificationLog.get_indexes():
            await db["absence_notifications"].create_index(
                idx["key"], name=idx["name"], unique=idx.get("unique", False)
            )
        logger.info("✅ Attendance indexes created")
