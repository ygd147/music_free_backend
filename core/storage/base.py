"""存储基类：定义统一的存储接口"""
from abc import ABC, abstractmethod
from enum import Enum
from typing import List, Dict, Optional, Any
from pathlib import Path
from core.constants import logger, app_config

# 存储类型枚举
class StorageType(Enum):
    SQLITE = "sqlite"
    FILE = "file"

class BaseStorage(ABC):
    """所有存储实现的基类"""
    def __init__(self):
        # 基础配置
        self.storage_dir = Path.home() / ".music_free" / "storage"
        self.storage_dir.mkdir(exist_ok=True, parents=True)
        self.logger = logger
        self._init_storage()

    @abstractmethod
    def _init_storage(self):
        """初始化存储（创建表/目录）"""
        pass

    # ========== 歌曲相关接口 ==========
    @abstractmethod
    def save_music(self, music: Dict[str, Any]) -> str:
        """保存歌曲信息，返回歌曲ID"""
        pass

    @abstractmethod
    def get_music_by_id(self, music_id: str) -> Optional[Dict[str, Any]]:
        """根据ID获取歌曲"""
        pass

    @abstractmethod
    def delete_music(self, music_id: str) -> bool:
        """删除歌曲"""
        pass

    @abstractmethod
    def search_music(self, keyword: str) -> List[Dict[str, Any]]:
        """搜索歌曲（名称/歌手）"""
        pass

    # ========== 播放列表相关接口 ==========
    @abstractmethod
    def save_playlist(self, playlist: Dict[str, Any]) -> str:
        """保存播放列表，返回列表ID"""
        pass

    @abstractmethod
    def get_playlist(self, playlist_id: str = "default") -> Optional[Dict[str, Any]]:
        """获取播放列表（默认获取默认列表）"""
        pass

    @abstractmethod
    def add_music_to_playlist(self, playlist_id: str, music_id: str) -> bool:
        """添加歌曲到播放列表"""
        pass

    @abstractmethod
    def remove_music_from_playlist(self, playlist_id: str, music_id: str) -> bool:
        """从播放列表移除歌曲"""
        pass

    # ========== 歌单相关接口 ==========
    @abstractmethod
    def save_music_sheet(self, sheet: Dict[str, Any]) -> str:
        """保存歌单，返回歌单ID"""
        pass

    @abstractmethod
    def get_all_music_sheets(self) -> List[Dict[str, Any]]:
        """获取所有歌单"""
        pass

    @abstractmethod
    def get_music_sheet_by_id(self, sheet_id: str) -> Optional[Dict[str, Any]]:
        """根据ID获取歌单"""
        pass

    # ========== 历史记录相关接口 ==========
    @abstractmethod
    def save_play_history(self, music_id: str, play_time: int = None) -> bool:
        """保存播放历史"""
        pass

    @abstractmethod
    def get_play_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """获取播放历史"""
        pass

    @abstractmethod
    def save_search_history(self, keyword: str) -> bool:
        """保存搜索历史"""
        pass

    @abstractmethod
    def get_search_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """获取搜索历史"""
        pass
    