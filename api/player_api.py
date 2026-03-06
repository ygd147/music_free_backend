from fastapi import APIRouter, Body
from typing import Optional

from core.message_bus import message_bus
from core.player import audio_player

router = APIRouter(prefix="/player", tags=["播放器控制"])

# ------------------------------
# 播放状态查询（从MessageBus获取统一状态）
# ------------------------------
@router.get("/status")
def get_player_status():
    """获取播放状态（从MessageBus同步）"""
    state = message_bus.send_command("GetAppState")
    return {
        "code": 0,
        "data": {
            "player_state": state.get("player_state"),
            "current_music": state.get("current_music"),
            "volume": state.get("volume"),
            "repeat_mode": state.get("repeat_mode"),
            "current_position": state.get("current_position"),
            "playlist_count": state.get("playlist_count"),
            "storage_type": state.get("storage_type"),
            # 补充播放器原生状态
            "queue_size": len(audio_player.get_queue()),
            "play_mode": audio_player.get_play_mode(),
            "duration": round(audio_player.get_duration(), 2)
        }
    }

# ------------------------------
# 播放控制（通过MessageBus执行命令）
# ------------------------------
@router.post("/play")
def play(
    # 为每个 Body 参数添加 embed=True，适配平铺的 JSON 请求体
    url: Optional[str] = Body(None, embed=True, description="音乐URL/本地路径"),
    position: float = Body(0.0, embed=True, description="起始位置(秒)")
):
    """播放音乐（自动同步MySQL）"""
    success = message_bus.send_command("PlayerPlay", url, position)
    return {"code": 0, "success": success, "msg": "播放成功" if success else "播放失败"}

@router.post("/pause")
def pause():
    """暂停播放"""
    success = message_bus.send_command("PlayerPause")
    return {"code": 0, "success": success, "msg": "已暂停"}

@router.post("/resume")
def resume():
    """恢复播放"""
    success = message_bus.send_command("PlayerResume")
    return {"code": 0, "success": success, "msg": "已恢复播放"}

@router.post("/stop")
def stop():
    """停止播放"""
    success = message_bus.send_command("PlayerStop")
    return {"code": 0, "success": success, "msg": "已停止"}

@router.post("/next")
def next_song():
    """下一曲（自动保存播放历史）"""
    success = message_bus.send_command("PlayerNext")
    return {"code": 0, "success": success, "msg": "已切换下一曲"}

@router.post("/prev")
def prev_song():
    """上一曲（自动保存播放历史）"""
    success = message_bus.send_command("PlayerPrev")
    return {"code": 0, "success": success, "msg": "已切换上一曲"}

# ------------------------------
# 音量/进度/模式控制（同步MySQL）
# ------------------------------
@router.post("/volume")
def set_volume(volume: int = Body(..., embed=True)):
    """设置音量（0-100，持久化到MySQL）"""
    success = message_bus.send_command("PlayerSetVolume", volume)
    return {
        "code": 0,
        "success": success,
        "volume": volume,
        "msg": "音量设置成功" if success else "音量设置失败"
    }

@router.post("/seek")
def seek(position: float = Body(..., embed=True)):
    """调整播放进度（秒）"""
    success = message_bus.send_command("PlayerSeek", position)
    return {
        "code": 0,
        "success": success,
        "position": position,
        "msg": "进度调整成功" if success else "进度调整失败"
    }

@router.post("/mode")
def set_play_mode(mode: str = Body(..., embed=True)):
    """设置播放模式（sequence/loop/random，持久化到MySQL）"""
    success = message_bus.send_command("PlayerSetMode", mode)
    return {
        "code": 0,
        "success": success,
        "mode": mode,
        "msg": "播放模式设置成功" if success else "播放模式设置失败"
    }

# ------------------------------
# 播放队列（同步MySQL播放列表）
# ------------------------------
@router.get("/queue")
def get_queue():
    """获取播放队列（从MessageBus的播放列表同步）"""
    playlist = message_bus.get_playlist()
    queue = audio_player.get_queue()
    return {
        "code": 0,
        "data": {
            "mysql_playlist": [item.to_dict() for item in playlist],
            "player_queue": queue
        }
    }

@router.post("/queue/add")
def add_to_queue(items: list = Body(..., embed=True)):
    """添加到播放队列（自动保存到MySQL）"""
    success = message_bus.send_command("PlayerAddQueue", items)
    return {
        "code": 0,
        "success": success,
        "count": len(items),
        "msg": "已添加到队列" if success else "添加队列失败"
    }

@router.post("/queue/clear")
def clear_queue():
    """清空播放队列（同步清空MySQL播放列表）"""
    # 清空播放器队列
    audio_player.clear_queue()
    # 清空MySQL播放列表
    message_bus.send_command("ClearPlaylist")
    return {"code": 0, "msg": "播放队列已清空（同步MySQL）"}