"""基于Pygame + FFmpeg的音频播放器实现"""
import time
import os
import threading
import pygame
from typing import Optional, Dict, Any

from core.constants import logger
from .base import BaseAudioPlayer, PlaybackState, PlaybackEvent
from .ffmpeg_utils import ffmpeg_utils

# ========== Pygame播放器实现 ==========
class PygameAudioPlayer(BaseAudioPlayer):
    """
    基于Pygame的音频播放器
    特性：
    1. 支持本地文件和网络URL播放
    2. 通过FFmpeg转换不支持的音频格式
    3. 实时进度更新
    4. 完整的播放控制接口
    """
    
    def __init__(self):
        super().__init__()
        
        # 初始化Pygame音频
        pygame.mixer.init(44100, -16, 2, 4096)
        pygame.mixer.set_num_channels(1)
        
        # 播放器内部状态
        self._audio_channel: Optional[pygame.mixer.Channel] = None
        self._audio_sound: Optional[pygame.mixer.Sound] = None
        self._play_thread: Optional[threading.Thread] = None
        self._stop_thread: bool = False
        self._progress_update_interval = 0.5  # 进度更新间隔（秒）
        
        # FFmpeg缓存检查
        ffmpeg_utils.check_cache_size()

    def play(self, source: str, start_position: float = 0.0) -> bool:
        """
        播放音频
        :param source: 音频源（音频文件路径或URL）
        :param start_position: 起始位置（秒）
        :return: 是否成功
        """
        # 停止当前播放
        self.stop()

        if not os.path.exists(source):
            logger.error(f"播放失败：文件不存在 {source}")
            raise FileNotFoundError(f"文件不存在：{source}")
        
        try:
            # 1. 更新状态为缓冲中
            self._state = PlaybackState.BUFFERING
            self._dispatch_event(PlaybackEvent.EVENT_BUFFERING, {"source": source})
            
            # 2. 转换音频格式（如果需要）
            playable_source = ffmpeg_utils.convert_to_playable_format(source)
            if not playable_source:
                playable_source = source
            
            # 3. 加载音频文件
            try:
                self._audio_sound = pygame.mixer.Sound(playable_source)
            except Exception as e:
                logger.error(f"Pygame加载音频失败，尝试使用FFmpeg转换：{e}")
                # 强制转换为WAV格式
                playable_source = ffmpeg_utils.convert_to_playable_format(source, "wav")
                if not playable_source:
                    raise Exception(f"无法加载音频：{source}")
                self._audio_sound = pygame.mixer.Sound(playable_source)
            
            # 4. 获取音频时长
            audio_info = ffmpeg_utils.get_audio_info(source)
            if audio_info:
                self._duration = audio_info["duration"]
            else:
                # 回退到Pygame的时长计算
                self._duration = self._audio_sound.get_length()
            
            # 5. 验证起始位置
            if start_position < 0 or start_position > self._duration:
                start_position = 0.0
            self._current_position = start_position
            
            # 6. 获取音频通道并播放
            self._audio_channel = pygame.mixer.Channel(0)
            self._audio_channel.set_volume(self._volume / 100)
            
            # 启动播放
            self._audio_channel.play(self._audio_sound)
            
            # 如果需要从指定位置开始播放
            if start_position > 0:
                self.seek(start_position)
            
            # 7. 更新状态
            self._state = PlaybackState.PLAYING
            self._current_source = source
            
            # 8. 启动进度更新线程
            self._stop_thread = False
            self._play_thread = threading.Thread(target=self._progress_monitor, daemon=True)
            self._play_thread.start()
            
            # 9. 分发播放事件
            self._dispatch_event(
                PlaybackEvent.EVENT_PLAY,
                {"source": source, "duration": self._duration, "start_position": start_position}
            )
            
            logger.info(f"开始播放音频：{source}（时长：{self._duration:.2f}秒）")
            return True
            
        except Exception as e:
            self._state = PlaybackState.ERROR
            self._dispatch_event(PlaybackEvent.EVENT_ERROR, {"error": str(e), "source": source})
            logger.error(f"播放音频失败：{e}", exc_info=True)
            return False

    def pause(self) -> bool:
        """暂停播放"""
        if self._state != PlaybackState.PLAYING or not self._audio_channel:
            return False
        
        try:
            self._audio_channel.pause()
            self._state = PlaybackState.PAUSED
            self._dispatch_event(PlaybackEvent.EVENT_PAUSE, {"position": self._current_position})
            logger.info(f"暂停播放：{self._current_source}（位置：{self._current_position:.2f}秒）")
            return True
        except Exception as e:
            logger.error(f"暂停播放失败：{e}", exc_info=True)
            return False

    def resume(self) -> bool:
        """恢复播放"""
        if self._state != PlaybackState.PAUSED or not self._audio_channel:
            return False
        
        try:
            self._audio_channel.unpause()
            self._state = PlaybackState.PLAYING
            self._dispatch_event(PlaybackEvent.EVENT_RESUME, {"position": self._current_position})
            logger.info(f"恢复播放：{self._current_source}（位置：{self._current_position:.2f}秒）")
            return True
        except Exception as e:
            logger.error(f"恢复播放失败：{e}", exc_info=True)
            return False

    def stop(self) -> bool:
        """停止播放"""
        if self._state == PlaybackState.STOPPED:
            return True
        
        try:
            # 停止进度线程
            self._stop_thread = True
            if self._play_thread and self._play_thread.is_alive():
                self._play_thread.join(timeout=1.0)
            
            # 停止音频播放
            if self._audio_channel:
                self._audio_channel.stop()
            
            # 释放音频资源
            if self._audio_sound:
                # Pygame没有直接释放Sound的方法，置空即可
                self._audio_sound = None
            
            # 更新状态
            prev_state = self._state
            self._state = PlaybackState.STOPPED
            self._current_position = 0.0
            
            # 分发事件
            if prev_state == PlaybackState.PLAYING:
                self._dispatch_event(PlaybackEvent.EVENT_STOP, {"source": self._current_source})
            
            logger.info(f"停止播放：{self._current_source}")
            return True
        except Exception as e:
            logger.error(f"停止播放失败：{e}", exc_info=True)
            return False

    def seek(self, position: float) -> bool:
        """调整播放进度"""
        if not self._audio_channel or not self._audio_sound:
            return False
        
        try:
            # 验证位置
            if position < 0 or position > self._duration:
                logger.warning(f"无效的播放位置：{position}（时长：{self._duration}）")
                return False
            
            # 暂停播放
            was_playing = self.is_playing()
            if was_playing:
                self._audio_channel.pause()
            
            # 计算样本位置
            sample_rate = pygame.mixer.get_init()[0]
            sample_pos = int(position * sample_rate)
            
            # 设置播放位置
            self._audio_channel.set_play_pos(sample_pos)
            self._current_position = position
            
            # 恢复播放（如果之前在播放）
            if was_playing:
                self._audio_channel.unpause()
            
            logger.debug(f"调整播放位置：{position:.2f}秒")
            return True
        except Exception as e:
            logger.error(f"调整播放进度失败：{e}", exc_info=True)
            return False

    def set_volume(self, volume: int) -> bool:
        """设置音量"""
        try:
            # 验证音量范围
            if volume < 0 or volume > 100:
                logger.warning(f"无效的音量值：{volume}（必须0-100）")
                return False
            
            self._volume = volume
            volume_float = volume / 100
            
            # 设置通道音量
            if self._audio_channel:
                self._audio_channel.set_volume(volume_float)
            
            logger.info(f"音量已设置为：{volume}%")
            return True
        except Exception as e:
            logger.error(f"设置音量失败：{e}", exc_info=True)
            return False

    def _progress_monitor(self):
        """进度监控线程"""
        last_position = 0.0
        
        while not self._stop_thread:
            try:
                if self._state == PlaybackState.PLAYING and self._audio_channel:
                    # 获取当前播放位置（秒）
                    if self._audio_channel.get_busy():
                        sample_pos = self._audio_channel.get_play_pos()
                        if sample_pos > 0:
                            sample_rate = pygame.mixer.get_init()[0]
                            self._current_position = sample_pos / sample_rate
                    else:
                        # 播放结束
                        self._current_position = self._duration
                        self.stop()
                        self._dispatch_event(PlaybackEvent.EVENT_END, {"source": self._current_source})
                        break
                    
                    # 定期分发进度事件
                    if abs(self._current_position - last_position) >= self._progress_update_interval:
                        self._dispatch_event(
                            PlaybackEvent.EVENT_PROGRESS,
                            {
                                "position": self._current_position,
                                "duration": self._duration,
                                "progress": (self._current_position / self._duration) * 100 if self._duration > 0 else 0
                            }
                        )
                        last_position = self._current_position
                
                # 休眠
                time.sleep(self._progress_update_interval / 2)
                
            except Exception as e:
                logger.error(f"进度监控线程异常：{e}", exc_info=True)
                break

    def release(self):
        """释放资源"""
        self.stop()
        pygame.mixer.quit()
        logger.info("Pygame播放器资源已释放")

    def __del__(self):
        """析构函数"""
        self.release()