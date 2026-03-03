"""文件存储实现：基于JSON文件的轻量级存储"""
import json
import os
from datetime import datetime
from typing import List, Dict, Optional, Any
from pathlib import Path
from .base import BaseStorage
from .models import (
    MusicModel, PlaylistModel, MusicSheetModel,
    PlayHistoryModel, SearchHistoryModel, model_to_dict, dict_to_model
)
from core.constants import logger

class FileStorage(BaseStorage):
    """文件存储实现（JSON格式）"""
    def _init_storage(self):
        """初始化文件存储目录"""
        # 子目录结构
        self.music_dir = self.storage_dir / "music"
        self.playlist_dir = self.storage_dir / "playlist"
        self.sheet_dir = self.storage_dir / "sheet"
        self.history_dir = self.storage_dir / "history"
        
        # 创建目录
        for dir_path in [self.music_dir, self.playlist_dir, self.sheet_dir, self.history_dir]:
            dir_path.mkdir(exist_ok=True, parents=True)
        
        # 初始化默认播放列表
        default_playlist_path = self.playlist_dir / "default.json"
        if not default_playlist_path.exists():
            default_playlist = PlaylistModel(id="default", name="默认播放列表")
            self._save_json(default_playlist_path, model_to_dict(default_playlist))
            logger.info("创建默认播放列表文件")
        
        logger.info(f"文件存储初始化完成：{self.storage_dir}")

    # ========== 通用JSON工具 ==========
    def _save_json(self, file_path: Path, data: Dict[str, Any]):
        """保存JSON文件"""
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _load_json(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """加载JSON文件"""
        if not file_path.exists():
            return None
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            logger.error(f"JSON文件解析失败：{file_path}")
            return None

    # ========== 歌曲相关实现 ==========
    def save_music(self, music: Dict[str, Any]) -> str:
        """保存歌曲到JSON文件"""
        music_model = dict_to_model(music, MusicModel)
        music_path = self.music_dir / f"{music_model.id}.json"
        
        # 更新时间
        music_model.update_time = datetime.now()
        self._save_json(music_path, model_to_dict(music_model))
        logger.info(f"保存歌曲文件：{music_path}")
        return music_model.id

    def get_music_by_id(self, music_id: str) -> Optional[Dict[str, Any]]:
        """根据ID获取歌曲"""
        music_path = self.music_dir / f"{music_id}.json"
        data = self._load_json(music_path)
        return data

    def delete_music(self, music_id: str) -> bool:
        """删除歌曲文件"""
        music_path = self.music_dir / f"{music_id}.json"
        if not music_path.exists():
            return False
        
        try:
            os.remove(music_path)
            logger.info(f"删除歌曲文件：{music_path}")
            # 同时从所有播放列表/歌单中移除
            self._remove_music_from_all_collections(music_id)
            return True
        except Exception as e:
            logger.error(f"删除歌曲文件失败：{e}", exc_info=True)
            return False

    def _remove_music_from_all_collections(self, music_id: str):
        """从所有播放列表/歌单中移除歌曲"""
        # 处理播放列表
        for playlist_file in self.playlist_dir.glob("*.json"):
            playlist = self._load_json(playlist_file)
            if playlist and "music_ids" in playlist and music_id in playlist["music_ids"]:
                playlist["music_ids"].remove(music_id)
                playlist["update_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                self._save_json(playlist_file, playlist)
        
        # 处理歌单
        for sheet_file in self.sheet_dir.glob("*.json"):
            sheet = self._load_json(sheet_file)
            if sheet and "music_ids" in sheet and music_id in sheet["music_ids"]:
                sheet["music_ids"].remove(music_id)
                sheet["update_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                self._save_json(sheet_file, sheet)

    def search_music(self, keyword: str) -> List[Dict[str, Any]]:
        """搜索歌曲"""
        result = []
        keyword_lower = keyword.lower()
        
        for music_file in self.music_dir.glob("*.json"):
            music = self._load_json(music_file)
            if not music:
                continue
            
            # 匹配名称或歌手
            if (keyword_lower in music.get("name", "").lower() or 
                keyword_lower in music.get("artist", "").lower()):
                result.append(music)
        
        return result[:50]  # 限制返回数量

    # ========== 播放列表相关实现 ==========
    def save_playlist(self, playlist: Dict[str, Any]) -> str:
        """保存播放列表"""
        playlist_model = dict_to_model(playlist, PlaylistModel)
        playlist_path = self.playlist_dir / f"{playlist_model.id}.json"
        
        playlist_model.update_time = datetime.now()
        self._save_json(playlist_path, model_to_dict(playlist_model))
        logger.info(f"保存播放列表：{playlist_path}")
        return playlist_model.id

    def get_playlist(self, playlist_id: str = "default") -> Optional[Dict[str, Any]]:
        """获取播放列表"""
        playlist_path = self.playlist_dir / f"{playlist_id}.json"
        playlist = self._load_json(playlist_path)
        
        if not playlist:
            return None
        
        # 加载关联的歌曲
        playlist["musics"] = []
        for music_id in playlist.get("music_ids", []):
            music = self.get_music_by_id(music_id)
            if music:
                playlist["musics"].append(music)
        
        return playlist

    def add_music_to_playlist(self, playlist_id: str, music_id: str) -> bool:
        """添加歌曲到播放列表"""
        playlist = self.get_playlist(playlist_id)
        if not playlist:
            logger.warning(f"播放列表不存在：{playlist_id}")
            return False
        
        # 检查歌曲是否存在
        if not self.get_music_by_id(music_id):
            logger.warning(f"歌曲不存在：{music_id}")
            return False
        
        # 避免重复添加
        if music_id not in playlist.get("music_ids", []):
            playlist["music_ids"].append(music_id)
            playlist["update_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.save_playlist(playlist)
            logger.info(f"添加歌曲{music_id}到播放列表{playlist_id}")
        
        return True

    def remove_music_from_playlist(self, playlist_id: str, music_id: str) -> bool:
        """从播放列表移除歌曲"""
        playlist = self.get_playlist(playlist_id)
        if not playlist or music_id not in playlist.get("music_ids", []):
            return False
        
        playlist["music_ids"].remove(music_id)
        playlist["update_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.save_playlist(playlist)
        logger.info(f"从播放列表{playlist_id}移除歌曲{music_id}")
        return True

    # ========== 歌单相关实现 ==========
    def save_music_sheet(self, sheet: Dict[str, Any]) -> str:
        """保存歌单"""
        sheet_model = dict_to_model(sheet, MusicSheetModel)
        sheet_path = self.sheet_dir / f"{sheet_model.id}.json"
        
        sheet_model.update_time = datetime.now()
        self._save_json(sheet_path, model_to_dict(sheet_model))
        logger.info(f"保存歌单：{sheet_path}")
        return sheet_model.id

    def get_all_music_sheets(self) -> List[Dict[str, Any]]:
        """获取所有歌单"""
        sheets = []
        for sheet_file in self.sheet_dir.glob("*.json"):
            sheet = self._load_json(sheet_file)
            if sheet:
                sheet["music_count"] = len(sheet.get("music_ids", []))
                sheets.append(sheet)
        
        # 按创建时间排序
        sheets.sort(key=lambda x: x.get("create_time", ""), reverse=True)
        return sheets

    def get_music_sheet_by_id(self, sheet_id: str) -> Optional[Dict[str, Any]]:
        """根据ID获取歌单"""
        sheet_path = self.sheet_dir / f"{sheet_id}.json"
        sheet = self._load_json(sheet_path)
        
        if not sheet:
            return None
        
        # 加载关联的歌曲
        sheet["musics"] = []
        for music_id in sheet.get("music_ids", []):
            music = self.get_music_by_id(music_id)
            if music:
                sheet["musics"].append(music)
        
        return sheet

    # ========== 历史记录相关实现 ==========
    def save_play_history(self, music_id: str, play_time: int = None) -> bool:
        """保存播放历史"""
        # 检查歌曲是否存在
        if not self.get_music_by_id(music_id):
            logger.warning(f"歌曲不存在：{music_id}")
            return False
        
        # 加载历史文件
        history_path = self.history_dir / "play_history.json"
        histories = self._load_json(history_path) or []
        
        # 创建历史记录
        history_model = PlayHistoryModel(
            music_id=music_id,
            play_duration=play_time or 0
        )
        history_dict = model_to_dict(history_model)
        history_dict["play_time"] = history_dict["play_time"].strftime("%Y-%m-%d %H:%M:%S")
        
        # 添加到历史列表
        histories.insert(0, history_dict)  # 插入到开头
        histories = histories[:100]  # 限制最多100条
        
        # 保存
        self._save_json(history_path, histories)
        logger.info(f"保存播放历史：{music_id}")
        return True

    def get_play_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """获取播放历史"""
        history_path = self.history_dir / "play_history.json"
        histories = self._load_json(history_path) or []
        
        # 加载关联的歌曲信息
        result = []
        for history in histories[:limit]:
            music = self.get_music_by_id(history["music_id"])
            if music:
                history["music"] = music
                result.append(history)
        
        return result

    def save_search_history(self, keyword: str) -> bool:
        """保存搜索历史"""
        # 加载历史文件
        history_path = self.history_dir / "search_history.json"
        histories = self._load_json(history_path) or []
        
        # 去重
        keywords = [h["keyword"] for h in histories]
        if keyword in keywords:
            # 移除旧的，添加新的到开头
            histories = [h for h in histories if h["keyword"] != keyword]
        
        # 创建历史记录
        history_model = SearchHistoryModel(keyword=keyword)
        history_dict = model_to_dict(history_model)
        history_dict["search_time"] = history_dict["search_time"].strftime("%Y-%m-%d %H:%M:%S")
        
        # 添加到开头
        histories.insert(0, history_dict)
        histories = histories[:50]  # 限制最多50条
        
        # 保存
        self._save_json(history_path, histories)
        logger.info(f"保存搜索历史：{keyword}")
        return True

    def get_search_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """获取搜索历史"""
        history_path = self.history_dir / "search_history.json"
        histories = self._load_json(history_path) or []
        return histories[:limit]