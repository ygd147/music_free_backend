"""事件总线：深度集成 MySQL 存储的消息/状态管理核心"""
import threading
from typing import Dict, List, Callable, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime

# 【修复1】统一在顶部导入所有依赖
from core.constants import logger, RepeatMode, mysql_config
from core.storage import MySQLStorage
# 直接导入模型类，用于删除操作
from core.storage.mysql_storage import DB_MusicSheet, sheet_music
from core.storage.models import generate_id, MusicModel
# 【关键修复2】导入 text 用于执行原生 SQL
from sqlalchemy import delete, text
from core.plugin_manager import plugin_manager, SearchResult
from core.player import audio_player, PlaybackEvent

# ========== 线程安全配置 ==========
_STORAGE_LOCK = threading.RLock()

# ========== 核心数据模型（增强版） ==========
@dataclass
class MusicItem:
    """增强版歌曲数据模型"""
    id: str
    name: str
    artist: str
    album: str = ""
    duration: int = 0
    url: str = ""
    lyric: str = ""
    cover: str = ""
    source: str = ""
    create_time: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    update_time: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MusicItem":
        if not data:
            return None
        return cls(
            id=data.get("id", generate_id("m")),
            name=data.get("name", ""),
            artist=data.get("artist", ""),
            album=data.get("album", ""),
            duration=int(data.get("duration", 0)),
            url=data.get("url", ""),
            lyric=data.get("lyric", ""),
            cover=data.get("cover", ""),
            source=data.get("source", ""),
            create_time=data.get("create_time", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            update_time=data.get("update_time", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id, "name": self.name, "artist": self.artist,
            "album": self.album, "duration": self.duration, "url": self.url,
            "lyric": self.lyric, "cover": self.cover, "source": self.source,
            "create_time": self.create_time, "update_time": self.update_time
        }

@dataclass
class AppState:
    """应用状态模型"""
    current_music: Optional[MusicItem] = None
    player_state: str = "paused"
    repeat_mode: int = RepeatMode.Queue
    volume: int = 100
    current_position: int = 0
    
    playlist_id: str = "default"
    active_sheet_id: Optional[str] = None
    
    _playlist_cache: List[MusicItem] = field(default_factory=list)
    _sheets_cache: List[Dict[str, Any]] = field(default_factory=list)
    _cache_ttl: int = 300
    _last_cache_update: float = field(default_factory=lambda: datetime.now().timestamp())

# ========== 核心 MessageBus 类 ==========
class MessageBus:
    def __init__(self):
        # 1. 强制初始化 MySQL
        self.mysql_storage = self._init_mysql_storage()
        
        # 2. 应用状态
        self.app_state = AppState()
        
        # 3. 命令注册
        self._commands: Dict[str, Callable] = {}
        self._init_commands()
        
        # 4. 加载数据
        self._load_from_mysql()
        
        # 5. 启动缓存刷新
        self._start_cache_refresh()
        
        logger.info("MessageBus 初始化完成 (纯 MySQL 模式)")

    def _init_player_integration(self):
        """初始化播放器集成"""
        # 注册播放器事件到MessageBus
        audio_player.register_event_callback(PlaybackEvent.EVENT_PROGRESS, self._on_player_progress)
        audio_player.register_event_callback(PlaybackEvent.EVENT_END, self._on_player_end)
        
        # 注册播放器相关命令
        self._commands.update({
            "PlayerPlay": self._player_play,
            "PlayerPause": self._player_pause,
            "PlayerResume": self._player_resume,
            "PlayerStop": self._player_stop,
            "PlayerNext": self._player_next,
            "PlayerPrev": self._player_prev,
            "PlayerSetVolume": self._player_set_volume,
            "PlayerSeek": self._player_seek,
            "PlayerSetMode": self._player_set_mode
        })
    
    def _player_play(self, source: str = None):
        """播放音频"""
        success = audio_player.play(source)
        if success and source:
            # 更新应用状态
            self.app_state.current_music = MusicItem.from_dict({"id": hash(source), "name": source})
            self.app_state.player_state = "playing"
        return success
    def _init_plugin_commands(self):
        """注册插件相关命令"""
        self._commands.update({
            "SearchMusicByPlugin": self._search_music_by_plugin,
            "GetPlayUrl": self._get_play_url,
            "GetLyric": self._get_lyric,
            "GetPluginsInfo": self._get_plugins_info
        })

    def _search_music_by_plugin(self, keyword: str, source: str = None):
        """通过插件搜索歌曲并保存到MySQL"""
        results = plugin_manager.search(keyword, source)
        
        # 将搜索结果保存到MySQL
        music_ids = []
        for result in results:
            music_data = {
                "id": result.id,
                "name": result.name,
                "artist": result.artist,
                "album": result.album,
                "duration": result.duration,
                "cover": result.cover,
                "source": result.source,
                "url": result.url,
                "lyric": result.lyric
            }
            music_id = self.mysql_storage.save_music(music_data)
            music_ids.append(music_id)
        
        return music_ids
    def _init_mysql_storage(self) -> MySQLStorage:
        """强制初始化 MySQL 存储"""
        try:
            storage_instance = MySQLStorage()
            logger.info(f"MySQL 存储连接成功：{mysql_config.host}:{mysql_config.port}/{mysql_config.database}")
            
            # 预检模型对象合法性
            if not hasattr(sheet_music, 'c'):
                raise RuntimeError("sheet_music 不是合法的 SQLAlchemy Table 对象")
            if not hasattr(DB_MusicSheet, '__table__'):
                raise RuntimeError("DB_MusicSheet 不是合法的 SQLAlchemy Model 对象")
                
            return storage_instance
        except Exception as e:
            logger.critical(f"MySQL 存储初始化失败，程序终止：{e}", exc_info=True)
            # 包装错误信息，提示用户检查 mysql_storage.py 中的 text() 修复
            error_msg = str(e)
            if "Not an executable object" in error_msg:
                logger.critical(">>> 关键提示：请在 core/storage/mysql_storage.py 中，将 conn.execute('CREATE DATABASE...') 修改为 conn.execute(text('CREATE DATABASE...'))")
            raise RuntimeError(f"无法连接 MySQL 数据库：{e}")

    def _init_commands(self):
        """注册所有支持的命令"""
        self._commands.update({
            "PlayMusic": self._play_music,
            "PauseMusic": self._pause_music,
            "ResumeMusic": self._resume_music,
            "StopMusic": self._stop_music,
            "SkipToNext": self._skip_to_next,
            "SkipToPrevious": self._skip_to_prev,
            "SetRepeatMode": self._set_repeat_mode,
            "SetVolume": self._set_volume,
            "SeekToPosition": self._seek_to_position,
            "SetAudioDevice": self._set_audio_device,
            "AddToPlaylist": self._add_to_playlist,
            "RemoveFromPlaylist": self._remove_from_playlist,
            "ClearPlaylist": self._clear_playlist,
            "ReorderPlaylist": self._reorder_playlist,
            "CreatePlaylist": self._create_playlist,
            "DeletePlaylist": self._delete_playlist,
            "CreateMusicSheet": self._create_music_sheet,
            "UpdateMusicSheet": self._update_music_sheet,
            "DeleteMusicSheet": self._delete_music_sheet, # 已修复缩进
            "AddToMusicSheet": self._add_to_music_sheet,
            "RemoveFromMusicSheet": self._remove_from_music_sheet,
            "SyncMusicSheets": self._sync_music_sheets,
            "SavePlayHistory": self._save_play_history,
            "ClearPlayHistory": self._clear_play_history,
            "SaveSearchHistory": self._save_search_history,
            "ClearSearchHistory": self._clear_search_history,
            "SaveMusic": self._save_music,
            "DeleteMusic": self._delete_music,
            "SearchMusic": self._search_music,
            "GetAppState": self._get_app_state,
            "RefreshCache": self._refresh_cache
        })

    # ========== 命令具体实现 ==========
    
    def _set_repeat_mode(self, mode: int):
        with _STORAGE_LOCK:
            self.app_state.repeat_mode = mode
            logger.info(f"重复模式已设置为：{mode}")

    def _set_volume(self, volume: int):
        with _STORAGE_LOCK:
            self.app_state.volume = max(0, min(100, volume))
            logger.info(f"音量已设置为：{self.app_state.volume}")

    def _seek_to_position(self, position: int):
        with _STORAGE_LOCK:
            self.app_state.current_position = max(0, position)
            if self.app_state.current_music:
                logger.info(f"跳转到：{self.app_state.current_music.name} ({position}s)")

    def _set_audio_device(self, device_name: str):
        logger.info(f"音频设备已切换至：{device_name}")

    def _create_playlist(self, name: str, playlist_id: Optional[str] = None):
        with _STORAGE_LOCK:
            try:
                pid = playlist_id or generate_id("p")
                self.mysql_storage.save_playlist({"id": pid, "name": name})
                logger.info(f"播放列表已创建：{pid} - {name}")
                return pid
            except Exception as e:
                logger.error(f"创建播放列表失败：{e}")
                return None

    def _delete_playlist(self, playlist_id: str):
        with _STORAGE_LOCK:
            if playlist_id == "default":
                logger.warning("默认播放列表不可删除")
                return False
            logger.warning(f"删除播放列表 {playlist_id} 暂仅清空内容")
            return self._clear_playlist(playlist_id)

    def _update_music_sheet(self, sheet_info: Dict[str, Any]):
        with _STORAGE_LOCK:
            try:
                self.mysql_storage.save_music_sheet(sheet_info)
                self._refresh_sheets_cache()
                return True
            except Exception as e:
                logger.error(f"更新歌单失败：{e}")
                return False

    def _add_to_music_sheet(self, sheet_id: str, music_id: str):
        with _STORAGE_LOCK:
            try:
                sheet_data = self.mysql_storage.get_music_sheet_by_id(sheet_id)
                if sheet_data:
                    current_ids = sheet_data.get("music_ids", [])
                    if music_id not in current_ids:
                        current_ids.append(music_id)
                        self.mysql_storage.save_music_sheet({"id": sheet_id, "music_ids": current_ids})
                        self._refresh_sheets_cache()
                        return True
                return False
            except Exception as e:
                logger.error(f"添加歌曲到歌单失败：{e}")
                return False

    def _remove_from_music_sheet(self, sheet_id: str, music_id: str):
        with _STORAGE_LOCK:
            try:
                sheet_data = self.mysql_storage.get_music_sheet_by_id(sheet_id)
                if sheet_data:
                    current_ids = sheet_data.get("music_ids", [])
                    if music_id in current_ids:
                        current_ids.remove(music_id)
                        self.mysql_storage.save_music_sheet({"id": sheet_id, "music_ids": current_ids})
                        self._refresh_sheets_cache()
                        return True
                return False
            except Exception as e:
                logger.error(f"从歌单移除歌曲失败：{e}")
                return False

    def _sync_music_sheets(self):
        self._refresh_sheets_cache()
        logger.info("歌单已同步")

    def _clear_play_history(self):
        logger.warning("清空播放历史功能需扩展 Storage 接口")
        return False

    def _clear_search_history(self):
        logger.warning("清空搜索历史功能需扩展 Storage 接口")
        return False

    def _delete_music(self, music_id: str):
        with _STORAGE_LOCK:
            try:
                success = self.mysql_storage.delete_music(music_id)
                if success:
                    self._refresh_playlist_cache()
                    logger.info(f"歌曲已删除：{music_id}")
                return success
            except Exception as e:
                logger.error(f"删除歌曲失败：{e}")
                return False

    # ========== 核心业务逻辑 ==========

    def _load_from_mysql(self):
        with _STORAGE_LOCK:
            try:
                playlist_data = self.mysql_storage.get_playlist(self.app_state.playlist_id)
                if playlist_data and "musics" in playlist_data:
                    self.app_state._playlist_cache = [
                        MusicItem.from_dict(m) for m in playlist_data["musics"] if m
                    ]
                
                self.app_state._sheets_cache = self.mysql_storage.get_all_music_sheets() or []
                
                history = self.mysql_storage.get_play_history(limit=1)
                if history and len(history) > 0 and history[0].get("music"):
                    self.app_state.current_music = MusicItem.from_dict(history[0]["music"])
                    
            except Exception as e:
                logger.error(f"初始化加载数据失败：{e}", exc_info=True)
                self.app_state._playlist_cache = [
                    MusicItem(id=generate_id("m"), name="默认测试歌曲", artist="测试歌手")
                ]

    def _start_cache_refresh(self):
        def loop():
            import time
            while True:
                time.sleep(self.app_state._cache_ttl)
                try:
                    self._refresh_cache()
                except Exception as e:
                    logger.error(f"缓存刷新异常：{e}")
        t = threading.Thread(target=loop, daemon=True, name="CacheRefresh")
        t.start()

    def _play_music(self, music: Dict[str, Any]):
        with _STORAGE_LOCK:
            try:
                music_id = music.get("id") or generate_id("m")
                music["id"] = music_id
                self.mysql_storage.save_music(music)
                
                music_item = MusicItem.from_dict(music)
                self.app_state.current_music = music_item
                self.app_state.player_state = "playing"
                self.app_state.current_position = 0
                
                if not any((item and item.id == music_id) for item in self.app_state._playlist_cache):
                    self.mysql_storage.add_music_to_playlist(self.app_state.playlist_id, music_id)
                    self._refresh_playlist_cache_internal()
                
                self._do_save_play_history(music_id)
                logger.info(f"播放：{music_item.name}")
            except Exception as e:
                logger.error(f"播放失败：{e}", exc_info=True)
                raise

    def _pause_music(self):
        self.app_state.player_state = "paused"
        logger.info("暂停播放")

    def _resume_music(self):
        self.app_state.player_state = "playing"
        logger.info("恢复播放")

    def _stop_music(self):
        self.app_state.player_state = "stopped"
        self.app_state.current_position = 0
        logger.info("停止播放")

    def _skip_to_next(self):
        with _STORAGE_LOCK:
            if not self.app_state._playlist_cache:
                return
            curr_idx = self._get_current_music_idx()
            next_idx = (curr_idx + 1) % len(self.app_state._playlist_cache)
            self.app_state.current_music = self.app_state._playlist_cache[next_idx]
            self.app_state.player_state = "playing"
            self.app_state.current_position = 0
            if self.app_state.current_music:
                self._do_save_play_history(self.app_state.current_music.id)

    def _skip_to_prev(self):
        with _STORAGE_LOCK:
            if not self.app_state._playlist_cache:
                return
            curr_idx = self._get_current_music_idx()
            prev_idx = (curr_idx - 1) % len(self.app_state._playlist_cache)
            self.app_state.current_music = self.app_state._playlist_cache[prev_idx]
            self.app_state.player_state = "playing"
            self.app_state.current_position = 0
            if self.app_state.current_music:
                self._do_save_play_history(self.app_state.current_music.id)

    def _add_to_playlist(self, music: Dict[str, Any], playlist_id: str = "default"):
        with _STORAGE_LOCK:
            try:
                mid = self.mysql_storage.save_music(music)
                if self.mysql_storage.add_music_to_playlist(playlist_id, mid):
                    self._refresh_playlist_cache_internal()
                    return True
                return False
            except Exception as e:
                logger.error(e)
                return False

    def _remove_from_playlist(self, music_id: str, playlist_id: str = "default"):
        with _STORAGE_LOCK:
            try:
                if self.mysql_storage.remove_music_from_playlist(playlist_id, music_id):
                    self._refresh_playlist_cache_internal()
                    if self.app_state.current_music and self.app_state.current_music.id == music_id:
                        self.app_state.player_state = "stopped"
                    return True
                return False
            except Exception as e:
                logger.error(e)
                return False

    def _clear_playlist(self, playlist_id: str = "default"):
        with _STORAGE_LOCK:
            try:
                p_data = self.mysql_storage.get_playlist(playlist_id)
                if p_data:
                    for m in p_data.get("musics", []):
                        if m:
                            self.mysql_storage.remove_music_from_playlist(playlist_id, m['id'])
                    self._refresh_playlist_cache_internal()
                    self.app_state.current_music = None
                    self.app_state.player_state = "stopped"
                return True
            except Exception as e:
                logger.error(e)
                return False

    def _reorder_playlist(self, playlist_id: str, music_ids: List[str]):
        with _STORAGE_LOCK:
            try:
                self.mysql_storage.save_playlist({"id": playlist_id, "music_ids": music_ids})
                self._refresh_playlist_cache_internal()
                return True
            except Exception as e:
                logger.error(e)
                return False

    def _create_music_sheet(self, sheet_info: Dict[str, Any]):
        with _STORAGE_LOCK:
            try:
                sid = sheet_info.get("id") or generate_id("s")
                sheet_info["id"] = sid
                self.mysql_storage.save_music_sheet(sheet_info)
                self._refresh_sheets_cache_internal()
                return sid
            except Exception as e:
                logger.error(e)
                return None

    # 【修复3】修正缩进，确保此方法在类内部
    def _delete_music_sheet(self, sheet_id: str):
        """删除歌单 (使用 text() 修复 SQL 执行错误)"""
        with _STORAGE_LOCK:
            try:
                sheet_data = self.mysql_storage.get_music_sheet_by_id(sheet_id)
                if not sheet_data:
                    logger.warning(f"歌单 {sheet_id} 不存在")
                    return False
                
                session = self.mysql_storage.Session()
                try:
                    session.begin()
                    
                    # 方式 A: 使用 SQLAlchemy Core delete (推荐)
                    # 确保 sheet_music 是 Table 对象
                    session.execute(delete(sheet_music).where(sheet_music.c.sheet_id == sheet_id))
                    
                    # 方式 B: 使用 text() 执行原生 SQL (最稳妥，避免 ORM 映射问题)
                    # session.execute(text("DELETE FROM sheet_music WHERE sheet_id = :sid"), {"sid": sheet_id})
                    
                    session.execute(delete(DB_MusicSheet).where(DB_MusicSheet.id == sheet_id))
                    # 或者: session.execute(text("DELETE FROM music_sheet WHERE id = :sid"), {"sid": sheet_id})
                    
                    session.commit()
                    self._refresh_sheets_cache_internal()
                    logger.info(f"歌单 {sheet_id} 已成功删除")
                    return True
                    
                except Exception as e:
                    session.rollback()
                    logger.error(f"删除歌单事务回滚：{e}", exc_info=True)
                    raise
                finally:
                    session.close()
                    
            except Exception as e:
                logger.error(f"删除歌单失败：{e}", exc_info=True)
                return False

    def _save_play_history(self, music_id: str):
        with _STORAGE_LOCK:
            return self._do_save_play_history(music_id)

    def _do_save_play_history(self, music_id: str):
        try:
            duration = self.app_state.current_position
            self.mysql_storage.save_play_history(music_id, duration)
            return True
        except Exception as e:
            logger.error(f"保存历史失败：{e}")
            return False

    def _save_search_history(self, keyword: str):
        with _STORAGE_LOCK:
            try:
                return self.mysql_storage.save_search_history(keyword)
            except Exception as e:
                logger.error(e)
                return False

    def _save_music(self, music: Dict[str, Any]) -> str:
        with _STORAGE_LOCK:
            return self.mysql_storage.save_music(music)

    def _search_music(self, keyword: str) -> List[Dict[str, Any]]:
        try:
            return self.mysql_storage.search_music(keyword)
        except Exception as e:
            logger.error(e)
            return []

    def _get_app_state(self) -> Dict[str, Any]:
        return {
            "current_music": self.app_state.current_music.to_dict() if self.app_state.current_music else None,
            "player_state": self.app_state.player_state,
            "repeat_mode": self.app_state.repeat_mode,
            "volume": self.app_state.volume,
            "current_position": self.app_state.current_position,
            "storage_type": "mysql",
            "playlist_count": len(self.app_state._playlist_cache),
            "sheets_count": len(self.app_state._sheets_cache)
        }

    def _get_current_music_idx(self) -> int:
        if not self.app_state.current_music:
            return 0
        for i, item in enumerate(self.app_state._playlist_cache):
            if item and item.id == self.app_state.current_music.id:
                return i
        return 0

    def _refresh_playlist_cache_internal(self):
        try:
            data = self.mysql_storage.get_playlist(self.app_state.playlist_id)
            if data and "musics" in data:
                self.app_state._playlist_cache = [MusicItem.from_dict(m) for m in data["musics"] if m]
                self.app_state._last_cache_update = datetime.now().timestamp()
        except Exception as e:
            logger.error(f"刷新列表缓存失败：{e}")

    def _refresh_sheets_cache_internal(self):
        try:
            self.app_state._sheets_cache = self.mysql_storage.get_all_music_sheets() or []
            self.app_state._last_cache_update = datetime.now().timestamp()
        except Exception as e:
            logger.error(f"刷新歌单缓存失败：{e}")

    def _refresh_playlist_cache(self, playlist_id: str = None):
        with _STORAGE_LOCK:
            self._refresh_playlist_cache_internal()

    def _refresh_sheets_cache(self):
        with _STORAGE_LOCK:
            self._refresh_sheets_cache_internal()

    def _refresh_cache(self):
        self._refresh_playlist_cache_internal()
        self._refresh_sheets_cache_internal()

    def send_command(self, cmd: str, *args, **kwargs) -> Any:
        if cmd not in self._commands:
            logger.warning(f"未知命令：{cmd}")
            return None
        try:
            return self._commands[cmd](*args, **kwargs)
        except Exception as e:
            logger.error(f"命令执行失败 {cmd}: {e}", exc_info=True)
            return None

    def get_playlist(self, playlist_id: str = "default") -> List[MusicItem]:
        self._refresh_playlist_cache(playlist_id)
        return self.app_state._playlist_cache

    def get_music_sheets(self) -> List[Dict[str, Any]]:
        self._refresh_sheets_cache()
        return self.app_state._sheets_cache
    
    def get_play_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        return self.mysql_storage.get_play_history(limit)

    def get_search_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        return self.mysql_storage.get_search_history(limit)

# 全局实例
message_bus = MessageBus()