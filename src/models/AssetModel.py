from .BaseDataModel import BaseDataModel
from src.models.enums.DataBaseEnumProject import DataBaseEnumProject
from src.models.scheme_db import Asset


class AssetModel(BaseDataModel):
    def __init__(self, client: object = None, project_id: str = None):
        super().__init__(client)
        self.project_id = project_id
        self.collection = self.db[DataBaseEnumProject.ASSET.value] if self.db is not None else None

    @classmethod
    async def create_index(cls,db_client:object):
        instance=cls(client=db_client)
        await instance.init_collection()
        return instance
    
    async def init_collection(self):
        all_collections= await self.db.list_collection_names()
        if DataBaseEnumProject.ASSET.value not in all_collections:
            self.collection=self.db[DataBaseEnumProject.ASSET.value]
            indexes=Asset.get_indexes()

            for index in indexes:
                await self.collection.create_index(
                    index["key"],
                    unique=index["unique"],
                    name=index["name"]
                    )
    
    async def create_asset(self,asset:Asset):
        result= await self.collection.insert_one(asset.dict(by_alias=True,exclude_unset=True))
        asset._id=result.inserted_id
        return asset
    
    async def get_asset(self,asset_id:str):
        result= await self.collection.find_one({"asset_id":asset_id})
        if result is None:
            return None
        return Asset(**result)
    
    async def get_all_assets(self,project_id:str):
        result= await self.collection.find({
            "asset_project_id":project_id
            })
        return [Asset(**asset) async for asset in result]  

    
    async def update_asset(self,asset:Asset):
        result= await self.collection.update_one({"asset_id":asset.asset_id},
        update={"$set":asset.dict()})
        return result
    
    async def delete_asset(self,asset_id:str):
        result= await self.collection.delete_one({"asset_id":asset_id})
        return result
