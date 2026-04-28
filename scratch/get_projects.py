import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv

async def get_projects():
    load_dotenv(".env")
    url = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
    db_name = os.getenv("MONGODB_DATABASE", "satr_edu")
    
    client = AsyncIOMotorClient(url)
    db = client[db_name]
    projects = await db.projects.find().to_list(10)
    for p in projects:
        print(f"Project ID: {p.get('project_id') or p.get('_id')} - Name: {p.get('name')}")
    client.close()

if __name__ == "__main__":
    asyncio.run(get_projects())
