"""音频播放器抽象接口定义"""
from abc import ABC, abstractmethod
from typing import Callable, Optional, Dict, Any
from dataclasses import dataclass

# ========== 播放状态定义 ==========
class PlaybackState:
    """播放状态枚举"""
    STOPPED = "stopped"    # 已停止
    PLAYING = "playing"    # 播放中
    PAUSED = "paused"      # 已暂停
    BUFFERING = "buffering"# 缓冲中
    ERROR = "error"        # 播放错误

# ========== 播放事件定义 ==========
@dataclass
class PlaybackEvent:
    """播放事件数据结构"""
    EVENT_PLAY = "play"                # 开始播放
    EVENT_PAUSE = "pause"              # 暂停播放
    EVENT_RESUME = "resume"            # 恢复播放
    EVENT_STOP = "stop"                # 停止播放
    EVENT_END = "end"                  # 播放结束
    EVENT_ERROR = "error"              # 播放错误
    EVENT_PROGRESS = "progress"        # 进度更新
    EVENT_BUFFERING = "buffering"      # 缓冲状态
    
    type: str
    data: Optional[Dict[str, Any]] = None

# ========== 播放器抽象基类 ==========
class BaseAudioPlayer(ABC):
    """所有音频播放器的抽象基类"""
    
    def __init__(self):
        # 事件回调注册表
        self._event_callbacks: Dict[str, List[Callable]] = {}
        # 当前播放状态
        self._state: str = PlaybackState.STOPPED
        # 当前播放的音频源
        self._current_source: Optional[str] = None
        # 播放进度（秒）
        self._current_position: float = 0.0
        # 音量（0-100）
        self._volume: int = 100
        # 音频时长（秒）
        self._duration: float = 0.0

    # ========== 事件注册/注销 ==========
    def register_callback(self, event_type: str, callback: Callable):
        """
        注册事件回调
        :param event_type: 事件类型（PlaybackEvent.EVENT_*）
        :param callback: 回调函数，接收PlaybackEvent参数
        """
        if event_type not in self._event_callbacks:
            self._event_callbacks[event_type] = []
        if callback not in self._event_callbacks[event_type]:
            self._event_callbacks[event_type].append(callback)

    def unregister_callback(self, event_type: str, callback: Callable):
        """注销事件回调"""
        if event_type in self._event_callbacks and callback in self._event_callbacks[event_type]:
            self._event_callbacks[event_type].remove(callback)

    def _dispatch_event(self, event_type: str, data: Optional[Dict[str, Any]] = None):
        """分发事件（内部使用）"""
        event = PlaybackEvent(type=event_type, data=data)
        if event_type in self._event_callbacks:
            for callback in self._event_callbacks[event_type]:
                try:
                    callback(event)
                except Exception as e:
                    print(f"事件回调执行失败：{e}")

    # ========== 抽象播放控制接口 ==========
    @abstractmethod
    def play(self, source: str, start_position: float = 0.0) -> bool:
        """
        播放音频
        :param source: 音频源（本地文件路径/网络URL）
        :param start_position: 起始播放位置（秒）
        :return: 是否成功
        """
        pass

    @abstractmethod
    def pause(self) -> bool:
        """暂停播放"""
        pass

    @abstractmethod
    def resume(self) -> bool:
        """恢复播放"""
        pass

    @abstractmethod
    def stop(self) -> bool:
        """停止播放"""
        pass

    @abstractmethod
    def seek(self, position: float) -> bool:
        """
        调整播放进度
        :param position: 目标位置（秒）
        :return: 是否成功
        """
        pass

    # ========== 音量控制接口 ==========
    @abstractmethod
    def set_volume(self, volume: int) -> bool:
        """
        设置音量（0-100）
        :param volume: 音量值
        :return: 是否成功
        """
        pass

    def get_volume(self) -> int:
        """获取当前音量"""
        return self._volume

    # ========== 状态查询接口 ==========
    def get_state(self) -> str:
        """获取当前播放状态"""
        return self._state

    def get_current_source(self) -> Optional[str]:
        """获取当前播放的音频源"""
        return self._current_source

    def get_current_position(self) -> float:
        """获取当前播放位置（秒）"""
        return self._current_position

    def get_duration(self) -> float:
        """获取音频总时长（秒）"""
        return self._duration

    def is_playing(self) -> bool:
        """是否正在播放"""
        return self._state == PlaybackState.PLAYING

    def is_paused(self) -> bool:
        """是否已暂停"""
        return self._state == PlaybackState.PAUSED

    # ========== 资源释放接口 ==========
    @abstractmethod
    def release(self):
        """释放播放器资源"""
        pass