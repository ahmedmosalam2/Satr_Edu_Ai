from motor.motor_asyncio import AsyncIOMotorClient
from typing import Optional, List
from datetime import datetime

from src.models.scheme_db.exam import Exam
from src.models.scheme_db.question import Question
from src.models.enums.ExamStatus import ExamStatus


class ExamModel:

    def __init__(self, client: AsyncIOMotorClient):
        self.client = client
        self.db = client["Satr-Edu"]
        self.exams = self.db["exams"]
        self.questions = self.db["questions"]

 

    async def create_exam(self, exam: Exam) -> bool:
        await self.exams.insert_one(exam.dict())
        return True

    async def get_exam(self, exam_id: str) -> Optional[Exam]:
        doc = await self.exams.find_one({"exam_id": exam_id})
        if not doc:
            return None
        doc.pop("_id", None)
        return Exam(**doc)

    async def list_exams_by_project(self, project_id: str) -> List[Exam]:
        cursor = self.exams.find({"project_id": project_id})
        exams = []
        async for doc in cursor:
            doc.pop("_id", None)
            exams.append(Exam(**doc))
        return exams

    async def list_approved_exams_by_project(self, project_id: str) -> List[Exam]:
        """للطلاب — يشوفوا الامتحانات المعتمدة فقط."""
        cursor = self.exams.find({
            "project_id": project_id,
            "status": ExamStatus.APPROVED.value
        })
        exams = []
        async for doc in cursor:
            doc.pop("_id", None)
            exams.append(Exam(**doc))
        return exams

    async def approve_exam(self, exam_id: str, teacher_id: str) -> bool:
        result = await self.exams.update_one(
            {"exam_id": exam_id, "teacher_id": teacher_id},
            {"$set": {
                "status": ExamStatus.APPROVED.value,
                "approved_at": datetime.now()
            }}
        )
        return result.modified_count > 0

 

    async def insert_questions(self, questions: List[Question]) -> bool:
        if not questions:
            return False
        docs = [q.dict() for q in questions]
        await self.questions.insert_many(docs)
        return True

    async def get_questions_by_exam(self, exam_id: str) -> List[Question]:
        cursor = self.questions.find({"exam_id": exam_id})
        questions = []
        async for doc in cursor:
            doc.pop("_id", None)
            questions.append(Question(**doc))
        return questions

    async def get_question(self, question_id: str) -> Optional[Question]:
        doc = await self.questions.find_one({"question_id": question_id})
        if not doc:
            return None
        doc.pop("_id", None)
        return Question(**doc)

   
    @classmethod
    async def create_indexes(cls, client: AsyncIOMotorClient):
        db = client["Satr-Edu"]
        for idx in Exam.get_indexes():
            await db["exams"].create_index(idx["key"], name=idx["name"], unique=idx.get("unique", False))
        for idx in Question.get_indexes():
            await db["questions"].create_index(idx["key"], name=idx["name"], unique=idx.get("unique", False))
