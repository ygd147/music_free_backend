"""音频播放器管理器（全局控制）"""
import threading
from typing import Optional, Dict, Any, Callable, List

from core.constants import logger
from .base import PlaybackState, PlaybackEvent
from .pygame_player import PygameAudioPlayer

# ========== 全局播放器管理器 ==========
class AudioPlayerManager:
    """
    播放器管理器
    功能：
    1. 全局单例播放器实例管理
    2. 播放队列管理
    3. 播放模式控制（顺序/循环/随机）
    4. 统一的播放控制接口
    """
    
    _instance: Optional["AudioPlayerManager"] = None
    _lock = threading.Lock()
    
    # 播放模式
    MODE_SEQUENCE = "sequence"    # 顺序播放
    MODE_LOOP = "loop"            # 单曲循环
    MODE_RANDOM = "random"        # 随机播放
    
    def __new__(cls):
        """单例模式"""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._init()
            return cls._instance

    def _init(self):
        """初始化管理器"""
        # 核心播放器实例
        self._player = PygameAudioPlayer()
        
        # 播放队列
        self._play_queue: List[Dict[str, Any]] = []
        self._current_queue_index = -1
        
        # 播放模式
        self._play_mode = self.MODE_SEQUENCE
        
        # 事件回调
        self._register_player_events()
        
        # 线程安全锁
        self._queue_lock = threading.RLock()
        
        logger.info("音频播放器管理器初始化完成")

    def _register_player_events(self):
        """注册播放器事件"""
        # 播放结束事件 - 自动播放下一曲
        def on_playback_end(event: PlaybackEvent):
            with self._queue_lock:
                if self._play_mode == self.MODE_LOOP and self._current_queue_index >= 0:
                    # 单曲循环 - 重新播放当前歌曲
                    current_item = self._play_queue[self._current_queue_index]
                    self.play(current_item["source"])
                else:
                    # 播放下一曲
                    self.play_next()
        
        # 错误事件处理
        def on_playback_error(event: PlaybackEvent):
            logger.error(f"播放错误：{event.data.get('error')}")
            self.play_next()
        
        # 注册事件
        self._player.register_callback(PlaybackEvent.EVENT_END, on_playback_end)
        self._player.register_callback(PlaybackEvent.EVENT_ERROR, on_playback_error)

    # ========== 播放队列管理 ==========
    def add_to_queue(self, items: List[Dict[str, Any]]):
        """
        添加歌曲到播放队列
        :param items: 歌曲列表，每个元素包含source、title、artist等信息
        """
        with self._queue_lock:
            self._play_queue.extend(items)
            logger.info(f"已添加{len(items)}首歌曲到播放队列，队列总数：{len(self._play_queue)}")

    def clear_queue(self):
        """清空播放队列"""
        with self._queue_lock:
            self._play_queue.clear()
            self._current_queue_index = -1
            logger.info("播放队列已清空")

    def get_queue(self) -> List[Dict[str, Any]]:
        """获取当前播放队列"""
        with self._queue_lock:
            return self._play_queue.copy()

    # ========== 播放控制 ==========
    def play(self, source: Optional[str] = None, start_position: float = 0.0) -> bool:
        """
        播放音频（支持指定源或播放队列中的歌曲）
        :param source: 音频源，None表示播放队列当前歌曲
        :param start_position: 起始位置（秒）
        :return: 是否成功
        """
        with self._queue_lock:
            # 如果指定了source，直接播放
            if source:
                # 查找source在队列中的位置
                for idx, item in enumerate(self._play_queue):
                    if item.get("source") == source:
                        self._current_queue_index = idx
                        break
                
                return self._player.play(source, start_position)
            
            # 没有指定source，播放队列中的歌曲
            if not self._play_queue:
                logger.warning("播放队列为空，无法播放")
                return False
            
            # 如果当前索引无效，从第一首开始
            if self._current_queue_index < 0 or self._current_queue_index >= len(self._play_queue):
                self._current_queue_index = 0
            
            # 播放当前队列歌曲
            current_item = self._play_queue[self._current_queue_index]
            return self._player.play(current_item["source"], start_position)

    def play_next(self) -> bool:
        """播放下一曲"""
        with self._queue_lock:
            if not self._play_queue:
                logger.warning("播放队列为空，无法播放下一曲")
                return False
            
            # 根据播放模式计算下一曲索引
            if self._play_mode == self.MODE_RANDOM:
                import random
                self._current_queue_index = random.randint(0, len(self._play_queue) - 1)
            else:
                self._current_queue_index = (self._current_queue_index + 1) % len(self._play_queue)
            
            # 播放下一曲
            next_item = self._play_queue[self._current_queue_index]
            logger.info(f"播放下一曲：{next_item.get('title', '未知歌曲')}")
            return self._player.play(next_item["source"])

    def play_prev(self) -> bool:
        """播放上一曲"""
        with self._queue_lock:
            if not self._play_queue:
                logger.warning("播放队列为空，无法播放上一曲")
                return False
            
            # 计算上一曲索引
            self._current_queue_index = (self._current_queue_index - 1) % len(self._play_queue)
            
            # 播放上一曲
            prev_item = self._play_queue[self._current_queue_index]
            logger.info(f"播放上一曲：{prev_item.get('title', '未知歌曲')}")
            return self._player.play(prev_item["source"])

    def pause(self) -> bool:
        """暂停播放"""
        return self._player.pause()

    def resume(self) -> bool:
        """恢复播放"""
        return self._player.resume()

    def stop(self) -> bool:
        """停止播放"""
        return self._player.stop()

    def seek(self, position: float) -> bool:
        """调整播放进度"""
        return self._player.seek(position)

    def set_volume(self, volume: int) -> bool:
        """设置音量"""
        return self._player.set_volume(volume)

    # ========== 播放模式控制 ==========
    def set_play_mode(self, mode: str) -> bool:
        """
        设置播放模式
        :param mode: 模式（sequence/loop/random）
        :return: 是否成功
        """
        if mode not in [self.MODE_SEQUENCE, self.MODE_LOOP, self.MODE_RANDOM]:
            logger.warning(f"无效的播放模式：{mode}")
            return False
        
        self._play_mode = mode
        mode_names = {
            self.MODE_SEQUENCE: "顺序播放",
            self.MODE_LOOP: "单曲循环",
            self.MODE_RANDOM: "随机播放"
        }
        logger.info(f"播放模式已设置为：{mode_names[mode]}")
        return True

    def get_play_mode(self) -> str:
        """获取当前播放模式"""
        return self._play_mode

    # ========== 状态查询 ==========
    def get_state(self) -> str:
        """获取播放状态"""
        return self._player.get_state()

    def get_current_source(self) -> Optional[str]:
        """获取当前播放源"""
        return self._player.get_current_source()

    def get_current_position(self) -> float:
        """获取当前播放位置"""
        return self._player.get_current_position()

    def get_duration(self) -> float:
        """获取当前音频时长"""
        return self._player.get_duration()

    def get_volume(self) -> int:
        """获取当前音量"""
        return self._player.get_volume()

    def is_playing(self) -> bool:
        """是否正在播放"""
        return self._player.is_playing()

    # ========== 事件注册 ==========
    def register_event_callback(self, event_type: str, callback: Callable):
        """注册播放器事件回调"""
        self._player.register_callback(event_type, callback)

    def unregister_event_callback(self, event_type: str, callback: Callable):
        """注销事件回调"""
        self._player.unregister_callback(event_type, callback)

    # ========== 资源管理 ==========
    def release(self):
        """释放播放器资源"""
        self.stop()
        self.clear_queue()
        self._player.release()
        logger.info("音频播放器管理器资源已释放")

# ========== 全局播放器实例 ==========
# 单例实例
audio_player = AudioPlayerManager()

# 程序退出时释放资源
import atexit
atexit.register(audio_player.release)