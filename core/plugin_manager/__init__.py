"""插件管理器模块：加载和管理音乐平台插件"""
from .base import (
    BaseMusicPlugin, PluginMeta, SearchResult,
    PluginError, PluginLoadError, PluginExecuteError
)
from .manager import PluginManager, plugin_manager
from .utils import scan_plugins, load_plugin, validate_plugin

__all__ = [
    # 基类/模型
    "BaseMusicPlugin", "PluginMeta", "SearchResult",
    # 异常
    "PluginError", "PluginLoadError", "PluginExecuteError",
    # 核心管理器
    "PluginManager", "plugin_manager",
    # 工具函数
    "scan_plugins", "load_plugin", "validate_plugin"
]