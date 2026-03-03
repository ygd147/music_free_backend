"""服务管理器：模拟原有ServiceManager，管理子服务和HTTP服务生命周期"""
import subprocess
import threading
import os
import sys
from typing import Dict, Optional
from pathlib import Path
from .constants import logger, app_config, HTTP_SERVER_DEFAULT_PORT, HTTP_SERVER_HOST

class ServiceManager:
    """服务生命周期管理核心"""
    def __init__(self):
        self._services: Dict[str, Optional[dict]] = {}  # 修正类型注解
        self._http_server_thread: Optional[threading.Thread] = None  # HTTP服务线程
        self._service_dir = Path(__file__).parent.parent / ".service"  # 子服务目录
        self._service_dir.mkdir(exist_ok=True)

    def add_service(self, service_name: str, service_script: str = ""):
        """
        添加子服务
        :param service_name: 服务名
        :param service_script: 服务脚本路径（默认：.service/{service_name小写+下划线}.py）
        """
        if service_name in self._services:
            logger.warning(f"服务已存在：{service_name}")
            return

        # 修复：保留服务名的下划线格式（RequestForwarder → request_forwarder.py）
        if not service_script:
            # 驼峰转下划线：RequestForwarder → request_forwarder
            snake_case_name = ''.join(['_' + c.lower() if c.isupper() else c for c in service_name]).lstrip('_')
            service_script = str(self._service_dir / f"{snake_case_name}.py")
        
        self._services[service_name] = {
            "process": None,
            "script": service_script
        }
        logger.info(f"添加服务：{service_name}（脚本：{service_script}）")

    def start_service(self, service_name: str):
        """启动子服务"""
        service = self._services.get(service_name)
        if not service:
            logger.warning(f"服务不存在：{service_name}")
            return

        script_path = service["script"]
        if not Path(script_path).exists():
            logger.warning(f"服务脚本不存在：{script_path}，跳过启动")
            return

        try:
            # 启动子进程
            proc = subprocess.Popen(
                [sys.executable, script_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=str(self._service_dir.parent)
            )
            service["process"] = proc
            logger.info(f"启动服务：{service_name} (PID: {proc.pid})")

            # 异步监听进程输出
            def log_output(proc: subprocess.Popen, name: str):
                while proc.poll() is None:
                    if proc.stdout:
                        line = proc.stdout.readline()
                        if line:
                            logger.info(f"[{name}] {line.strip()}")
                # 进程退出处理
                exit_code = proc.poll()
                if exit_code != 0:
                    stderr = proc.stderr.read() if proc.stderr else ""
                    logger.error(f"服务{name}异常退出（码：{exit_code}）：{stderr}")
                else:
                    logger.info(f"服务{name}正常退出（码：{exit_code}）")

            threading.Thread(target=log_output, args=(proc, service_name), daemon=True).start()

        except Exception as e:
            logger.error(f"启动服务{service_name}失败", exc_info=True)

    def stop_service(self, service_name: str):
        """停止子服务"""
        service = self._services.get(service_name)
        if not service or not service["process"]:
            logger.warning(f"服务未运行：{service_name}")
            return

        proc = service["process"]
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)  # 等待5秒退出
                logger.info(f"停止服务：{service_name} (PID: {proc.pid})")
            except subprocess.TimeoutExpired:
                proc.kill()
                logger.warning(f"强制终止服务：{service_name} (PID: {proc.pid})")
        service["process"] = None

    def _start_http_server(self):
        """启动HTTP服务（内部方法）"""
        from api.main import app
        import uvicorn

        port = HTTP_SERVER_DEFAULT_PORT
        # 端口重试逻辑
        while port < HTTP_SERVER_DEFAULT_PORT + 100:
            try:
                logger.info(f"尝试启动HTTP服务：{HTTP_SERVER_HOST}:{port}")
                app_config.set_config("HTTP_SERVICE.currentPort", str(port))
                # 启动uvicorn服务
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
                    raise
        else:
            raise RuntimeError("端口重试次数超限，无法启动HTTP服务")

    def start_http_server(self):
        """启动HTTP服务（异步线程）"""
        if self._http_server_thread and self._http_server_thread.is_alive():
            logger.warning("HTTP服务已在运行")
            return

        self._http_server_thread = threading.Thread(
            target=self._start_http_server,
            daemon=True,
            name="HTTP-Server-Thread"
        )
        self._http_server_thread.start()
        logger.info("HTTP服务线程已启动")

    def setup(self):
        """初始化所有服务"""
        logger.info("===== 初始化ServiceManager =====")
        # 1. 添加并启动内置子服务
        self.add_service("RequestForwarder")
        self.start_service("RequestForwarder")

        # 2. 启动HTTP接口服务
        self.start_http_server()

        logger.info("===== ServiceManager初始化完成 =====")

    def destroy(self):
        """销毁所有服务"""
        logger.info("===== 销毁ServiceManager =====")
        # 1. 停止所有子服务
        for service_name in self._services.keys():
            self.stop_service(service_name)

        # 2. 停止HTTP服务（简化处理：线程为守护线程，主进程退出自动终止）
        if self._http_server_thread and self._http_server_thread.is_alive():
            logger.info("HTTP服务线程将随主进程退出")

        logger.info("===== ServiceManager销毁完成 =====")

# 全局服务管理器实例
service_manager = ServiceManager()