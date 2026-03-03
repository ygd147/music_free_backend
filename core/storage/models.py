"""数据模型：ORM模型和序列化工具"""
from datetime import datetime
from pydantic import BaseModel, Field
from typing import List, Optional, Any,Dict
from uuid import uuid4

# 生成唯一ID
def generate_id(prefix: str = "m") -> str:
    """生成带前缀的唯一ID（如 m_123456）"""
    return f"{prefix}_{uuid4().hex[:8]}"

# ========== Pydantic模型（数据验证） ==========
class MusicModel(BaseModel):
    """歌曲数据模型"""
    id: Optional[str] = Field(default_factory=lambda: generate_id("m"))
    name: str
    artist: str
    album: Optional[str] = ""
    duration: Optional[int] = 0
    url: Optional[str] = ""
    lyric: Optional[str] = ""
    cover: Optional[str] = ""
    source: Optional[str] = ""  # 来源平台
    create_time: Optional[datetime] = Field(default_factory=datetime.now)
    update_time: Optional[datetime] = Field(default_factory=datetime.now)

    class Config:
        orm_mode = True
        json_encoders = {
            datetime: lambda v: v.strftime("%Y-%m-%d %H:%M:%S")
        }

class PlaylistModel(BaseModel):
    """播放列表模型"""
    id: Optional[str] = Field(default="default")
    name: Optional[str] = "默认播放列表"
    music_ids: List[str] = Field(default_factory=list)
    create_time: Optional[datetime] = Field(default_factory=datetime.now)
    update_time: Optional[datetime] = Field(default_factory=datetime.now)

class MusicSheetModel(BaseModel):
    """歌单模型"""
    id: Optional[str] = Field(default_factory=lambda: generate_id("s"))
    name: str
    description: Optional[str] = ""
    music_ids: List[str] = Field(default_factory=list)
    cover: Optional[str] = ""
    create_time: Optional[datetime] = Field(default_factory=datetime.now)
    update_time: Optional[datetime] = Field(default_factory=datetime.now)

class PlayHistoryModel(BaseModel):
    """播放历史模型"""
    id: Optional[str] = Field(default_factory=lambda: generate_id("ph"))
    music_id: str
    play_time: Optional[datetime] = Field(default_factory=datetime.now)
    play_duration: Optional[int] = 0  # 播放时长（秒）

class SearchHistoryModel(BaseModel):
    """搜索历史模型"""
    id: Optional[str] = Field(default_factory=lambda: generate_id("sh"))
    keyword: str
    search_time: Optional[datetime] = Field(default_factory=datetime.now)

# ========== 模型转换工具 ==========
def model_to_dict(model: BaseModel) -> Dict[str, Any]:
    """将Pydantic模型转换为字典"""
    return model.dict(exclude_none=True)

def dict_to_model(data: Dict[str, Any], model_cls: Any) -> BaseModel:
    """将字典转换为Pydantic模型"""
    return model_cls(**data)