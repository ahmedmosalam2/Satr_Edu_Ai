import asyncio
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient

async def seed_data():
    client = AsyncIOMotorClient("mongodb://admin:admin@localhost:27017")
    db = client["Satr-Edu"]
    
    student_id = "e75c9ff8-882c-4cdd-a1a0-ef181c71d25d"
    project_id = "project_123"
    
    await db["exam_results"].delete_many({"student_id": student_id})
    
    # Fake Exam Results
    fake_results = [
        {
            "result_id": "res_1",
            "student_id": student_id,
            "exam_id": "exam_1",
            "project_id": project_id,
            "total_score": 75,
            "max_score": 100,
            "percentage": 75.0,
            "weak_chunks": ["أساسيات معالجة اللغات الطبيعية"],
            "submitted_at": datetime.now()
        },
        {
            "result_id": "res_2",
            "student_id": student_id,
            "exam_id": "exam_2",
            "project_id": project_id,
            "total_score": 85,
            "max_score": 100,
            "percentage": 85.0,
            "weak_chunks": ["تحليل المشاعر باستخدام LLMs"],
            "submitted_at": datetime.now()
        },
        {
            "result_id": "res_3",
            "student_id": student_id,
            "exam_id": "exam_3",
            "project_id": project_id,
            "total_score": 60,
            "max_score": 100,
            "percentage": 60.0,
            "weak_chunks": ["الشبكات العصبية العميقة", "أساسيات معالجة اللغات الطبيعية"],
            "submitted_at": datetime.now()
        }
    ]
    
    # Insert results
    await db["exam_results"].insert_many(fake_results)
    print("✅ تم إضافة بيانات امتحانات وهمية للطالب بنجاح!")
    
    # Fake Exams for Teacher Overview / Leaderboard
    teacher_id = "teacher_123"
    fake_exams = [
        {"exam_id": "exam_1", "teacher_id": teacher_id, "project_id": project_id, "status": "approved", "exam_title": "امتحان 1"},
        {"exam_id": "exam_2", "teacher_id": teacher_id, "project_id": project_id, "status": "approved", "exam_title": "امتحان 2"},
        {"exam_id": "exam_3", "teacher_id": teacher_id, "project_id": project_id, "status": "approved", "exam_title": "امتحان 3"}
    ]
    
    # Optional: just to make sure leaderboard and teacher overview also work if they test them
    await db["exams"].insert_many(fake_exams)
    print("✅ تم إضافة بيانات الامتحانات بنجاح!")
    
    client.close()

if __name__ == "__main__":
    asyncio.run(seed_data())
