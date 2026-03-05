"""插件管理器核心实现"""
import threading
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

from core.constants import logger
from .base import BaseMusicPlugin, SearchResult, PluginError, PluginExecuteError
from .utils import scan_plugins, load_plugin, validate_plugin

# ========== 线程安全配置 ==========
_LOCK = threading.RLock()

# ========== 插件管理器 ==========
class PluginManager:
    """
    插件管理器核心类
    功能：
    1. 自动扫描/加载/卸载插件
    2. 统一调度插件执行
    3. 管理插件状态和配置
    4. 提供插件注册/注销接口
    """
    
    def __init__(self):
        """初始化插件管理器"""
        # 插件存储：{插件名: 插件实例}
        self._plugins: Dict[str, BaseMusicPlugin] = {}
        # 插件配置缓存
        self._plugin_configs: Dict[str, Dict[str, Any]] = {}
        
        # 自动加载插件
        self.load_all_plugins()
        
        logger.info(f"插件管理器初始化完成，已加载{len(self._plugins)}个插件")

    # ========== 插件加载/卸载 ==========
    def load_all_plugins(self) -> List[str]:
        """加载所有可用插件"""
        with _LOCK:
            loaded_plugins = []
            
            try:
                # 扫描插件列表
                plugin_names = scan_plugins()
                
                for plugin_name in plugin_names:
                    if self.load_plugin(plugin_name):
                        loaded_plugins.append(plugin_name)
                
                return loaded_plugins
                
            except Exception as e:
                logger.error(f"加载所有插件失败：{e}", exc_info=True)
                return []

    def load_plugin(self, plugin_name: str) -> bool:
        """
        加载单个插件
        :param plugin_name: 插件名称
        :return: 是否加载成功
        """
        with _LOCK:
            try:
                # 检查是否已加载
                if plugin_name in self._plugins:
                    logger.warning(f"插件{plugin_name}已加载，跳过")
                    return True
                
                # 加载插件类
                plugin_class = load_plugin(plugin_name)
                
                # 创建插件实例
                plugin_instance = plugin_class()
                
                # 应用配置（如果有）
                if plugin_name in self._plugin_configs:
                    plugin_instance.configure(self._plugin_configs[plugin_name])
                
                # 验证插件
                if not validate_plugin(plugin_instance):
                    logger.warning(f"插件{plugin_name}验证失败，无法加载")
                    return False
                
                # 存储插件实例
                self._plugins[plugin_name] = plugin_instance
                
                logger.info(f"成功加载插件：{plugin_instance.meta.label}（{plugin_name} v{plugin_instance.meta.version}）")
                
                return True
                
            except Exception as e:
                logger.error(f"加载插件{plugin_name}失败：{e}", exc_info=True)
                return False

    def unload_plugin(self, plugin_name: str) -> bool:
        """
        卸载插件
        :param plugin_name: 插件名称
        :return: 是否卸载成功
        """
        with _LOCK:
            try:
                if plugin_name not in self._plugins:
                    logger.warning(f"插件{plugin_name}未加载，无需卸载")
                    return True
                
                # 移除插件实例
                plugin = self._plugins.pop(plugin_name)
                logger.info(f"已卸载插件：{plugin.meta.label}（{plugin_name}）")
                
                return True
                
            except Exception as e:
                logger.error(f"卸载插件{plugin_name}失败：{e}", exc_info=True)
                return False

    def reload_plugin(self, plugin_name: str) -> bool:
        """
        重新加载插件
        :param plugin_name: 插件名称
        :return: 是否成功
        """
        with _LOCK:
            # 先卸载
            self.unload_plugin(plugin_name)
            # 再加载
            return self.load_plugin(plugin_name)

    # ========== 插件配置 ==========
    def configure_plugin(self, plugin_name: str, config: Dict[str, Any]) -> bool:
        """
        配置插件
        :param plugin_name: 插件名称
        :param config: 配置参数
        :return: 是否成功
        """
        with _LOCK:
            try:
                # 保存配置
                self._plugin_configs[plugin_name] = config
                
                # 如果插件已加载，应用配置
                if plugin_name in self._plugins:
                    self._plugins[plugin_name].configure(config)
                    logger.info(f"已更新插件{plugin_name}的配置")
                
                return True
                
            except Exception as e:
                logger.error(f"配置插件{plugin_name}失败：{e}", exc_info=True)
                return False

    # ========== 插件执行 ==========
    def search(self, keyword: str, source: Optional[str] = None, 
               page: int = 1, limit: int = 20) -> List[SearchResult]:
        """
        搜索歌曲（支持指定平台或全平台）
        :param keyword: 搜索关键词
        :param source: 来源平台（插件名），None表示所有平台
        :param page: 页码
        :param limit: 每页数量
        :return: 合并后的搜索结果
        """
        with _LOCK:
            results: List[SearchResult] = []
            
            # 确定要执行的插件列表
            target_plugins = []
            if source:
                # 指定单个插件
                if source in self._plugins and self._plugins[source].enabled:
                    target_plugins = [self._plugins[source]]
                else:
                    logger.warning(f"插件{source}未加载或已禁用，无法搜索")
                    return results
            else:
                # 所有启用的插件
                target_plugins = [p for p in self._plugins.values() if p.enabled]
            
            # 执行搜索
            for plugin in target_plugins:
                try:
                    logger.debug(f"执行插件{plugin.meta.name}的搜索：{keyword}")
                    plugin_results = plugin.search(keyword, page, limit)
                    
                    # 补充来源信息
                    for result in plugin_results:
                        result.source = plugin.meta.name
                    
                    results.extend(plugin_results)
                    
                except Exception as e:
                    logger.error(f"插件{plugin.meta.name}搜索失败：{e}", exc_info=True)
                    raise PluginExecuteError(f"{plugin.meta.label}搜索失败：{str(e)}")
            
            logger.info(f"搜索完成：{keyword}，共找到{len(results)}条结果")
            return results

    def get_play_url(self, music_id: str, source: str) -> Optional[str]:
        """
        获取播放URL
        :param music_id: 歌曲ID
        :param source: 来源平台（插件名）
        :return: 播放URL或None
        """
        with _LOCK:
            try:
                if source not in self._plugins or not self._plugins[source].enabled:
                    logger.warning(f"插件{source}未加载或已禁用，无法获取播放URL")
                    return None
                
                plugin = self._plugins[source]
                if "play" not in plugin.meta.supported_features:
                    logger.warning(f"插件{source}不支持播放功能")
                    return None
                
                url = plugin.get_play_url(music_id)
                logger.debug(f"插件{source}获取的播放URL：{music_id} -> {url}")
                
                return url
                
            except Exception as e:
                logger.error(f"获取播放URL失败：{e}", exc_info=True)
                raise PluginExecuteError(f"获取播放URL失败：{str(e)}")

    def get_lyric(self, music_id: str, source: str) -> Optional[str]:
        """
        获取歌词
        :param music_id: 歌曲ID
        :param source: 来源平台（插件名）
        :return: 歌词或None
        """
        with _LOCK:
            try:
                if source not in self._plugins or not self._plugins[source].enabled:
                    logger.warning(f"插件{source}未加载或已禁用，无法获取歌词")
                    return None
                
                plugin = self._plugins[source]
                lyric = plugin.get_lyric(music_id)
                logger.debug(f"插件{source}获取歌词：{music_id} -> {len(lyric) if lyric else 0}字符")
                
                return lyric
                
            except Exception as e:
                logger.error(f"获取歌词失败：{e}", exc_info=True)
                raise PluginExecuteError(f"获取歌词失败：{str(e)}")

    def download_song(self, music_id: str, source: str, save_path: str) -> bool:
        """
        下载歌曲
        :param music_id: 歌曲ID
        :param source: 来源平台（插件名）
        :param save_path: 保存路径
        :return: 是否成功
        """
        with _LOCK:
            try:
                if source not in self._plugins or not self._plugins[source].enabled:
                    logger.warning(f"插件{source}未加载或已禁用，无法下载歌曲")
                    return False
                
                plugin = self._plugins[source]
                if "download" not in plugin.meta.supported_features:
                    logger.warning(f"插件{source}不支持下载功能")
                    return False
                
                success = plugin.download(music_id, save_path)
                logger.info(f"插件{source}下载歌曲{music_id}：{'成功' if success else '失败'}")
                
                return success
                
            except Exception as e:
                logger.error(f"下载歌曲失败：{e}", exc_info=True)
                raise PluginExecuteError(f"下载歌曲失败：{str(e)}")

    # ========== 插件状态管理 ==========
    def enable_plugin(self, plugin_name: str) -> bool:
        """启用插件"""
        with _LOCK:
            if plugin_name not in self._plugins:
                logger.warning(f"插件{plugin_name}未加载，无法启用")
                return False
            
            self._plugins[plugin_name].enabled = True
            logger.info(f"已启用插件：{plugin_name}")
            return True

    def disable_plugin(self, plugin_name: str) -> bool:
        """禁用插件"""
        with _LOCK:
            if plugin_name not in self._plugins:
                logger.warning(f"插件{plugin_name}未加载，无法禁用")
                return False
            
            self._plugins[plugin_name].enabled = False
            logger.info(f"已禁用插件：{plugin_name}")
            return True

    # ========== 插件信息查询 ==========
    def get_plugins_info(self) -> List[Dict[str, Any]]:
        """获取所有插件的信息"""
        with _LOCK:
            info_list = []
            for name, plugin in self._plugins.items():
                info_list.append({
                    "name": plugin.meta.name,
                    "label": plugin.meta.label,
                    "version": plugin.meta.version,
                    "author": plugin.meta.author,
                    "description": plugin.meta.description,
                    "supported_features": plugin.meta.supported_features,
                    "enabled": plugin.enabled,
                    "config": plugin.config
                })
            return info_list

    def get_plugin_by_name(self, plugin_name: str) -> Optional[BaseMusicPlugin]:
        """根据名称获取插件实例"""
        with _LOCK:
            return self._plugins.get(plugin_name)

# ========== 全局插件管理器实例 ==========
plugin_manager = PluginManager()