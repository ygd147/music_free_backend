"""FFmpeg格式处理与解码工具"""
import os
import subprocess
import tempfile
import shutil
from typing import Optional, Dict, Any
from pathlib import Path

from core.constants import logger, app_config

# ========== FFmpeg配置 ==========
class FFmpegConfig:
    """FFmpeg配置"""
    def __init__(self):
        self.ffmpeg_path = app_config.get_config("PLAYER.ffmpeg_path") or shutil.which("ffmpeg")
        self.ffprobe_path = app_config.get_config("PLAYER.ffprobe_path") or shutil.which("ffprobe")
        self.cache_dir = Path(app_config.get_config("PLAYER.cache_dir") or tempfile.gettempdir()) / "music_free_cache"
        self.cache_dir.mkdir(exist_ok=True, parents=True)
        self.max_cache_size = int(app_config.get_config("PLAYER.max_cache_size") or 1024)  # MB

    def validate(self) -> bool:
        """验证FFmpeg是否可用"""
        if not self.ffmpeg_path or not os.path.exists(self.ffmpeg_path):
            logger.warning("FFmpeg未找到，将使用pygame原生解码")
            return False
        return True

# 全局FFmpeg配置
ffmpeg_config = FFmpegConfig()

# ========== FFmpeg核心工具 ==========
class FFmpegUtils:
    """FFmpeg工具类"""
    
    @staticmethod
    def get_audio_info(source: str) -> Optional[Dict[str, Any]]:
        """
        获取音频文件信息（时长、码率、格式等）
        :param source: 音频文件路径/URL
        :return: 音频信息字典
        """
        if not ffmpeg_config.validate():
            return None
        
        cmd = [
            ffmpeg_config.ffprobe_path,
            "-v", "error",
            "-show_entries", "format=duration,bit_rate,codec_name,filename",
            "-show_entries", "stream=sample_rate,channels",
            "-of", "json",
            source
        ]
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode != 0:
                logger.error(f"FFprobe获取音频信息失败：{result.stderr}")
                return None
            
            import json
            data = json.loads(result.stdout)
            
            # 解析关键信息
            format_info = data.get("format", {})
            stream_info = data.get("streams", [{}])[0]
            
            return {
                "duration": float(format_info.get("duration", 0)),
                "bit_rate": int(format_info.get("bit_rate", 0)) / 1000 if format_info.get("bit_rate") else 0,
                "codec": format_info.get("codec_name", ""),
                "sample_rate": int(stream_info.get("sample_rate", 0)),
                "channels": int(stream_info.get("channels", 0)),
                "filename": format_info.get("filename", "")
            }
            
        except Exception as e:
            logger.error(f"获取音频信息失败：{e}", exc_info=True)
            return None

    @staticmethod
    def convert_to_playable_format(source: str, output_format: str = "wav") -> Optional[str]:
        """
        转换音频格式为pygame可播放的格式
        :param source: 源音频路径/URL
        :param output_format: 目标格式（wav/mp3）
        :return: 转换后的文件路径
        """
        if not ffmpeg_config.validate():
            return source
        
        # 生成临时文件名
        temp_filename = f"converted_{hash(source)}.{output_format}"
        output_path = ffmpeg_config.cache_dir / temp_filename
        
        # 如果已转换过，直接返回
        if output_path.exists():
            return str(output_path)
        
        cmd = [
            ffmpeg_config.ffmpeg_path,
            "-i", source,
            "-vn",  # 禁用视频流
            "-acodec", "pcm_s16le" if output_format == "wav" else "mp3",
            "-y",  # 覆盖已有文件
            str(output_path)
        ]
        
        try:
            logger.info(f"开始转换音频格式：{source} -> {output_path}")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode != 0:
                logger.error(f"音频格式转换失败：{result.stderr}")
                if output_path.exists():
                    output_path.unlink()
                return None
            
            logger.info(f"音频格式转换完成：{output_path}")
            return str(output_path)
            
        except Exception as e:
            logger.error(f"转换音频格式失败：{e}", exc_info=True)
            if output_path.exists():
                output_path.unlink()
            return None

    @staticmethod
    def clear_cache():
        """清理转换缓存"""
        try:
            if ffmpeg_config.cache_dir.exists():
                total_size = 0
                for file in ffmpeg_config.cache_dir.glob("*"):
                    total_size += file.stat().st_size
                    file.unlink()
                
                logger.info(f"已清理FFmpeg缓存：{ffmpeg_config.cache_dir}，释放空间：{total_size/1024/1024:.2f}MB")
        except Exception as e:
            logger.error(f"清理FFmpeg缓存失败：{e}", exc_info=True)

    @staticmethod
    def check_cache_size() -> bool:
        """检查缓存大小，超过阈值则清理"""
        try:
            total_size = 0
            for file in ffmpeg_config.cache_dir.glob("*"):
                total_size += file.stat().st_size
            
            total_size_mb = total_size / 1024 / 1024
            if total_size_mb > ffmpeg_config.max_cache_size:
                logger.warning(f"缓存大小超过阈值：{total_size_mb:.2f}MB > {ffmpeg_config.max_cache_size}MB")
                FFmpegUtils.clear_cache()
                return True
            return False
        except Exception as e:
            logger.error(f"检查缓存大小失败：{e}", exc_info=True)
            return False

# 全局FFmpeg工具实例
ffmpeg_utils = FFmpegUtils()