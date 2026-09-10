from motor.motor_asyncio import AsyncIOMotorClient
from src.models.scheme_db.user import User
from src.models.enums.UserRole import UserRole
from src.helpers.config import get_settings
from typing import Optional, List
from datetime import datetime


class UserModel:

    def __init__(self, client: AsyncIOMotorClient):
        self.client = client
        self.db = client[get_settings().MONGODB_DATABASE]
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

    async def activate_user(self, user_id: str) -> bool:
        result = await self.collection.update_one(
            {"user_id": user_id},
            {"$set": {"is_active": True, "updated_at": datetime.now()}}
        )
        return result.modified_count > 0

    async def delete_user(self, user_id: str) -> bool:
        result = await self.collection.delete_one({"user_id": user_id})
        return result.deleted_count > 0

    async def get_all_users(
        self,
        role_filter: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> List[User]:
        query = {}
        if role_filter:
            query["user_role"] = role_filter
        skip = (page - 1) * page_size
        cursor = self.collection.find(query).skip(skip).limit(page_size)
        docs = await cursor.to_list(length=page_size)
        users = []
        for doc in docs:
            doc.pop("_id", None)
            users.append(User(**doc))
        return users

    async def count_users(self, role_filter: Optional[str] = None) -> int:
        query = {"user_role": role_filter} if role_filter else {}
        return await self.collection.count_documents(query)
