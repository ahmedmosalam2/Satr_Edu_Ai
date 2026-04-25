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
import asyncio
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


async def run_index_project_job(
    project_id: str,
    do_reset: bool = False,
    mongodb_url: str = None,
    mongodb_database: str = None,
    status_callback=None,
):
    """
    Reusable indexing job for both Celery workers and local FastAPI fallbacks.
    """
    from motor.motor_asyncio import AsyncIOMotorClient
    from src.controllers.NLPController import NLPController
    from src.helpers.config import get_settings
    from src.helpers.nlp_clients import get_embedding_client, get_vectordb_client, template_parser
    from src.models.ChunkModel import ChunkModel
    from src.models.ProjectModel import ProjectModel

    settings = get_settings()
    resolved_mongodb_url = mongodb_url or settings.MONGODB_URL
    resolved_database = mongodb_database or settings.MONGODB_DATABASE

    def update_status(state: str, meta: dict):
        if status_callback is not None:
            status_callback(state, meta)

    client = AsyncIOMotorClient(resolved_mongodb_url, serverSelectionTimeoutMS=5000)
    try:
        update_status("PROCESSING", {"status": "Connecting to MongoDB"})
        await client.admin.command("ping")

        db_client = client
        project_model = await ProjectModel.create_index(db_client=db_client)
        project = await project_model.get_project(project_id=project_id)

        chunk_model = await ChunkModel.create_index(db_client=db_client)
        nlp_controller = NLPController(
            vectordb_client=get_vectordb_client(),
            generation_client=None,
            embedding_client=get_embedding_client(),
            template_parser=template_parser,
            chunk_model=chunk_model,
        )

        page = 1
        page_size = 50
        indexed_count = 0
        total_batches = 0

        update_status("PROCESSING", {"status": "Preparing chunks for indexing"})
        while True:
            chunks = await chunk_model.get_project_chunks(
                project_id=project.project_id,
                page=page,
                page_size=page_size,
            )
            if not chunks:
                break

            chunk_ids = list(range(indexed_count, indexed_count + len(chunks)))

            for chunk in chunks:
                if not chunk.chunk_metadata:
                    chunk.chunk_metadata = {}
                chunk.chunk_metadata["chunk_id"] = chunk.chunk_id
                chunk.chunk_metadata["chunk_order"] = chunk.chunk_order
                if "source" not in chunk.chunk_metadata and "source_file" not in chunk.chunk_metadata:
                    chunk.chunk_metadata["source_file"] = (
                        chunk.chunk_id.split("_")[2]
                        if chunk.chunk_id.count("_") >= 2 else chunk.chunk_id
                    )

            update_status(
                "PROCESSING",
                {
                    "status": f"Indexing batch {page}",
                    "batch": page,
                    "indexed_count": indexed_count,
                },
            )

            await nlp_controller.index_into_vector_db(
                project=project,
                chunks=chunks,
                chunks_ids=chunk_ids,
                do_reset=(bool(do_reset) and page == 1),
            )

            indexed_count += len(chunks)
            total_batches += 1
            page += 1

        result = {
            "status": "success",
            "project_id": project.project_id,
            "indexed_count": indexed_count,
            "batches": total_batches,
            "did_reset": bool(do_reset),
        }
        update_status("SUCCESS", result)
        logger.info("Indexing completed for project %s: %s chunks", project_id, indexed_count)
        return result
    finally:
        client.close()


@celery_app.task(bind=True, name="index_project")
def index_project_task(
    self,
    project_id: str,
    do_reset: bool = False,
    mongodb_url: str = None,
    mongodb_database: str = None,
):
    logger.info("[Task %s] Starting vector indexing for project %s", self.request.id, project_id)

    def _status_callback(state: str, meta: dict):
        self.update_state(state=state, meta=meta)

    try:
        return asyncio.run(
            run_index_project_job(
                project_id=project_id,
                do_reset=do_reset,
                mongodb_url=mongodb_url,
                mongodb_database=mongodb_database,
                status_callback=_status_callback,
            )
        )
    except Exception as exc:
        logger.exception("[Task %s] Vector indexing failed for project %s", self.request.id, project_id)
        raise exc


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
            from motor.motor_asyncio import AsyncIOMotorClient
            from src.models.ChunkModel import ChunkModel
            from src.models.scheme_db.data_chunk import DataChunk

            async def _save_chunks():
                client = AsyncIOMotorClient(mongodb_url, serverSelectionTimeoutMS=5000)
                chunk_model = ChunkModel(client=client, project_id=project_id)

                now = datetime.now().isoformat()
                total_chunks = len(file_chunks)
                batch_size = 50 # معالجة 50 قطعة في المرة
                chunks_saved = 0

                for i in range(0, total_chunks, batch_size):
                    batch = file_chunks[i:i + batch_size]
                    chunks_to_save = [
                        DataChunk(
                            chunk_id=f"{project_id}_{file_id}_{i+j}",
                            chunk_text=chunk.page_content,
                            chunk_metadata=chunk.metadata,
                            chunk_order=i+j,
                            chunk_created_at=now,
                            chunk_updated_at=now,
                            chunk_project_id=project_id,
                        )
                        for j, chunk in enumerate(batch)
                    ]

                    if chunk_model.collection is not None and len(chunks_to_save) > 0:
                        await chunk_model.insert_many_chunks(
                            project_id=project_id, chunks=chunks_to_save
                        )
                    
                    chunks_saved += len(chunks_to_save)
                    percent = round((chunks_saved / total_chunks) * 100, 2)
                    
                    # تحديث الحالة للمستخدم
                    self.update_state(
                        state="PROCESSING",
                        meta={
                            "status": f"Saving chunks: {chunks_saved}/{total_chunks}",
                            "current": chunks_saved,
                            "total": total_chunks,
                            "percent": percent
                        }
                    )
                    logger.info(f"[Task {self.request.id}] Progress: {percent}% ({chunks_saved}/{total_chunks})")

                client.close()
                return chunks_saved

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
            "chunks": [
                {
                    "text": chunk.page_content,
                    "page": chunk.metadata.get("page", 0),
                    "order": i
                }
                for i, chunk in enumerate(file_chunks) # نرجع كل القطع
            ]
        }
        logger.info(f"[Task {self.request.id}] Completed: {result}")
        return result

    except Exception as e:
        logger.error(f"[Task {self.request.id}] Failed: {e}")
        # Celery بيحفظ الـ exception تلقائياً كـ FAILURE
        raise
