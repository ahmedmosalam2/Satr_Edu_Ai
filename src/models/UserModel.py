from motor.motor_asyncio import AsyncIOMotorClient
from src.models.scheme_db.user import User
from src.models.enums.UserRole import UserRole
from typing import Optional
from datetime import datetime


class UserModel:

    def __init__(self, client: AsyncIOMotorClient):
        self.client = client
        self.db = client["Satr-Edu"]
        self.collection = self.db["users"]

    async def create_user(self, user: User) -> bool:
        user_dict = user.dict()
        await self.collection.insert_one(user_dict)
        return True

    async def get_user_by_email(self, email: str) -> Optional[User]:
        doc = await self.collection.find_one({"user_email": email})
        if not doc:
            return None
        doc.pop("_id", None)
        return User(**doc)

    async def get_user_by_id(self, user_id: str) -> Optional[User]:
        doc = await self.collection.find_one({"user_id": user_id})
        if not doc:
            return None
        doc.pop("_id", None)
        return User(**doc)

    async def approve_teacher(self, user_id: str) -> bool:
        result = await self.collection.update_one(
            {"user_id": user_id, "user_role": UserRole.TEACHER.value},
            {"$set": {"is_approved": True, "updated_at": datetime.now()}}
        )
        return result.modified_count > 0

    async def email_exists(self, email: str) -> bool:
        doc = await self.collection.find_one(
            {"user_email": email}, {"_id": 1}
        )
        return doc is not None

    async def deactivate_user(self, user_id: str) -> bool:
        result = await self.collection.update_one(
            {"user_id": user_id},
            {"$set": {"is_active": False, "updated_at": datetime.now()}}
        )
        return result.modified_count > 0
