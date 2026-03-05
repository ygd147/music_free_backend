"""插件基类与接口定义"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

# ========== 数据模型 ==========
@dataclass
class SearchResult:
    """统一的搜索结果模型"""
    id: str                  # 歌曲ID
    name: str                # 歌曲名称
    artist: str              # 歌手
    album: str = ""          # 专辑
    duration: int = 0        # 时长（秒）
    cover: str = ""          # 封面URL
    source: str = ""         # 来源平台（插件名）
    url: str = ""            # 播放URL（可选）
    lyric: str = ""          # 歌词（可选）

@dataclass
class PluginMeta:
    """插件元数据"""
    name: str                # 插件名称（如：netease）
    label: str               # 显示名称（如：网易云音乐）
    version: str = "1.0.0"   # 版本号
    author: str = ""         # 作者
    description: str = ""    # 描述
    supported_features: List[str] = None  # 支持的功能：search/play/download

# ========== 插件基类 ==========
class BaseMusicPlugin(ABC):
    """所有音乐平台插件必须继承的基类"""
    
    # 插件元数据（子类必须重写）
    meta: PluginMeta = PluginMeta(
        name="base",
        label="基础插件",
        supported_features=["search"]
    )
    
    def __init__(self):
        """初始化插件"""
        self.enabled = True  # 插件是否启用
        self.config: Dict[str, Any] = {}  # 插件配置
    
    @abstractmethod
    def search(self, keyword: str, page: int = 1, limit: int = 20) -> List[SearchResult]:
        """
        搜索歌曲（核心接口）
        :param keyword: 搜索关键词
        :param page: 页码
        :param limit: 每页数量
        :return: 统一格式的搜索结果列表
        """
        pass
    
    def get_play_url(self, music_id: str) -> Optional[str]:
        """
        获取播放URL（可选实现）
        :param music_id: 歌曲ID
        :return: 播放URL或None
        """
        return None
    
    def get_lyric(self, music_id: str) -> Optional[str]:
        """
        获取歌词（可选实现）
        :param music_id: 歌曲ID
        :return: 歌词文本或None
        """
        return None
    
    def download(self, music_id: str, save_path: str) -> bool:
        """
        下载歌曲（可选实现）
        :param music_id: 歌曲ID
        :param save_path: 保存路径
        :return: 是否成功
        """
        return False
    
    def configure(self, config: Dict[str, Any]) -> None:
        """
        配置插件
        :param config: 配置参数
        """
        self.config.update(config)
    
    def validate(self) -> bool:
        """
        验证插件是否可用
        :return: 是否有效
        """
        return True

# ========== 插件异常定义 ==========
class PluginError(Exception):
    """插件通用异常"""
    pass

class PluginLoadError(PluginError):
    """插件加载异常"""
    pass

class PluginExecuteError(PluginError):
    """插件执行异常"""
    pass