from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Request
from fastapi.responses import JSONResponse
import os
import logging

logger = logging.getLogger("uvicorn.error")

pipeline_router = APIRouter(
    prefix="/api/v1/pipeline",
    tags=["Pipeline — Document Processing"],
)


@pipeline_router.get("/info")
async def pipeline_info():
    from src.pipeline.pipeline_manager import DocumentPipeline
    return {
        "supported_extensions": DocumentPipeline.supported_extensions(),
        "chunking_strategies": DocumentPipeline.available_strategies(),
        "description": "Universal Document Processing Pipeline — Parse any file type, chunk with multiple strategies.",
    }


@pipeline_router.get("/strategies")
async def list_strategies():
    return {
        "strategies": [
            {
                "name": "naive",
                "description": "تقسيم عادي بالحجم — سريع ومناسب لأغلب الحالات",
                "best_for": "نصوص عادية، ملفات صغيرة",
            },
            {
                "name": "structure",
                "description": "يحترم هيكل المستند — العناوين بتبدأ chunk جديد والجداول بتيجي كاملة",
                "best_for": "كتب دراسية، PDFs، مستندات رسمية",
            },
            {
                "name": "semantic",
                "description": "يقسم بناءً على تغيّر المعنى باستخدام embeddings",
                "best_for": "مقالات طويلة، أبحاث، محتوى متنوع",
                "requires": "embedding_client",
            },
        ]
    }


@pipeline_router.post("/process")
async def process_file(
    file: UploadFile = File(...),
    chunk_strategy: str = Form("naive"),
    chunk_size: int = Form(500),
    chunk_overlap: int = Form(50),
    return_chunks: bool = Form(True),
):
    from src.pipeline.pipeline_manager import DocumentPipeline

    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    ext = os.path.splitext(file.filename)[-1].lower()
    supported = DocumentPipeline.supported_extensions()
    if ext not in supported:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {ext}. Supported: {supported}"
        )

    tmp_dir = os.path.join(os.getcwd(), "src", "assets", "tmp")
    os.makedirs(tmp_dir, exist_ok=True)
    tmp_path = os.path.join(tmp_dir, file.filename)

    try:
        content = await file.read()
        with open(tmp_path, "wb") as f:
            f.write(content)

        pipeline = DocumentPipeline()
        result = pipeline.process(
            file_path=tmp_path,
            chunk_strategy=chunk_strategy,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

        if not result.success:
            raise HTTPException(status_code=422, detail=result.error)

        response = result.to_dict()

        if return_chunks:
            response["chunks"] = [
                {
                    "text": chunk.chunk_text,
                    "metadata": chunk.chunk_metadata,
                    "char_count": len(chunk.chunk_text),
                }
                for chunk in result.chunks
            ]

        return response

    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass


@pipeline_router.post("/process-text")
async def process_text(
    text: str = Form(...),
    chunk_strategy: str = Form("naive"),
    chunk_size: int = Form(500),
    chunk_overlap: int = Form(50),
    source_name: str = Form("raw_text"),
):
    from src.pipeline.pipeline_manager import DocumentPipeline

    if not text or not text.strip():
        raise HTTPException(status_code=400, detail="Empty text provided")

    pipeline = DocumentPipeline()
    result = pipeline.process_text(
        text=text,
        chunk_strategy=chunk_strategy,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        metadata={"source": source_name},
    )

    if not result.success:
        raise HTTPException(status_code=422, detail=result.error)

    response = result.to_dict()
    response["chunks"] = [
        {
            "text": chunk.chunk_text,
            "metadata": chunk.chunk_metadata,
            "char_count": len(chunk.chunk_text),
        }
        for chunk in result.chunks
    ]

    return response
