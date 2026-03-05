# core/local_music_manager.py
import os
import json
import threading
import math
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict
from pathlib import Path

# 引入 mutagen
from mutagen import File as MutagenFile
from mutagen.mp3 import MP3
from mutagen.flac import FLAC
from mutagen.id3 import ID3, TIT2, TPE1, TALB, TDRC
from mutagen.mp4 import MP4

# 支持的音乐格式
SUPPORTED_AUDIO_EXT = {".mp3", ".flac", ".wav", ".aac", ".m4a", ".ogg", ".wma"}

# 数据存储文件路径
DATA_FILE = Path("data/local_dirs.json")

# 线程锁，防止文件并发写入冲突
_file_lock = threading.Lock()


@dataclass
class LocalDirectory:
    """本地目录数据模型"""
    id: str
    path: str
    name: str  # 给目录起的别名


@dataclass
class MusicItem:
    """音乐文件数据模型 (增强版)"""
    id: str
    title: str
    artist: str
    album: str
    year: str
    duration: int  # 时长(秒)
    duration_str: str # 时长字符串 (mm:ss)
    path: str
    file_size: int
    bitrate: int # 比特率 (kbps)
    has_cover: bool # 是否包含封面


class LocalMusicManager:
    def __init__(self):
        self._ensure_data_file()

    def _ensure_data_file(self):
        """确保数据文件和目录存在"""
        DATA_FILE.parent.mkdir(exist_ok=True)
        if not DATA_FILE.exists():
            DATA_FILE.write_text(json.dumps([]), encoding="utf-8")

    def _load_dirs(self) -> List[Dict]:
        """从文件加载所有目录"""
        with _file_lock:
            try:
                return json.loads(DATA_FILE.read_text(encoding="utf-8"))
            except Exception:
                return []

    def _save_dirs(self, dirs: List[Dict]):
        """保存目录列表到文件"""
        with _file_lock:
            DATA_FILE.write_text(json.dumps(dirs, indent=2, ensure_ascii=False), encoding="utf-8")

    # ========== 工具函数：解析元数据 ==========
    def _extract_music_metadata(self, file_path: Path) -> Dict:
        """
        内部方法：使用 mutagen 提取文件元数据
        返回一个包含 metadata 的字典
        """
        info = {
            "title": file_path.stem,
            "artist": "未知艺术家",
            "album": "未知专辑",
            "year": "",
            "duration": 0,
            "duration_str": "00:00",
            "bitrate": 0,
            "has_cover": False
        }

        try:
            # 使用 Mutagen 打开文件
            f = MutagenFile(file_path, easy=True) # easy=True 简化标签访问
            
            if f is None:
                return info

            # 1. 获取时长 (通用)
            if f.info.length:
                info["duration"] = int(f.info.length)
                mins, secs = divmod(info["duration"], 60)
                info["duration_str"] = f"{mins:02d}:{secs:02d}"

            # 2. 获取比特率 (尽量获取)
            if hasattr(f.info, 'bitrate') and f.info.bitrate:
                info["bitrate"] = int(f.info.bitrate / 1000)

            # 3. 读取标签 (Title, Artist, Album, Year)
            # 'easy' 模式下，键名通常是统一的
            if 'title' in f: info["title"] = f['title'][0]
            if 'artist' in f: info["artist"] = f['artist'][0]
            if 'album' in f: info["album"] = f['album'][0]
            if 'date' in f: info["year"] = str(f['date'][0])[:4] # 只取年份

            # 4. 检查封面 (需要重新在非 easy 模式下打开，或者特定处理)
            # 这里做一个简单的封面检测，不提取图片二进制，只标记有无
            # 如果需要提取封面返回给前端，建议单独做一个 /cover API
            try:
                f_full = MutagenFile(file_path)
                if f_full:
                    # MP3 (ID3)
                    if hasattr(f_full, 'tags') and f_full.tags:
                        # 检查常见的封面帧
                        if 'APIC:' in str(f_full.tags) or hasattr(f_full.tags, 'getall') and f_full.tags.getall('APIC'):
                            info["has_cover"] = True
                    # MP4/M4A
                    elif isinstance(f_full, MP4):
                        if 'covr' in f_full:
                            info["has_cover"] = True
                    # FLAC
                    elif isinstance(f_full, FLAC):
                        if f_full.pictures:
                            info["has_cover"] = True
            except Exception:
                pass # 封面检测失败不影响主流程

        except Exception as e:
            # 文件损坏或格式不支持，保持默认值
            pass

        return info

    # ========== 目录 CRUD ==========
    def get_all_dirs(self) -> List[LocalDirectory]:
        """获取所有目录"""
        return [LocalDirectory(**d) for d in self._load_dirs()]

    def add_dir(self, path: str, name: Optional[str] = None) -> LocalDirectory:
        """添加一个新目录"""
        path = os.path.abspath(path)
        if not os.path.isdir(path):
            raise ValueError(f"路径不存在或不是目录: {path}")

        dirs = self._load_dirs()
        # 检查是否已添加
        for d in dirs:
            if d["path"] == path:
                raise ValueError("该目录已存在")

        new_dir = LocalDirectory(
            id=str(len(dirs) + 1),  # 简单ID生成
            path=path,
            name=name or os.path.basename(path)
        )
        dirs.append(asdict(new_dir))
        self._save_dirs(dirs)
        return new_dir

    def delete_dir(self, dir_id: str) -> bool:
        """删除目录"""
        dirs = self._load_dirs()
        new_dirs = [d for d in dirs if d["id"] != dir_id]
        if len(new_dirs) == len(dirs):
            return False
        self._save_dirs(new_dirs)
        return True

    # ========== 音乐扫描 (增强版) ==========
    def scan_music(self, dir_id: str) -> Dict:
        """扫描指定目录下的所有音乐，并解析元数据"""
        dirs = self._load_dirs()
        target_dir = next((d for d in dirs if d["id"] == dir_id), None)
        
        if not target_dir:
            raise ValueError("目录ID不存在")

        root_path = Path(target_dir["path"])
        music_list = []

        if not root_path.exists():
            return {"playlist_name": target_dir["name"], "music_list": []}

        # 遍历目录
        idx = 0
        # 使用 rglob 递归查找，iterdir 配合 os.walk 也可以
        for file_path in root_path.rglob("*"):
            if file_path.is_file() and file_path.suffix.lower() in SUPPORTED_AUDIO_EXT:
                idx += 1
                
                # 提取元数据
                metadata = self._extract_music_metadata(file_path)

                music_list.append(MusicItem(
                    id=f"local_{dir_id}_{idx}",
                    title=metadata["title"],
                    artist=metadata["artist"],
                    album=metadata["album"],
                    year=metadata["year"],
                    duration=metadata["duration"],
                    duration_str=metadata["duration_str"],
                    path=str(file_path.absolute()),
                    file_size=file_path.stat().st_size,
                    bitrate=metadata["bitrate"],
                    has_cover=metadata["has_cover"]
                ))

        return {
            "playlist_id": dir_id,
            "playlist_name": target_dir["name"],
            "source_path": target_dir["path"],
            "total_count": len(music_list),
            "music_list": [asdict(m) for m in music_list]
        }


# 全局单例
local_music_manager = LocalMusicManager()