"""音频播放器内核模块：集成Pygame + FFmpeg的音频播放解决方案"""
from .base import (
    BaseAudioPlayer,
    PlaybackState,
    PlaybackEvent
)
from .pygame_player import PygameAudioPlayer
from .ffmpeg_utils import FFmpegUtils, ffmpeg_utils, ffmpeg_config
from .manager import AudioPlayerManager, audio_player

__all__ = [
    # 基础接口
    "BaseAudioPlayer",
    "PlaybackState",
    "PlaybackEvent",
    # 播放器实现
    "PygameAudioPlayer",
    # FFmpeg工具
    "FFmpegUtils",
    "ffmpeg_utils",
    "ffmpeg_config",
    # 管理器
    "AudioPlayerManager",
    "audio_player"
]