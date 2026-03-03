"""数据持久化模块：仅支持MySQL存储，提供统一数据访问接口"""
from .base import BaseStorage, StorageType
from .models import (
    MusicModel, PlaylistModel, MusicSheetModel, 
    PlayHistoryModel, SearchHistoryModel
)

# 强制导入MySQL存储（不再捕获导入异常）
from .mysql_storage import MySQLStorage

# 全局存储实例 - 仅使用MySQL
from core.constants import app_config, logger

# 忽略配置文件中的存储类型，强制使用MySQL
logger.info("数据持久化模块初始化：强制使用MySQL存储")
storage = MySQLStorage()

__all__ = [
    "BaseStorage", "StorageType", "MySQLStorage",
    "MusicModel", "PlaylistModel", "MusicSheetModel",
    "PlayHistoryModel", "SearchHistoryModel", "storage"
]