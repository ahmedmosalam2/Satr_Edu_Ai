from enum import Enum


class AssetType(Enum):
    IMAGE='image'
    VIDEO='video'
    AUDIO='audio'
    TEXT='text'
    OTHER='other'
    FILE='file'
    PDF='pdf'