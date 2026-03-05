"""FastAPI HTTP服务核心实现"""
import uvicorn
import json
from fastapi import FastAPI, Request, HTTPException,APIRouter
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import Optional, Any

from core.plugin_manager import plugin_manager
from core.local_music_manager import local_music_manager, LocalDirectory
from pydantic import BaseModel, Field

# 导入核心模块
from core.constants import logger, app_config, HTTP_SERVER_HOST, HTTP_SERVER_DEFAULT_PORT
from core.command_handler import cmd_handler


# ========== FastAPI实例初始化 ==========
app = FastAPI(
    title="MusicFree Python Backend API",
    description="MusicFree前后端分离Python后端接口",
    version="0.0.1"
)
# ========== 增强跨域配置 ==========
# 生产环境建议替换为具体的前端域名列表，如 ["http://127.0.0.1:8080", "http://localhost:8080"]
ALLOWED_ORIGINS = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,  # 允许携带凭证（cookies/Authorization）
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],  # 支持更多HTTP方法
    allow_headers=[
        "Content-Type", 
        "Authorization", 
        "X-Requested-With", 
        "X-Custom-Header",
        "Accept",
        "Origin",
        "Referer"
    ],  # 允许自定义Header
    expose_headers=["X-Service-Name", "X-Current-Port"],  # 暴露自定义响应头给前端
    max_age=3600  # OPTIONS预检请求缓存时间（秒），减少预检请求次数
)

# ========== 通用响应工具 ==========
@app.middleware("http")
async def add_response_header(request: Request, call_next):
    """全局响应中间件：统一添加响应头"""
    response = await call_next(request)
    response.headers["X-Service-Name"] = "MusicFreeBackend"
    response.headers["X-Current-Port"] = app_config.get_config("HTTP_SERVICE.currentPort") or "3001"
    # 额外添加跨域安全头
    response.headers["Access-Control-Allow-Credentials"] = "true"
    return response

def create_json_response(data: dict, status_code: int = 200):
    """创建标准化JSON响应"""
    return JSONResponse(
        content=data,
        status_code=status_code,
        media_type="application/json; charset=utf-8"
    )

# ========== 接口路由 ==========
@app.options("/api/command", tags=["核心接口"])
async def handle_options():
    """处理OPTIONS预检请求"""
    return create_json_response({"msg": "OK"}, 200)

@app.get("/api/command", tags=["核心接口"])
async def handle_get_command(
    cmd: str,
    args: Optional[str] = None
):
    """
    GET方式执行命令
    :param cmd: 命令名（如skip-next、get-current-music）
    :param args: 命令参数（JSON字符串）
    """
    # 解析参数
    parsed_args: Any = args
    if args:
        try:
            parsed_args = json.loads(args)
        except json.JSONDecodeError:
            # 非JSON格式直接作为字符串
            parsed_args = args

    # 执行命令
    params = {"cmd": cmd, "args": parsed_args}
    result = cmd_handler(params)
    return create_json_response(result)

@app.post("/api/command", tags=["核心接口"])
async def handle_post_command(request: Request):
    """
    POST方式执行命令
    支持Content-Type:
    - application/json
    - application/x-www-form-urlencoded
    """
    try:
        # 解析请求体
        content_type = request.headers.get("content-type", "")
        params: dict = {}

        if "application/json" in content_type:
            params = await request.json()

        elif "application/x-www-form-urlencoded" in content_type:
            form_data = await request.form()
            params = {
                "cmd": form_data.get("cmd", ""),
                "args": form_data.get("args")
            }
            # 尝试解析args为JSON
            if params["args"]:
                try:
                    params["args"] = json.loads(params["args"])
                except json.JSONDecodeError:
                    pass  # 非JSON则保留字符串

        else:
            raise HTTPException(
                status_code=400,
                detail=f"不支持的Content-Type：{content_type}（仅支持JSON/表单）"
            )

        # 执行命令
        result = cmd_handler(params)
        return create_json_response(result)

    except HTTPException as e:
        logger.warning(f"POST请求解析失败：{e.detail}")
        return create_json_response({
            "rtn_code": "100004",
            "rtn_msg": e.detail,
            "return_data": ""
        }, e.status_code)

    except Exception as e:
        logger.error("POST请求处理异常", exc_info=True)
        return create_json_response({
            "rtn_code": "100004",
            "rtn_msg": f"请求解析失败: {str(e)}",
            "return_data": ""
        }, 400)

@app.get("/api/health", tags=["基础接口"])
async def health_check():
    """健康检查接口"""
    return create_json_response({
        "rtn_code": "000000",
        "rtn_msg": "success",
        "return_data": json.dumps({
            "status": "running",
            "port": app_config.get_config("HTTP_SERVICE.currentPort"),
            "version": "0.0.1"
        })
    })

router = APIRouter(prefix="/plugins", tags=["插件管理"])

#插件
@router.get("/list")
async def list_plugins():
    """获取插件列表"""
    return {"code": 0, "data": plugin_manager.get_plugins_info()}

@router.post("/search")
async def search_music(keyword: str, source: str = None, page: int = 1, limit: int = 20):
    """搜索歌曲"""
    results = plugin_manager.search(keyword, source, page, limit)
    return {"code": 0, "data": results}

@router.get("/play-url")
async def get_play_url(music_id: str, source: str):
    """获取播放URL"""
    url = plugin_manager.get_play_url(music_id, source)
    return {"code": 0, "data": {"url": url}}


# ========== 新增：本地音乐管理路由 ==========
local_router = APIRouter(prefix="/local", tags=["本地音乐管理"])

class AddDirRequest(BaseModel):
    path: str = Field(..., description="本地目录的绝对路径")
    name: Optional[str] = Field(None, description="目录别名 (可选)")

@local_router.get("/dirs", summary="获取所有已添加的目录")
async def get_local_dirs():
    dirs = local_music_manager.get_all_dirs()
    return {"code": 0, "data": [{"id": d.id, "name": d.name, "path": d.path} for d in dirs]}

@local_router.post("/dirs", summary="添加一个本地目录")
async def add_local_dir(req: AddDirRequest):
    try:
        new_dir = local_music_manager.add_dir(req.path, req.name)
        return {"code": 0, "data": {"id": new_dir.id, "msg": "添加成功"}}
    except ValueError as e:
        return {"code": 1, "msg": str(e)}

@local_router.delete("/dirs/{dir_id}", summary="删除一个本地目录")
async def delete_local_dir(dir_id: str):
    success = local_music_manager.delete_dir(dir_id)
    if success:
        return {"code": 0, "msg": "删除成功"}
    return {"code": 1, "msg": "目录ID不存在"}

@local_router.get("/scan/{dir_id}", summary="扫描目录并返回音乐列表")
async def scan_directory(dir_id: str):
    try:
        playlist = local_music_manager.scan_music(dir_id)
        return {"code": 0, "data": playlist}
    except ValueError as e:
        return {"code": 1, "msg": str(e)}


app.include_router(router)
app.include_router(local_router)

# ========== 服务启动逻辑 ==========
def start_server_with_retry(initial_port: int = HTTP_SERVER_DEFAULT_PORT):
    """启动HTTP服务，端口占用时自动重试"""
    port = initial_port
    max_retry = 100  # 最大重试100个端口

    while port < initial_port + max_retry:
        try:
            # 更新当前端口配置
            app_config.set_config("HTTP_SERVICE.currentPort", str(port))
            # 启动服务（阻塞式）
            uvicorn.run(
                app,
                host=HTTP_SERVER_HOST,
                port=port,
                log_level="info",
                access_log=True,
                use_colors=False
            )
            break
        except OSError as e:
            if "address already in use" in str(e):
                logger.warning(f"端口 {port} 被占用，尝试 {port + 1}")
                port += 1
            else:
                logger.error(f"启动HTTP服务失败", exc_info=True)
                raise
    else:
        raise RuntimeError(f"端口重试{max_retry}次后仍失败，无法启动服务")

# ========== 本地测试启动 ==========
if __name__ == "__main__":
    start_server_with_retry(HTTP_SERVER_DEFAULT_PORT)