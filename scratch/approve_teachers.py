import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

async def approve_teachers():
    client = AsyncIOMotorClient('mongodb://admin:admin@localhost:27017')
    db = client['Satr-Edu']
    result = await db['users'].update_many({'user_role': 'teacher'}, {'$set': {'is_approved': True}})
    print(f"Approved {result.modified_count} teachers!")
    client.close()

if __name__ == '__main__':
    asyncio.run(approve_teachers())
