from motor.motor_asyncio import AsyncIOMotorClient
from typing import Optional, List

from src.models.scheme_db.student_answer import StudentAnswer
from src.models.scheme_db.exam_result import ExamResult


class ExamResultModel:

    def __init__(self, client: AsyncIOMotorClient):
        self.client = client
        self.db = client["Satr-Edu"]
        self.answers = self.db["student_answers"]
        self.results = self.db["exam_results"]

   

    async def save_answers(self, answers: List[StudentAnswer]) -> bool:
        if not answers:
            return False
        docs = [a.dict() for a in answers]
        await self.answers.insert_many(docs)
        return True

    async def get_answers(self, exam_id: str, student_id: str) -> List[StudentAnswer]:
        cursor = self.answers.find({"exam_id": exam_id, "student_id": student_id})
        answers = []
        async for doc in cursor:
            doc.pop("_id", None)
            answers.append(StudentAnswer(**doc))
        return answers

    async def already_submitted(self, exam_id: str, student_id: str) -> bool:
        """منع التقديم مرتين."""
        doc = await self.results.find_one({"exam_id": exam_id, "student_id": student_id})
        return doc is not None

    # ─── Exam Results ─────────────────────────────────────────────────────────

    async def save_result(self, result: ExamResult) -> bool:
        await self.results.insert_one(result.dict())
        return True

    async def get_result(self, exam_id: str, student_id: str) -> Optional[ExamResult]:
        doc = await self.results.find_one({"exam_id": exam_id, "student_id": student_id})
        if not doc:
            return None
        doc.pop("_id", None)
        return ExamResult(**doc)

    async def get_all_results(self, exam_id: str) -> List[ExamResult]:
        """للمعلم — كل نتائج طلاب الامتحان."""
        cursor = self.results.find({"exam_id": exam_id})
        results = []
        async for doc in cursor:
            doc.pop("_id", None)
            results.append(ExamResult(**doc))
        return results

 
    @classmethod
    async def create_indexes(cls, client: AsyncIOMotorClient):
        db = client["Satr-Edu"]
        for idx in StudentAnswer.get_indexes():
            await db["student_answers"].create_index(idx["key"], name=idx["name"], unique=idx.get("unique", False))
        for idx in ExamResult.get_indexes():
            await db["exam_results"].create_index(idx["key"], name=idx["name"], unique=idx.get("unique", False))
