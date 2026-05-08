"""
Shared utility to fetch all text chunks for a project from MongoDB.
Used by AI routes, exam routes, and anywhere project content is needed.
"""
import logging

logger = logging.getLogger("uvicorn.error")


async def fetch_project_content(db_client, project_id: str) -> str:
    """
    Fetch all chunks from MongoDB for a project and concatenate into a single string.

    Args:
        db_client: The Motor AsyncIOMotorClient instance.
        project_id: The project ID to fetch chunks for.

    Returns:
        Concatenated text of all chunks, or empty string on failure.
    """
    try:
        from src.models.ChunkModel import ChunkModel
        chunk_model = ChunkModel(client=db_client, project_id=project_id)

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
