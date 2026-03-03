"""命令处理器：统一处理所有业务命令，返回标准化响应"""
import json
from typing import Dict, Any
from .constants import logger, SUCCESS_RESP, ERROR_RESP_TPL, RepeatMode
from .message_bus import message_bus

def cmd_handler(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    处理前端传入的命令
    :param params: {"cmd": 命令名, "args": 命令参数}
    :return: 标准化响应字典
    """
    # 基础参数校验
    cmd = params.get("cmd")
    args = params.get("args")
    resp = SUCCESS_RESP.copy()

    if not cmd:
        return ERROR_RESP_TPL.format(code="100003", msg="缺少cmd参数")

    logger.info(f"处理命令：{cmd}，参数：{args}")

    try:
        # ========== 播放控制类命令 ==========
        if cmd == "skip-next":
            message_bus.send_command("SkipToNext")

        elif cmd == "skip-prev":
            message_bus.send_command("SkipToPrevious")

        elif cmd == "set-repeat-mode":
            if args not in [RepeatMode.Shuffle, RepeatMode.Queue, RepeatMode.Loop]:
                return ERROR_RESP_TPL.format(code="100001", msg="无效的重复模式（仅支持0/1/2）")
            message_bus.send_command("SetRepeatMode", args)

        elif cmd == "set-player-state":
            message_bus.send_command("TogglePlayerState")

        elif cmd == "set-play-music":
            if not isinstance(args, dict) or "id" not in args:
                return ERROR_RESP_TPL.format(code="100005", msg="播放歌曲参数无效（需包含id）")
            message_bus.send_command("PlayMusic", args)

        elif cmd == "set-volume":
            if not isinstance(args, int) or args < 0 or args > 100:
                return ERROR_RESP_TPL.format(code="100006", msg="音量参数无效（0-100）")
            message_bus.send_command("setVolume", args)

        elif cmd == "set-seek-to":
            if not isinstance(args, int) or args < 0:
                return ERROR_RESP_TPL.format(code="100007", msg="进度参数无效（非负整数）")
            message_bus.send_command("setSeekTo", args)

        elif cmd == "set-audio-device":
            if not isinstance(args, str):
                return ERROR_RESP_TPL.format(code="100009", msg="音频设备ID必须为字符串")
            message_bus.send_command("setAudioDevice", args)

        # ========== 数据查询类命令 ==========
        elif cmd == "get-current-music":
            resp["return_data"] = json.dumps(message_bus.get_app_state(), ensure_ascii=False)

        elif cmd == "get-playlist":
            resp["return_data"] = json.dumps(message_bus.get_play_list(), ensure_ascii=False)

        elif cmd == "get-player-state":
            state_data = {
                "state": message_bus.get_app_state()["player_state"],
                "repeatMode": message_bus.get_app_state()["repeat_mode"]
            }
            resp["return_data"] = json.dumps(state_data, ensure_ascii=False)

        elif cmd == "get-sheets":
            resp["return_data"] = json.dumps(message_bus.get_music_sheets(), ensure_ascii=False)

        elif cmd == "get-search-result":
            resp["return_data"] = json.dumps(message_bus.get_search_result(), ensure_ascii=False)

        elif cmd == "get-audio-devices":
            resp["return_data"] = json.dumps(message_bus.get_audio_devices(), ensure_ascii=False)

        elif cmd == "get-volume":
            resp["return_data"] = json.dumps(message_bus.get_volume(), ensure_ascii=False)

        # ========== 播放列表/歌单类命令 ==========
        elif cmd == "add-to-playlist":
            if not isinstance(args, dict) or "id" not in args:
                return ERROR_RESP_TPL.format(code="100010", msg="添加播放列表参数无效（需包含id）")
            message_bus.send_command("AddToPlaylist", args)

        elif cmd == "remove-from-playlist":
            if not isinstance(args, str):
                return ERROR_RESP_TPL.format(code="100011", msg="移除播放列表参数无效（需为歌曲ID）")
            message_bus.send_command("RemoveFromPlaylist", args)

        elif cmd == "sync-music-sheets":
            if not isinstance(args, list):
                return ERROR_RESP_TPL.format(code="100012", msg="同步歌单参数无效（需为列表）")
            message_bus.send_command("SyncMusicSheets", args)

        # ========== 搜索类命令 ==========
        elif cmd == "search-music":
            if not isinstance(args, str) or len(args.strip()) == 0:
                return ERROR_RESP_TPL.format(code="100008", msg="搜索关键词不能为空")
            # 模拟搜索（实际需对接插件系统）
            message_bus.app_state.search_result = {
                "keyword": args,
                "result": [
                    {"id": "search1", "name": f"搜索结果-{args}", "artist": "未知歌手"}
                ],
                "state": "finished"
            }
            logger.info(f"执行搜索：{args}，返回{len(message_bus.app_state.search_result['result'])}条结果")

        # ========== 未知命令 ==========
        else:
            return ERROR_RESP_TPL.format(code="100002", msg=f"未知命令: {cmd}")

        return resp

    except Exception as e:
        logger.error(f"执行命令{cmd}失败", exc_info=True)
        return ERROR_RESP_TPL.format(
            code="999999",
            msg=f"执行失败: {str(e)}"
        )