import asyncio
import motor.motor_asyncio
from dotenv import load_dotenv
import os

load_dotenv("d:/Satr_Edu_Ai/.env")

async def main():
    client = motor.motor_asyncio.AsyncIOMotorClient("mongodb://admin:admin@localhost:27017")
    db = client["Satr-Edu"]
    count = await db["chunks"].count_documents({"chunk_project_id": "52657158-43e1-4646-ab38-1d9e83dc1a2d"})
    print(f"FOUND {count} CHUNKS IN MONGODB")
    
    # Just grab one to prove it exists
    if count > 0:
        doc = await db["chunks"].find_one({"chunk_project_id": "52657158-43e1-4646-ab38-1d9e83dc1a2d"})
        print(f"Sample chunk_id: {doc.get('chunk_id')}")
        print(f"Sample length: {len(doc.get('chunk_text', ''))}")
    
asyncio.run(main())
