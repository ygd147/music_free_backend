"""核心常量、配置管理、日志配置"""
import logging
import os
from configparser import ConfigParser
from pathlib import Path
from dataclasses import dataclass
# 新增：加载环境变量
from dotenv import load_dotenv

# 加载.env文件
load_dotenv()

# ========== 日志配置 ==========
def setup_logger():
    """初始化日志系统"""
    log_dir = Path.home() / ".music_free" / "logs"
    log_dir.mkdir(exist_ok=True, parents=True)
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_dir / "music_free.log", encoding="utf-8"),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger("music_free_backend")

logger = setup_logger()

# ========== MySQL配置类 ==========
@dataclass
class MySQLConfig:
    """MySQL配置"""
    host: str = os.getenv("MYSQL_HOST", "127.0.0.1")
    port: int = int(os.getenv("MYSQL_PORT", 3306))
    user: str = os.getenv("MYSQL_USER", "root")
    password: str = os.getenv("MYSQL_PASSWORD", "")
    database: str = os.getenv("MYSQL_DB", "music_free")
    charset: str = os.getenv("MYSQL_CHARSET", "utf8mb4")
    
    def get_connection_url(self) -> str:
        """获取SQLAlchemy连接URL"""
        return f"mysql+pymysql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}?charset={self.charset}"

# 全局MySQL配置实例
mysql_config = MySQLConfig()

# ========== 配置管理类 ==========
class AppConfig:
    """模拟原有AppConfig，管理应用配置"""
    def __init__(self):
        self.config_dir = Path.home() / ".music_free"
        self.config_path = self.config_dir / "config.ini"
        self.config = ConfigParser()
        self._init_default_config()

    def _init_default_config(self):
        """初始化默认配置"""
        self.config_dir.mkdir(exist_ok=True)
        default_config = {
            "HTTP_SERVICE": {
                "port": "3001",
                "host": "0.0.0.0",
                "currentPort": "3001"
            },
            "PLAYER": {
                "when_device_removed": "pause",
                "default_quality": "high",
                "volume": "100"
            },
            "STORAGE": {
                "type": os.getenv("STORAGE_TYPE", "sqlite"),  # 新增：从环境变量读取存储类型
                "music_sheets_path": str(self.config_dir / "music_sheets.json"),
                "playlist_path": str(self.config_dir / "playlist.json")
            }
        }

        # 读取现有配置或初始化
        if self.config_path.exists():
            self.config.read(self.config_path, encoding="utf-8")
        else:
            for section, items in default_config.items():
                self.config[section] = items
            self._save_config()

    def _save_config(self):
        """保存配置到文件"""
        with open(self.config_path, "w", encoding="utf-8") as f:
            self.config.write(f)

    def get_config(self, key: str) -> str | None:
        """读取配置，格式：section.key"""
        try:
            section, k = key.split(".")
            return self.config.get(section, k, fallback=None)
        except ValueError:
            logger.error(f"配置键格式错误：{key}（需为section.key）")
            return None

    def set_config(self, key: str, value: str):
        """设置配置，格式：section.key"""
        try:
            section, k = key.split(".")
            if section not in self.config:
                self.config[section] = {}
            self.config[section][k] = value
            self._save_config()
            logger.info(f"配置已更新：{key} = {value}")
        except ValueError:
            logger.error(f"配置键格式错误：{key}（需为section.key）")

# 全局配置实例
app_config = AppConfig()

# ========== 枚举常量 ==========
@dataclass(frozen=True)
class RepeatMode:
    """播放模式枚举（对齐原有TS）"""
    Shuffle = 0  # 随机
    Queue = 1    # 顺序
    Loop = 2     # 单曲循环

@dataclass(frozen=True)
class RequestStateCode:
    """请求状态码（对齐原有TS）"""
    PENDING_FIRST_PAGE = "pending_first_page"
    PENDING_REST_PAGE = "pending_rest_page"
    PARTLY_DONE = "partly_done"
    FINISHED = "finished"

# ========== 响应格式常量 ==========
SUCCESS_RESP = {"rtn_code": "000000", "rtn_msg": "success", "return_data": ""}
ERROR_RESP_TPL = {
    "rtn_code": "{code}",
    "rtn_msg": "{msg}",
    "return_data": ""
}

# ========== HTTP服务常量 ==========
HTTP_SERVER_DEFAULT_PORT = int(app_config.get_config("HTTP_SERVICE.port") or 3001)
HTTP_SERVER_HOST = app_config.get_config("HTTP_SERVICE.host") or "0.0.0.0"