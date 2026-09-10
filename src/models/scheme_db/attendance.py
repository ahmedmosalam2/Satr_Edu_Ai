"""
src/models/scheme_db/attendance.py
──────────────────────────────────
Schemas لتتبع الحضور والغياب وإشعارات الواتساب.

Collections في MongoDB:
  - session_attendance   : حضور/غياب كل سيشن
  - exam_enrollments     : تسجيل الطلاب في الامتحانات
  - absence_notifications: سجل الإشعارات المبعوتة
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
import uuid


# ── Session Attendance ────────────────────────────────────────────────────────

class SessionAttendance(BaseModel):
    """
    سجل حضور طالب في سيشن واحد.
    الـ source = 'session' | 'exam'
    """
    attendance_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    project_id: str
    student_id: str
    session_id: str                          # ID السيشن أو الامتحان
    session_title: str = ""                  # عنوان السيشن/الامتحان
    source: str = "session"                  # 'session' | 'exam'
    status: str = "absent"                   # 'present' | 'absent' | 'late'
    scheduled_at: Optional[datetime] = None  # موعد السيشن/الامتحان
    attended_at: Optional[datetime] = None   # وقت الحضور الفعلي (None = غاب)
    created_at: datetime = Field(default_factory=datetime.now)

    @classmethod
    def get_indexes(cls):
        return [
            {
                "key": [("attendance_id", 1)],
                "name": "attendance_id_unique",
                "unique": True,
            },
            {
                "key": [("student_id", 1), ("session_id", 1), ("source", 1)],
                "name": "student_session_unique",
                "unique": True,
            },
            {
                "key": [("project_id", 1), ("student_id", 1)],
                "name": "project_student_idx",
            },
            {
                "key": [("status", 1)],
                "name": "status_idx",
            },
        ]


# ── Absence Notification Log ──────────────────────────────────────────────────

class AbsenceNotificationLog(BaseModel):
    """
    سجل إشعارات الغياب المبعوتة — عشان ما نبعتش نفس الإشعار أكتر من مرة.
    """
    notification_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    student_id: str
    project_id: str
    absence_count: int                       # عدد مرات الغياب اللي أدت للإشعار
    student_phone: Optional[str] = None      # رقم الطالب
    guardian_phone: Optional[str] = None     # رقم ولي الأمر
    student_message_id: Optional[str] = None # message ID من Ultramsg
    guardian_message_id: Optional[str] = None
    student_sent: bool = False
    guardian_sent: bool = False
    sent_at: datetime = Field(default_factory=datetime.now)
    error: Optional[str] = None             # لو فيه خطأ في الإرسال

    @classmethod
    def get_indexes(cls):
        return [
            {
                "key": [("notification_id", 1)],
                "name": "notification_id_unique",
                "unique": True,
            },
            {
                "key": [("student_id", 1), ("project_id", 1)],
                "name": "student_project_idx",
            },
            {
                "key": [("sent_at", -1)],
                "name": "sent_at_desc",
            },
        ]
