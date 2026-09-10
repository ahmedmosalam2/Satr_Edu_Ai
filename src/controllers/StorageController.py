"""
src/controllers/StorageController.py
──────────────────────────────────────
MinIO-based object storage controller.

Strategy: MinIO-first with local filesystem fallback.
- If MinIO is reachable → store files in MinIO bucket
- If MinIO is unavailable → fallback to local filesystem (existing behavior)

This means ZERO breaking changes — the existing upload flow continues
to work even without MinIO running.
"""

import io
import os
import logging
from typing import Optional, Tuple

logger = logging.getLogger("uvicorn.error")


class StorageController:
    """
    Unified file storage — MinIO with filesystem fallback.

    Usage:
        storage = StorageController()
        path_or_url = await storage.save(project_id, file_id, file_bytes)
        content    = await storage.get(project_id, file_id)
        deleted    = await storage.delete(project_id, file_id)
    """

    DEFAULT_BUCKET = "satr-edu-files"

    def __init__(self):
        self._client = None
        self._available = None          # None = not yet checked
        self._bucket = self.DEFAULT_BUCKET

    # ── Internal: lazy-init MinIO client ────────────────────────────────────
    def _get_client(self):
        """Try to connect to MinIO once; cache result."""
        if self._available is not None:
            return self._client if self._available else None

        try:
            from minio import Minio
            from src.helpers.config import get_settings
            settings = get_settings()

            endpoint = getattr(settings, "MINIO_ENDPOINT", "localhost:9000")
            access_key = getattr(settings, "MINIO_ACCESS_KEY", "minioadmin")
            secret_key = getattr(settings, "MINIO_SECRET_KEY", "minioadmin")
            secure = getattr(settings, "MINIO_SECURE", False)

            client = Minio(
                endpoint=endpoint,
                access_key=access_key,
                secret_key=secret_key,
                secure=secure,
            )
            # Quick connectivity check
            client.list_buckets()
            self._client = client
            self._available = True

            # Ensure our bucket exists
            if not client.bucket_exists(self._bucket):
                client.make_bucket(self._bucket)
                logger.info(f"✅ MinIO bucket '{self._bucket}' created")
            else:
                logger.info(f"✅ MinIO connected — bucket '{self._bucket}' ready")

        except ImportError:
            logger.info("ℹ️ minio package not installed — using filesystem storage")
            self._available = False
            self._client = None
        except Exception as e:
            logger.warning(f"⚠️ MinIO unavailable ({e}) — falling back to filesystem")
            self._available = False
            self._client = None

        return self._client if self._available else None

    @property
    def is_minio_available(self) -> bool:
        return self._get_client() is not None

    # ── Object key helper ────────────────────────────────────────────────────
    @staticmethod
    def _object_key(project_id: str, file_id: str) -> str:
        """MinIO object path: projects/{project_id}/{file_id}"""
        return f"projects/{project_id}/{file_id}"

    # ── SAVE ─────────────────────────────────────────────────────────────────
    async def save(
        self,
        project_id: str,
        file_id: str,
        file_bytes: bytes,
        content_type: str = "application/octet-stream",
    ) -> str:
        """
        Save file bytes.
        Returns MinIO object key (if MinIO) or local file path (if fallback).
        """
        client = self._get_client()

        if client:
            try:
                key = self._object_key(project_id, file_id)
                client.put_object(
                    bucket_name=self._bucket,
                    object_name=key,
                    data=io.BytesIO(file_bytes),
                    length=len(file_bytes),
                    content_type=content_type,
                )
                logger.info(f"[Storage] Saved to MinIO: {key}")
                return key
            except Exception as e:
                logger.error(f"[Storage] MinIO save failed: {e} — falling back to filesystem")

        # Filesystem fallback
        return self._fs_save(project_id, file_id, file_bytes)

    # ── GET ───────────────────────────────────────────────────────────────────
    async def get(self, project_id: str, file_id: str) -> Optional[bytes]:
        """Load file bytes from MinIO or filesystem."""
        client = self._get_client()

        if client:
            try:
                key = self._object_key(project_id, file_id)
                response = client.get_object(self._bucket, key)
                data = response.read()
                response.close()
                response.release_conn()
                return data
            except Exception as e:
                logger.warning(f"[Storage] MinIO get failed for {file_id}: {e}")

        # Filesystem fallback
        return self._fs_get(project_id, file_id)

    # ── DELETE ────────────────────────────────────────────────────────────────
    async def delete(self, project_id: str, file_id: str) -> bool:
        """Delete file from MinIO and/or filesystem."""
        deleted = False
        client = self._get_client()

        if client:
            try:
                key = self._object_key(project_id, file_id)
                client.remove_object(self._bucket, key)
                logger.info(f"[Storage] Deleted from MinIO: {key}")
                deleted = True
            except Exception as e:
                logger.warning(f"[Storage] MinIO delete failed for {file_id}: {e}")

        # Also try filesystem (covers migration period)
        if self._fs_delete(project_id, file_id):
            deleted = True

        return deleted

    # ── PRESIGNED URL ─────────────────────────────────────────────────────────
    def get_presigned_url(
        self,
        project_id: str,
        file_id: str,
        expires_seconds: int = 3600,
    ) -> Optional[str]:
        """Generate a temporary download URL (MinIO only)."""
        from datetime import timedelta
        client = self._get_client()
        if not client:
            return None
        try:
            key = self._object_key(project_id, file_id)
            url = client.presigned_get_object(
                self._bucket, key, expires=timedelta(seconds=expires_seconds)
            )
            return url
        except Exception as e:
            logger.error(f"[Storage] Presigned URL error: {e}")
            return None

    # ── STATUS ────────────────────────────────────────────────────────────────
    def status(self) -> dict:
        """Return storage backend status info."""
        return {
            "backend": "minio" if self.is_minio_available else "filesystem",
            "minio_available": self.is_minio_available,
            "bucket": self._bucket if self.is_minio_available else None,
        }

    # ── FILESYSTEM HELPERS ────────────────────────────────────────────────────
    @staticmethod
    def _fs_path(project_id: str, file_id: str) -> str:
        from src.controllers.ProjectController import ProjectController
        project_path = ProjectController().get_project_path(project_id=project_id)
        # file_id may already contain the filename
        return os.path.join(project_path, file_id)

    def _fs_save(self, project_id: str, file_id: str, file_bytes: bytes) -> str:
        path = self._fs_path(project_id, file_id)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(file_bytes)
        logger.info(f"[Storage] Saved to filesystem: {path}")
        return path

    def _fs_get(self, project_id: str, file_id: str) -> Optional[bytes]:
        path = self._fs_path(project_id, file_id)
        if os.path.exists(path):
            with open(path, "rb") as f:
                return f.read()
        logger.warning(f"[Storage] File not found on filesystem: {path}")
        return None

    def _fs_delete(self, project_id: str, file_id: str) -> bool:
        path = self._fs_path(project_id, file_id)
        if os.path.exists(path):
            os.remove(path)
            return True
        return False


# ── Singleton ────────────────────────────────────────────────────────────────
_storage_instance: Optional[StorageController] = None


def get_storage() -> StorageController:
    """Return a shared StorageController instance (lazy init)."""
    global _storage_instance
    if _storage_instance is None:
        _storage_instance = StorageController()
    return _storage_instance
