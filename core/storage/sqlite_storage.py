"""SQLite存储实现：基于SQLAlchemy的ORM操作"""
import sqlite3
from datetime import datetime
from typing import List, Dict, Optional, Any
from pathlib import Path
from sqlalchemy import (
    create_engine, Column, String, Integer, Text, DateTime, 
    ForeignKey, Table, MetaData, select, update, delete
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

from .base import BaseStorage
from .models import (
    MusicModel, PlaylistModel, MusicSheetModel,
    PlayHistoryModel, SearchHistoryModel, model_to_dict, dict_to_model
)
from core.constants import logger

# ========== SQLAlchemy配置 ==========
Base = declarative_base()
metadata = MetaData()

# ========== 数据库表模型 ==========
class DB_Music(Base):
    """歌曲表"""
    __tablename__ = "music"
    id = Column(String(32), primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    artist = Column(String(255), nullable=False, index=True)
    album = Column(String(255), default="")
    duration = Column(Integer, default=0)
    url = Column(Text, default="")
    lyric = Column(Text, default="")
    cover = Column(Text, default="")
    source = Column(String(32), default="")
    create_time = Column(DateTime, default=datetime.now)
    update_time = Column(DateTime, default=datetime.now, onupdate=datetime.now)

class DB_Playlist(Base):
    """播放列表表"""
    __tablename__ = "playlist"
    id = Column(String(32), primary_key=True, index=True)
    name = Column(String(255), default="默认播放列表")
    create_time = Column(DateTime, default=datetime.now)
    update_time = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    # 关联歌曲（多对多）
    musics = relationship("DB_Music", secondary="playlist_music")

# 播放列表-歌曲关联表（多对多）
playlist_music = Table(
    "playlist_music", Base.metadata,
    Column("playlist_id", String(32), ForeignKey("playlist.id"), primary_key=True),
    Column("music_id", String(32), ForeignKey("music.id"), primary_key=True)
)

class DB_MusicSheet(Base):
    """歌单表"""
    __tablename__ = "music_sheet"
    id = Column(String(32), primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, default="")
    cover = Column(Text, default="")
    create_time = Column(DateTime, default=datetime.now)
    update_time = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    # 关联歌曲（多对多）
    musics = relationship("DB_Music", secondary="sheet_music")

# 歌单-歌曲关联表（多对多）
sheet_music = Table(
    "sheet_music", Base.metadata,
    Column("sheet_id", String(32), ForeignKey("music_sheet.id"), primary_key=True),
    Column("music_id", String(32), ForeignKey("music.id"), primary_key=True)
)

class DB_PlayHistory(Base):
    """播放历史表"""
    __tablename__ = "play_history"
    id = Column(String(32), primary_key=True, index=True)
    music_id = Column(String(32), ForeignKey("music.id"), nullable=False, index=True)
    play_time = Column(DateTime, default=datetime.now, index=True)
    play_duration = Column(Integer, default=0)

class DB_SearchHistory(Base):
    """搜索历史表"""
    __tablename__ = "search_history"
    id = Column(String(32), primary_key=True, index=True)
    keyword = Column(String(255), nullable=False, index=True)
    search_time = Column(DateTime, default=datetime.now, index=True)

# ========== SQLite存储实现 ==========
class SQLiteStorage(BaseStorage):
    """SQLite存储实现"""
    def _init_storage(self):
        """初始化SQLite数据库"""
        # 数据库文件路径
        self.db_path = self.storage_dir / "music_free.db"
        # 创建引擎（支持多线程）
        self.engine = create_engine(
            f"sqlite:///{self.db_path}",
            connect_args={"check_same_thread": False},
            echo=False  # 生产环境关闭echo
        )
        # 创建所有表
        Base.metadata.create_all(bind=self.engine)
        # 创建会话
        self.Session = sessionmaker(bind=self.engine)
        self.logger.info(f"SQLite数据库初始化完成：{self.db_path}")

        # 初始化默认播放列表
        with self.Session() as session:
            default_playlist = session.query(DB_Playlist).filter_by(id="default").first()
            if not default_playlist:
                default_playlist = DB_Playlist(id="default", name="默认播放列表")
                session.add(default_playlist)
                session.commit()
                self.logger.info("创建默认播放列表")

    # ========== 歌曲相关实现 ==========
    def save_music(self, music: Dict[str, Any]) -> str:
        """保存歌曲"""
        with self.Session() as session:
            # 验证数据
            music_model = dict_to_model(music, MusicModel)
            # 检查是否已存在
            existing = session.query(DB_Music).filter_by(id=music_model.id).first()
            if existing:
                # 更新现有歌曲
                for key, value in model_to_dict(music_model).items():
                    setattr(existing, key, value)
                session.commit()
                self.logger.info(f"更新歌曲：{music_model.id} - {music_model.name}")
                return music_model.id
            else:
                # 新增歌曲
                db_music = DB_Music(**model_to_dict(music_model))
                session.add(db_music)
                session.commit()
                self.logger.info(f"保存歌曲：{music_model.id} - {music_model.name}")
                return music_model.id

    def get_music_by_id(self, music_id: str) -> Optional[Dict[str, Any]]:
        """根据ID获取歌曲"""
        with self.Session() as session:
            music = session.query(DB_Music).filter_by(id=music_id).first()
            if music:
                return {
                    "id": music.id,
                    "name": music.name,
                    "artist": music.artist,
                    "album": music.album,
                    "duration": music.duration,
                    "url": music.url,
                    "lyric": music.lyric,
                    "cover": music.cover,
                    "source": music.source,
                    "create_time": music.create_time.strftime("%Y-%m-%d %H:%M:%S"),
                    "update_time": music.update_time.strftime("%Y-%m-%d %H:%M:%S")
                }
            return None

    def delete_music(self, music_id: str) -> bool:
        """删除歌曲"""
        try:
            with self.Session() as session:
                # 删除关联数据
                session.execute(delete(playlist_music).where(playlist_music.c.music_id == music_id))
                session.execute(delete(sheet_music).where(sheet_music.c.music_id == music_id))
                session.execute(delete(DB_PlayHistory).where(DB_PlayHistory.music_id == music_id))
                # 删除歌曲
                result = session.execute(delete(DB_Music).where(DB_Music.id == music_id))
                session.commit()
                self.logger.info(f"删除歌曲：{music_id}（影响行数：{result.rowcount}）")
                return result.rowcount > 0
        except Exception as e:
            self.logger.error(f"删除歌曲失败：{e}", exc_info=True)
            return False

    def search_music(self, keyword: str) -> List[Dict[str, Any]]:
        """搜索歌曲"""
        with self.Session() as session:
            query = session.query(DB_Music).filter(
                DB_Music.name.like(f"%{keyword}%") | DB_Music.artist.like(f"%{keyword}%")
            ).limit(50).all()
            
            result = []
            for music in query:
                result.append({
                    "id": music.id,
                    "name": music.name,
                    "artist": music.artist,
                    "album": music.album,
                    "duration": music.duration,
                    "cover": music.cover
                })
            return result

    # ========== 播放列表相关实现 ==========
    def save_playlist(self, playlist: Dict[str, Any]) -> str:
        """保存播放列表"""
        with self.Session() as session:
            playlist_model = dict_to_model(playlist, PlaylistModel)
            existing = session.query(DB_Playlist).filter_by(id=playlist_model.id).first()
            
            if existing:
                # 更新
                existing.name = playlist_model.name
                session.commit()
                self.logger.info(f"更新播放列表：{playlist_model.id}")
            else:
                # 新增
                db_playlist = DB_Playlist(
                    id=playlist_model.id,
                    name=playlist_model.name
                )
                session.add(db_playlist)
                session.commit()
                self.logger.info(f"创建播放列表：{playlist_model.id} - {playlist_model.name}")
            
            return playlist_model.id

    def get_playlist(self, playlist_id: str = "default") -> Optional[Dict[str, Any]]:
        """获取播放列表"""
        with self.Session() as session:
            playlist = session.query(DB_Playlist).filter_by(id=playlist_id).first()
            if not playlist:
                return None
            
            # 获取关联的歌曲
            music_list = []
            for music in playlist.musics:
                music_list.append({
                    "id": music.id,
                    "name": music.name,
                    "artist": music.artist,
                    "album": music.album,
                    "duration": music.duration
                })
            
            return {
                "id": playlist.id,
                "name": playlist.name,
                "music_ids": [m.id for m in playlist.musics],
                "musics": music_list,
                "create_time": playlist.create_time.strftime("%Y-%m-%d %H:%M:%S"),
                "update_time": playlist.update_time.strftime("%Y-%m-%d %H:%M:%S")
            }

    def add_music_to_playlist(self, playlist_id: str, music_id: str) -> bool:
        """添加歌曲到播放列表"""
        try:
            with self.Session() as session:
                playlist = session.query(DB_Playlist).filter_by(id=playlist_id).first()
                music = session.query(DB_Music).filter_by(id=music_id).first()
                
                if not playlist or not music:
                    self.logger.warning(f"播放列表或歌曲不存在：{playlist_id}/{music_id}")
                    return False
                
                # 检查是否已存在
                if music in playlist.musics:
                    return True
                
                playlist.musics.append(music)
                session.commit()
                self.logger.info(f"添加歌曲{music_id}到播放列表{playlist_id}")
                return True
        except Exception as e:
            self.logger.error(f"添加歌曲到播放列表失败：{e}", exc_info=True)
            return False

    def remove_music_from_playlist(self, playlist_id: str, music_id: str) -> bool:
        """从播放列表移除歌曲"""
        try:
            with self.Session() as session:
                playlist = session.query(DB_Playlist).filter_by(id=playlist_id).first()
                music = session.query(DB_Music).filter_by(id=music_id).first()
                
                if not playlist or not music:
                    return False
                
                if music not in playlist.musics:
                    return True
                
                playlist.musics.remove(music)
                session.commit()
                self.logger.info(f"从播放列表{playlist_id}移除歌曲{music_id}")
                return True
        except Exception as e:
            self.logger.error(f"移除歌曲失败：{e}", exc_info=True)
            return False

    # ========== 歌单相关实现 ==========
    def save_music_sheet(self, sheet: Dict[str, Any]) -> str:
        """保存歌单"""
        with self.Session() as session:
            sheet_model = dict_to_model(sheet, MusicSheetModel)
            existing = session.query(DB_MusicSheet).filter_by(id=sheet_model.id).first()
            
            if existing:
                # 更新
                existing.name = sheet_model.name
                existing.description = sheet_model.description
                existing.cover = sheet_model.cover
                session.commit()
                self.logger.info(f"更新歌单：{sheet_model.id}")
            else:
                # 新增
                db_sheet = DB_MusicSheet(
                    id=sheet_model.id,
                    name=sheet_model.name,
                    description=sheet_model.description,
                    cover=sheet_model.cover
                )
                session.add(db_sheet)
                session.commit()
                self.logger.info(f"创建歌单：{sheet_model.id} - {sheet_model.name}")
            
            # 同步歌曲
            if "music_ids" in sheet:
                self._sync_sheet_musics(session, sheet_model.id, sheet["music_ids"])
            
            return sheet_model.id

    def _sync_sheet_musics(self, session, sheet_id: str, music_ids: List[str]):
        """同步歌单歌曲"""
        sheet = session.query(DB_MusicSheet).filter_by(id=sheet_id).first()
        if not sheet:
            return
        
        # 清空现有歌曲
        sheet.musics.clear()
        # 添加新歌曲
        for music_id in music_ids:
            music = session.query(DB_Music).filter_by(id=music_id).first()
            if music:
                sheet.musics.append(music)
        
        session.commit()

    def get_all_music_sheets(self) -> List[Dict[str, Any]]:
        """获取所有歌单"""
        with self.Session() as session:
            sheets = session.query(DB_MusicSheet).all()
            result = []
            
            for sheet in sheets:
                music_ids = [m.id for m in sheet.musics]
                result.append({
                    "id": sheet.id,
                    "name": sheet.name,
                    "description": sheet.description,
                    "cover": sheet.cover,
                    "music_ids": music_ids,
                    "music_count": len(music_ids),
                    "create_time": sheet.create_time.strftime("%Y-%m-%d %H:%M:%S")
                })
            
            return result

    def get_music_sheet_by_id(self, sheet_id: str) -> Optional[Dict[str, Any]]:
        """根据ID获取歌单"""
        with self.Session() as session:
            sheet = session.query(DB_MusicSheet).filter_by(id=sheet_id).first()
            if not sheet:
                return None
            
            music_list = []
            for music in sheet.musics:
                music_list.append({
                    "id": music.id,
                    "name": music.name,
                    "artist": music.artist,
                    "album": music.album,
                    "duration": music.duration
                })
            
            return {
                "id": sheet.id,
                "name": sheet.name,
                "description": sheet.description,
                "cover": sheet.cover,
                "music_ids": [m.id for m in sheet.musics],
                "musics": music_list,
                "create_time": sheet.create_time.strftime("%Y-%m-%d %H:%M:%S"),
                "update_time": sheet.update_time.strftime("%Y-%m-%d %H:%M:%S")
            }

    # ========== 历史记录相关实现 ==========
    def save_play_history(self, music_id: str, play_time: int = None) -> bool:
        """保存播放历史"""
        try:
            with self.Session() as session:
                # 检查歌曲是否存在
                if not session.query(DB_Music).filter_by(id=music_id).first():
                    self.logger.warning(f"歌曲不存在，无法保存播放历史：{music_id}")
                    return False
                
                # 创建播放历史
                history_model = PlayHistoryModel(
                    music_id=music_id,
                    play_duration=play_time or 0
                )
                db_history = DB_PlayHistory(**model_to_dict(history_model))
                session.add(db_history)
                session.commit()
                self.logger.info(f"保存播放历史：{music_id}")
                return True
        except Exception as e:
            self.logger.error(f"保存播放历史失败：{e}", exc_info=True)
            return False

    def get_play_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """获取播放历史"""
        with self.Session() as session:
            histories = session.query(DB_PlayHistory).order_by(
                DB_PlayHistory.play_time.desc()
            ).limit(limit).all()
            
            result = []
            for history in histories:
                music = self.get_music_by_id(history.music_id)
                if music:
                    result.append({
                        "id": history.id,
                        "music": music,
                        "play_time": history.play_time.strftime("%Y-%m-%d %H:%M:%S"),
                        "play_duration": history.play_duration
                    })
            
            return result

    def save_search_history(self, keyword: str) -> bool:
        """保存搜索历史"""
        try:
            with self.Session() as session:
                # 去重：如果1分钟内有相同关键词，不重复保存
                one_minute_ago = datetime.now() - datetime.timedelta(minutes=1)
                existing = session.query(DB_SearchHistory).filter(
                    DB_SearchHistory.keyword == keyword,
                    DB_SearchHistory.search_time >= one_minute_ago
                ).first()
                
                if existing:
                    return True
                
                # 保存新的搜索历史
                history_model = SearchHistoryModel(keyword=keyword)
                db_history = DB_SearchHistory(**model_to_dict(history_model))
                session.add(db_history)
                session.commit()
                self.logger.info(f"保存搜索历史：{keyword}")
                return True
        except Exception as e:
            self.logger.error(f"保存搜索历史失败：{e}", exc_info=True)
            return False

    def get_search_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """获取搜索历史"""
        with self.Session() as session:
            histories = session.query(DB_SearchHistory).order_by(
                DB_SearchHistory.search_time.desc()
            ).limit(limit).all()
            
            return [
                {
                    "id": h.id,
                    "keyword": h.keyword,
                    "search_time": h.search_time.strftime("%Y-%m-%d %H:%M:%S")
                }
                for h in histories
            ]