"""
src/tasks/process_tasks.py
──────────────────────────
الـ Celery tasks المسؤولة عن معالجة الملفات في الخلفية.

الفكرة:
- الـ API يستقبل الطلب ويبعت task فوراً لـ Celery
- Celery Worker يعمل الشغل الفعلي (chunk + save) في الخلفية
- المستخدم يقدر يتابع الحالة عبر task_id
"""

import os
import logging
from celery import Celery
from datetime import datetime

logger = logging.getLogger(__name__)

# ── إعداد Celery مع Redis ────────────────────────────────────────────────
def make_celery_app() -> Celery:
    """إنشاء Celery app متصلة بـ Redis."""
    from src.helpers.config import get_settings
    settings = get_settings()
    redis_url = settings.REDIS_URL

    app = Celery(
        "satr_edu_tasks",
        broker=redis_url,   # Redis بيستقبل المهام
        backend=redis_url,  # Redis بيحفظ النتائج
    )
    app.conf.update(
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        timezone="Africa/Cairo",
        enable_utc=True,
        # المهمة تنتهي بعد 10 دقائق كحد أقصى
        task_soft_time_limit=600,
        task_time_limit=660,
    )
    return app


celery_app = make_celery_app()


# ── Task الرئيسية: معالجة ملف ────────────────────────────────────────────
@celery_app.task(bind=True, name="process_file")
def process_file_task(
    self,
    project_id: str,
    file_id: str,
    chunk_size: int = 500,
    chunk_overlap: int = 50,
    mongodb_url: str = None,
    mongodb_database: str = None,
):
    """
    معالجة ملف في الخلفية:
    1. تحميل الملف من الـ filesystem
    2. تقسيمه لـ chunks
    3. حفظ الـ chunks في MongoDB

    الـ parameters:
    - project_id: رقم المشروع
    - file_id: رقم الملف
    - chunk_size / chunk_overlap: إعدادات التقسيم
    - mongodb_url / mongodb_database: معلومات اتصال MongoDB
    """
    logger.info(f"[Task {self.request.id}] Starting processing: {file_id} in project {project_id}")

    try:
        # ── 1. تحديث الحالة ─────────────────────────────────────────────
        self.update_state(state="PROCESSING", meta={"status": "جاري تحميل الملف..."})

        # ── 2. تحميل الملف وتقسيمه ──────────────────────────────────────
        from src.controllers.ProcessController import ProcessController

        process_controller = ProcessController(project_id=project_id)
        file_content = process_controller.get_file_content(file_id=file_id)

        self.update_state(state="PROCESSING", meta={"status": "جاري تقسيم المحتوى..."})

        file_chunks = process_controller.process_file_content(
            file_content=file_content,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

        logger.info(f"[Task {self.request.id}] Generated {len(file_chunks)} chunks")

        # ── 3. حفظ الـ chunks في MongoDB ─────────────────────────────────
        self.update_state(state="PROCESSING", meta={"status": "جاري الحفظ في قاعدة البيانات..."})

        if mongodb_url and mongodb_database:
            import asyncio
            from motor.motor_asyncio import AsyncIOMotorClient
            from src.models.ChunkModel import ChunkModel
            from src.models.scheme_db.data_chunk import DataChunk

            async def _save_chunks():
                client = AsyncIOMotorClient(mongodb_url, serverSelectionTimeoutMS=5000)
                chunk_model = ChunkModel(client=client, project_id=project_id)

                now = datetime.now().isoformat()
                chunks_to_save = [
                    DataChunk(
                        chunk_id=f"{project_id}_{file_id}_{i}",
                        chunk_text=chunk.page_content,
                        chunk_metadata=chunk.metadata,
                        chunk_order=i,
                        chunk_created_at=now,
                        chunk_updated_at=now,
                        chunk_project_id=project_id,
                    )
                    for i, chunk in enumerate(file_chunks)
                ]

                if chunk_model.collection is not None and len(chunks_to_save) > 0:
                    await chunk_model.insert_many_chunks(
                        project_id=project_id, chunks=chunks_to_save
                    )

                client.close()
                return len(chunks_to_save)

            # Celery workers don't have an event loop → نعمل واحد مؤقت
            chunks_saved = asyncio.run(_save_chunks())
            logger.info(f"[Task {self.request.id}] Saved {chunks_saved} chunks to MongoDB")
        else:
            chunks_saved = 0
            logger.warning(f"[Task {self.request.id}] No MongoDB config → chunks not saved")

        # ── 4. النتيجة النهائية ───────────────────────────────────────────
        result = {
            "status": "success",
            "project_id": project_id,
            "file_id": file_id,
            "chunks_count": len(file_chunks),
            "chunks_saved": chunks_saved,
        }
        logger.info(f"[Task {self.request.id}] Completed: {result}")
        return result

    except Exception as e:
        logger.error(f"[Task {self.request.id}] Failed: {e}")
        # Celery بيحفظ الـ exception تلقائياً كـ FAILURE
        raise
