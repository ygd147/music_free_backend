"""MusicFree Python 后端 - 主入口"""
import signal
import sys
from core.service_manager import service_manager
from core.constants import logger

def signal_handler(sig, frame):
    """信号处理：捕获退出信号"""
    logger.info(f"接收到退出信号 {sig}，正在关闭服务...")
    service_manager.destroy()
    logger.info("===== MusicFree Python Backend 已退出 =====")
    sys.exit(0)

def main():
    """应用启动入口"""
    # 注册信号处理器
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    logger.info("===== MusicFree Python Backend 启动 =====")
    try:
        # 初始化服务管理器
        service_manager.setup()
        # 阻塞主线程（保持服务运行）
        logger.info("服务已启动，按 Ctrl+C 退出")
        while True:
            pass
    except Exception as e:
        logger.error("应用启动失败", exc_info=True)
        service_manager.destroy()
        sys.exit(1)

if __name__ == "__main__":
    main()