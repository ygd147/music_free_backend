"""MySQL存储实现：基于SQLAlchemy的ORM操作（修复 Not an executable object 错误）"""
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from sqlalchemy import (
    create_engine, Column, String, Integer, Text, DateTime, 
    ForeignKey, Table, MetaData, select, update, delete, Index, text
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, scoped_session
from sqlalchemy.exc import OperationalError, ProgrammingError

# 假设 BaseStorage 和模型转换函数已正确定义
from .base import BaseStorage
from .models import (
    MusicModel, PlaylistModel, MusicSheetModel,
    PlayHistoryModel, SearchHistoryModel, model_to_dict, dict_to_model
)
from core.constants import logger, mysql_config

# ========== SQLAlchemy配置 ==========
Base = declarative_base()
metadata = MetaData()

# ========== 数据库表模型（适配MySQL） ==========
class DB_Music(Base):
    """歌曲表"""
    __tablename__ = "music"
    id = Column(String(32), primary_key=True, comment="歌曲ID")
    name = Column(String(255), nullable=False, comment="歌曲名称")
    artist = Column(String(255), nullable=False, comment="歌手")
    album = Column(String(255), default="", comment="专辑")
    duration = Column(Integer, default=0, comment="时长（秒）")
    url = Column(Text, default="", comment="播放链接")
    lyric = Column(Text, default="", comment="歌词")
    cover = Column(Text, default="", comment="封面")
    source = Column(String(32), default="", comment="来源平台")
    create_time = Column(DateTime, default=datetime.now, comment="创建时间")
    update_time = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")
    
    # 新增MySQL索引
    __table_args__ = (
        Index('idx_music_name', 'name'),
        Index('idx_music_artist', 'artist'),
        {'mysql_charset': 'utf8mb4', 'mysql_collate': 'utf8mb4_unicode_ci'}
    )

class DB_Playlist(Base):
    """播放列表表"""
    __tablename__ = "playlist"
    id = Column(String(32), primary_key=True, comment="播放列表ID")
    name = Column(String(255), default="默认播放列表", comment="列表名称")
    create_time = Column(DateTime, default=datetime.now, comment="创建时间")
    update_time = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")
    # 关联歌曲（多对多）
    musics = relationship("DB_Music", secondary="playlist_music")
    
    __table_args__ = (
        {'mysql_charset': 'utf8mb4', 'mysql_collate': 'utf8mb4_unicode_ci'}
    )

# 播放列表-歌曲关联表（多对多）
playlist_music = Table(
    "playlist_music", 
    Base.metadata,
    Column("playlist_id", String(32), ForeignKey("playlist.id"), primary_key=True, comment="播放列表ID"),
    Column("music_id", String(32), ForeignKey("music.id"), primary_key=True, comment="歌曲ID"),
    Column("sort", Integer, default=0, comment="排序号"),
    mysql_charset='utf8mb4',
    mysql_collate='utf8mb4_unicode_ci'
)

class DB_MusicSheet(Base):
    """歌单表"""
    __tablename__ = "music_sheet"
    id = Column(String(32), primary_key=True, comment="歌单ID")
    name = Column(String(255), nullable=False, comment="歌单名称")
    description = Column(Text, default="", comment="歌单描述")
    cover = Column(Text, default="", comment="歌单封面")
    create_time = Column(DateTime, default=datetime.now, comment="创建时间")
    update_time = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")
    # 关联歌曲（多对多）
    musics = relationship("DB_Music", secondary="sheet_music")
    
    __table_args__ = (
        Index('idx_sheet_name', 'name'),
        {'mysql_charset': 'utf8mb4', 'mysql_collate': 'utf8mb4_unicode_ci'}
    )

# 歌单-歌曲关联表（多对多）
sheet_music = Table(
    "sheet_music", 
    Base.metadata,
    Column("sheet_id", String(32), ForeignKey("music_sheet.id"), primary_key=True, comment="歌单ID"),
    Column("music_id", String(32), ForeignKey("music.id"), primary_key=True, comment="歌曲ID"),
    Column("sort", Integer, default=0, comment="排序号"),
    mysql_charset='utf8mb4',
    mysql_collate='utf8mb4_unicode_ci'
)

class DB_PlayHistory(Base):
    """播放历史表"""
    __tablename__ = "play_history"
    id = Column(String(32), primary_key=True, comment="历史ID")
    music_id = Column(String(32), ForeignKey("music.id"), nullable=False, comment="歌曲ID")
    play_time = Column(DateTime, default=datetime.now, comment="播放时间")
    play_duration = Column(Integer, default=0, comment="播放时长（秒）")
    
    __table_args__ = (
        Index('idx_play_history_time', 'play_time'),
        Index('idx_play_history_music', 'music_id'),
        {'mysql_charset': 'utf8mb4', 'mysql_collate': 'utf8mb4_unicode_ci'}
    )

class DB_SearchHistory(Base):
    """搜索历史表"""
    __tablename__ = "search_history"
    id = Column(String(32), primary_key=True, comment="搜索ID")
    keyword = Column(String(255), nullable=False, comment="搜索关键词")
    search_time = Column(DateTime, default=datetime.now, comment="搜索时间")
    
    __table_args__ = (
        Index('idx_search_history_keyword', 'keyword'),
        Index('idx_search_history_time', 'search_time'),
        {'mysql_charset': 'utf8mb4', 'mysql_collate': 'utf8mb4_unicode_ci'}
    )

# ========== MySQL存储实现（修复版） ==========
class MySQLStorage(BaseStorage):
    """MySQL存储实现（修复 Not an executable object 错误）"""
    def __init__(self):
        # 初始化日志
        self.logger = logger
        # 初始化存储
        self._init_storage()

    def _init_storage(self):
        """初始化MySQL数据库（修复连接和建库逻辑）"""
        try:
            # 1. 先创建数据库（如果不存在）- 修复执行方式
            self._create_database_if_not_exists()
            
            # 2. 创建引擎（支持连接池，修复参数）
            conn_url = f"mysql+pymysql://{mysql_config.user}:{mysql_config.password}@{mysql_config.host}:{mysql_config.port}/{mysql_config.database}?charset={mysql_config.charset}"
            self.engine = create_engine(
                conn_url,
                pool_size=10,          # 连接池大小
                max_overflow=20,       # 最大溢出连接数
                pool_recycle=3600,     # 连接回收时间（秒）
                echo=False,            # 生产环境关闭SQL日志
                pool_pre_ping=True,    # 连接前检查是否有效
                future=True            # 启用SQLAlchemy 2.0兼容模式（关键修复）
            )
            
            # 3. 创建所有表（确保元数据绑定）
            Base.metadata.create_all(bind=self.engine)
            
            # 4. 创建线程安全的会话（修复session配置）
            self.SessionFactory = sessionmaker(
                bind=self.engine,
                autocommit=False,
                autoflush=False,
                expire_on_commit=False,
                future=True
            )
            self.Session = scoped_session(self.SessionFactory)
            
            self.logger.info(f"MySQL数据库初始化完成：{mysql_config.host}:{mysql_config.port}/{mysql_config.database}")

            # 5. 初始化默认播放列表
            self._init_default_playlist()
            
        except Exception as e:
            self.logger.error(f"MySQL初始化失败：{e}", exc_info=True)
            raise RuntimeError(f"MySQL存储初始化失败：{str(e)}")

    def _create_database_if_not_exists(self):
        """创建数据库（修复 Not an executable object 错误）"""
        try:
            # 先连接MySQL服务器（不指定数据库）
            temp_conn_url = f"mysql+pymysql://{mysql_config.user}:{mysql_config.password}@{mysql_config.host}:{mysql_config.port}/?charset={mysql_config.charset}"
            temp_engine = create_engine(temp_conn_url, pool_pre_ping=True, future=True)
            
            with temp_engine.connect() as conn:
                # 关闭自动提交
                conn.execution_options(isolation_level="AUTOCOMMIT")
                # 修复：使用text()包装SQL语句，避免执行对象错误
                create_db_sql = text(f"""
                    CREATE DATABASE IF NOT EXISTS {mysql_config.database} 
                    CHARACTER SET {mysql_config.charset} 
                    COLLATE {mysql_config.charset}_unicode_ci
                """)
                conn.execute(create_db_sql)
            
            temp_engine.dispose()
            self.logger.info(f"确保数据库存在：{mysql_config.database}")
        except Exception as e:
            self.logger.error(f"创建数据库失败：{e}", exc_info=True)
            raise

    def _init_default_playlist(self):
        """初始化默认播放列表"""
        session = self.Session()
        try:
            default_playlist = session.query(DB_Playlist).filter_by(id="default").first()
            if not default_playlist:
                default_playlist = DB_Playlist(id="default", name="默认播放列表")
                session.add(default_playlist)
                session.commit()
                self.logger.info("创建默认播放列表")
        except Exception as e:
            session.rollback()
            self.logger.error(f"初始化默认播放列表失败：{e}", exc_info=True)
        finally:
            session.close()

    # ========== 核心工具方法（新增） ==========
    def _get_session(self):
        """获取session并确保正确的上下文"""
        return self.Session()

    # ========== 歌曲相关实现（修复删除逻辑） ==========
    def save_music(self, music: Dict[str, Any]) -> str:
        """保存歌曲"""
        session = self._get_session()
        now = datetime.now()
        if "create_time" not in music or not music["create_time"]:
            music["create_time"] = now
        if "update_time" not in music or not music["update_time"]:
            music["update_time"] = now
        try:
            # 验证数据
            music_model = dict_to_model(music, MusicModel)
            # 检查是否已存在
            existing = session.query(DB_Music).filter_by(id=music_model.id).first()
            
            if existing:
                # 更新现有歌曲
                for key, value in model_to_dict(music_model).items():
                    if key not in ["id", "create_time"]:  # 不更新ID和创建时间
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
        except Exception as e:
            session.rollback()
            self.logger.error(f"保存歌曲失败：{e}", exc_info=True)
            raise
        finally:
            session.close()

    def get_music_by_id(self, music_id: str) -> Optional[Dict[str, Any]]:
        """根据ID获取歌曲"""
        session = self._get_session()
        try:
            music = session.query(DB_Music).filter_by(id=music_id).first()
            if not music:
                return None
                
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
        finally:
            session.close()

    def delete_music(self, music_id: str) -> bool:
        """删除歌曲（修复 Not an executable object 错误）"""
        session = self._get_session()
        try:
            # 开始事务
            session.begin()
            
            # 修复：使用表对象的delete()方法，而非全局delete函数
            # 1. 删除播放列表关联
            del_playlist_music = playlist_music.delete().where(playlist_music.c.music_id == music_id)
            session.execute(del_playlist_music)
            
            # 2. 删除歌单关联
            del_sheet_music = sheet_music.delete().where(sheet_music.c.music_id == music_id)
            session.execute(del_sheet_music)
            
            # 3. 删除播放历史
            del_play_history = DB_PlayHistory.__table__.delete().where(DB_PlayHistory.music_id == music_id)
            session.execute(del_play_history)
            
            # 4. 删除歌曲主表
            del_music = DB_Music.__table__.delete().where(DB_Music.id == music_id)
            result = session.execute(del_music)
            
            session.commit()
            affected_rows = result.rowcount
            self.logger.info(f"删除歌曲：{music_id}（影响行数：{affected_rows}）")
            return affected_rows > 0
            
        except Exception as e:
            session.rollback()
            self.logger.error(f"删除歌曲失败：{e}", exc_info=True)
            return False
        finally:
            session.close()

    def search_music(self, keyword: str) -> List[Dict[str, Any]]:
        """搜索歌曲（优化MySQL模糊查询）"""
        session = self._get_session()
        try:
            # 使用CONCAT优化模糊查询
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
        finally:
            session.close()

    # ========== 播放列表相关实现（修复删除逻辑） ==========
    def save_playlist(self, playlist: Dict[str, Any]) -> str:
        """保存播放列表"""
        session = self._get_session()
        try:
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
        except Exception as e:
            session.rollback()
            self.logger.error(f"保存播放列表失败：{e}", exc_info=True)
            raise
        finally:
            session.close()

    def get_playlist(self, playlist_id: str = "default") -> Optional[Dict[str, Any]]:
        """获取播放列表"""
        session = self._get_session()
        try:
            playlist = session.query(DB_Playlist).filter_by(id=playlist_id).first()
            if not playlist:
                return None
            
            # 获取关联的歌曲（带排序）
            music_list = []
            # 关联查询播放列表-歌曲表，按sort排序
            playlist_music_query = session.query(
                DB_Music, playlist_music.c.sort
            ).join(
                playlist_music, DB_Music.id == playlist_music.c.music_id
            ).filter(
                playlist_music.c.playlist_id == playlist_id
            ).order_by(
                playlist_music.c.sort
            ).all()
            
            for music, sort in playlist_music_query:
                music_list.append({
                    "id": music.id,
                    "name": music.name,
                    "artist": music.artist,
                    "album": music.album,
                    "duration": music.duration,
                    "sort": sort
                })
            
            return {
                "id": playlist.id,
                "name": playlist.name,
                "music_ids": [m["id"] for m in music_list],
                "musics": music_list,
                "create_time": playlist.create_time.strftime("%Y-%m-%d %H:%M:%S"),
                "update_time": playlist.update_time.strftime("%Y-%m-%d %H:%M:%S")
            }
        finally:
            session.close()

    def add_music_to_playlist(self, playlist_id: str, music_id: str) -> bool:
        """添加歌曲到播放列表（带排序）"""
        session = self._get_session()
        try:
            playlist = session.query(DB_Playlist).filter_by(id=playlist_id).first()
            music = session.query(DB_Music).filter_by(id=music_id).first()
            
            if not playlist or not music:
                self.logger.warning(f"播放列表或歌曲不存在：{playlist_id}/{music_id}")
                return False
            
            # 检查是否已存在
            existing = session.query(playlist_music).filter(
                playlist_music.c.playlist_id == playlist_id,
                playlist_music.c.music_id == music_id
            ).first()
            
            if existing:
                return True
            
            # 获取当前最大排序号
            max_sort = session.query(playlist_music.c.sort).filter(
                playlist_music.c.playlist_id == playlist_id
            ).order_by(playlist_music.c.sort.desc()).first()
            
            new_sort = (max_sort[0] + 1) if max_sort else 0
            
            # 添加关联记录（修复执行方式）
            insert_stmt = playlist_music.insert().values(
                playlist_id=playlist_id,
                music_id=music_id,
                sort=new_sort
            )
            session.execute(insert_stmt)
            session.commit()
            
            self.logger.info(f"添加歌曲{music_id}到播放列表{playlist_id}（排序：{new_sort}）")
            return True
            
        except Exception as e:
            session.rollback()
            self.logger.error(f"添加歌曲到播放列表失败：{e}", exc_info=True)
            return False
        finally:
            session.close()

    def remove_music_from_playlist(self, playlist_id: str, music_id: str) -> bool:
        """从播放列表移除歌曲（修复删除逻辑）"""
        session = self._get_session()
        try:
            # 检查关联是否存在
            existing = session.query(playlist_music).filter(
                playlist_music.c.playlist_id == playlist_id,
                playlist_music.c.music_id == music_id
            ).first()
            
            if not existing:
                return True
            
            # 修复：使用表对象的delete()方法
            del_stmt = playlist_music.delete().where(
                playlist_music.c.playlist_id == playlist_id,
                playlist_music.c.music_id == music_id
            )
            session.execute(del_stmt)
            session.commit()
            
            self.logger.info(f"从播放列表{playlist_id}移除歌曲{music_id}")
            return True
            
        except Exception as e:
            session.rollback()
            self.logger.error(f"移除歌曲失败：{e}", exc_info=True)
            return False
        finally:
            session.close()

    # ========== 歌单相关实现（新增删除歌单方法，修复同步逻辑） ==========
    def save_music_sheet(self, sheet: Dict[str, Any]) -> str:
        """保存歌单"""
        session = self._get_session()
        try:
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
            
        except Exception as e:
            session.rollback()
            self.logger.error(f"保存歌单失败：{e}", exc_info=True)
            raise
        finally:
            session.close()

    def _sync_sheet_musics(self, session, sheet_id: str, music_ids: List[str]):
        """同步歌单歌曲（带排序，修复删除逻辑）"""
        try:
            # 先删除现有关联（修复执行方式）
            del_stmt = sheet_music.delete().where(sheet_music.c.sheet_id == sheet_id)
            session.execute(del_stmt)
            
            # 批量添加新关联
            if music_ids:
                for idx, music_id in enumerate(music_ids):
                    # 检查歌曲是否存在
                    music_exists = session.query(DB_Music.id).filter_by(id=music_id).first()
                    if music_exists:
                        insert_stmt = sheet_music.insert().values(
                            sheet_id=sheet_id,
                            music_id=music_id,
                            sort=idx
                        )
                        session.execute(insert_stmt)
            
            session.commit()
        except Exception as e:
            session.rollback()
            raise

    def delete_music_sheet(self, sheet_id: str) -> bool:
        """删除歌单（新增，修复 Not an executable object 错误）"""
        session = self._get_session()
        try:
            # 检查歌单是否存在
            sheet = session.query(DB_MusicSheet).filter_by(id=sheet_id).first()
            if not sheet:
                self.logger.warning(f"歌单 {sheet_id} 不存在")
                return False
            
            # 开始事务
            session.begin()
            
            # 1. 删除歌单-歌曲关联（修复执行方式）
            del_sheet_music = sheet_music.delete().where(sheet_music.c.sheet_id == sheet_id)
            session.execute(del_sheet_music)
            
            # 2. 删除歌单主表（修复执行方式）
            del_sheet = DB_MusicSheet.__table__.delete().where(DB_MusicSheet.id == sheet_id)
            result = session.execute(del_sheet)
            
            session.commit()
            
            affected_rows = result.rowcount
            self.logger.info(f"删除歌单：{sheet_id}（影响行数：{affected_rows}）")
            return affected_rows > 0
            
        except Exception as e:
            session.rollback()
            self.logger.error(f"删除歌单失败：{e}", exc_info=True)
            return False
        finally:
            session.close()

    def get_all_music_sheets(self) -> List[Dict[str, Any]]:
        """获取所有歌单"""
        session = self._get_session()
        try:
            sheets = session.query(DB_MusicSheet).all()
            result = []
            
            for sheet in sheets:
                # 查询歌单歌曲数量
                music_count = session.query(sheet_music).filter(
                    sheet_music.c.sheet_id == sheet.id
                ).count()
                
                result.append({
                    "id": sheet.id,
                    "name": sheet.name,
                    "description": sheet.description,
                    "cover": sheet.cover,
                    "music_count": music_count,
                    "create_time": sheet.create_time.strftime("%Y-%m-%d %H:%M:%S")
                })
            
            # 按创建时间倒序
            result.sort(key=lambda x: x["create_time"], reverse=True)
            return result
        finally:
            session.close()

    def get_music_sheet_by_id(self, sheet_id: str) -> Optional[Dict[str, Any]]:
        """根据ID获取歌单"""
        session = self._get_session()
        try:
            sheet = session.query(DB_MusicSheet).filter_by(id=sheet_id).first()
            if not sheet:
                return None
            
            # 获取关联歌曲（带排序）
            music_list = []
            sheet_music_query = session.query(
                DB_Music, sheet_music.c.sort
            ).join(
                sheet_music, DB_Music.id == sheet_music.c.music_id
            ).filter(
                sheet_music.c.sheet_id == sheet_id
            ).order_by(
                sheet_music.c.sort
            ).all()
            
            for music, sort in sheet_music_query:
                music_list.append({
                    "id": music.id,
                    "name": music.name,
                    "artist": music.artist,
                    "album": music.album,
                    "duration": music.duration,
                    "sort": sort
                })
            
            return {
                "id": sheet.id,
                "name": sheet.name,
                "description": sheet.description,
                "cover": sheet.cover,
                "music_ids": [m["id"] for m in music_list],
                "musics": music_list,
                "create_time": sheet.create_time.strftime("%Y-%m-%d %H:%M:%S"),
                "update_time": sheet.update_time.strftime("%Y-%m-%d %H:%M:%S")
            }
        finally:
            session.close()

    # ========== 历史记录相关实现 ==========
    def save_play_history(self, music_id: str, play_time: int = None) -> bool:
        """保存播放历史"""
        session = self._get_session()
        try:
            # 检查歌曲是否存在
            if not session.query(DB_Music.id).filter_by(id=music_id).first():
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
            
            # 清理7天前的历史（可选）
            seven_days_ago = datetime.now() - timedelta(days=7)
            clean_stmt = DB_PlayHistory.__table__.delete().where(DB_PlayHistory.play_time < seven_days_ago)
            session.execute(clean_stmt)
            session.commit()
            
            self.logger.info(f"保存播放历史：{music_id}")
            return True
            
        except Exception as e:
            session.rollback()
            self.logger.error(f"保存播放历史失败：{e}", exc_info=True)
            return False
        finally:
            session.close()

    def get_play_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """获取播放历史"""
        session = self._get_session()
        try:
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
        finally:
            session.close()

    def save_search_history(self, keyword: str) -> bool:
        """保存搜索历史"""
        session = self._get_session()
        try:
            # 去重：如果1分钟内有相同关键词，不重复保存
            one_minute_ago = datetime.now() - timedelta(minutes=1)
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
            
            # 限制最多保存100条
            total = session.query(DB_SearchHistory).count()
            if total > 100:
                # 删除最早的记录
                oldest = session.query(DB_SearchHistory).order_by(
                    DB_SearchHistory.search_time.asc()
                ).first()
                if oldest:
                    session.delete(oldest)
            
            session.commit()
            self.logger.info(f"保存搜索历史：{keyword}")
            return True
            
        except Exception as e:
            session.rollback()
            self.logger.error(f"保存搜索历史失败：{e}", exc_info=True)
            return False
        finally:
            session.close()

    def get_search_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """获取搜索历史"""
        session = self._get_session()
        try:
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
        finally:
            session.close()

    # ========== 新增：清空历史方法 ==========
    def clear_play_history(self) -> bool:
        """清空播放历史"""
        session = self._get_session()
        try:
            del_stmt = DB_PlayHistory.__table__.delete()
            session.execute(del_stmt)
            session.commit()
            self.logger.info("清空播放历史成功")
            return True
        except Exception as e:
            session.rollback()
            self.logger.error(f"清空播放历史失败：{e}", exc_info=True)
            return False
        finally:
            session.close()

    def clear_search_history(self) -> bool:
        """清空搜索历史"""
        session = self._get_session()
        try:
            del_stmt = DB_SearchHistory.__table__.delete()
            session.execute(del_stmt)
            session.commit()
            self.logger.info("清空搜索历史成功")
            return True
        except Exception as e:
            session.rollback()
            self.logger.error(f"清空搜索历史失败：{e}", exc_info=True)
            return False
        finally:
            session.close()