import asyncio
import motor.motor_asyncio

async def main():
    client = motor.motor_asyncio.AsyncIOMotorClient("mongodb://admin:admin@localhost:27017")
    db = client["Satr-Edu"]
    count = await db["chunk"].count_documents({"chunk_project_id": "52657158-43e1-4646-ab38-1d9e83dc1a2d"})
    print(f"FOUND {count} CHUNKS IN MONGODB")
    
asyncio.run(main())
