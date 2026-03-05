"""插件加载与验证工具"""
import os
import sys
import importlib
import inspect
from typing import Dict, List, Type, Optional
from pathlib import Path

from .base import BaseMusicPlugin, PluginLoadError

# ========== 插件加载工具 ==========
def get_plugin_dirs() -> List[Path]:
    """获取插件目录列表"""
    # 1. 内置插件目录（项目根目录/plugins）
    project_plugin_dir = Path(__file__).parent.parent.parent / "plugins"
    # 2. 用户自定义插件目录（~/.music_free/plugins）
    user_plugin_dir = Path.home() / ".music_free" / "plugins"
    
    plugin_dirs = []
    for dir_path in [project_plugin_dir, user_plugin_dir]:
        if dir_path.exists():
            plugin_dirs.append(dir_path)
            # 将目录加入Python路径
            if str(dir_path) not in sys.path:
                sys.path.insert(0, str(dir_path))
    
    return plugin_dirs

def scan_plugins() -> List[str]:
    """扫描所有可用插件（返回模块名列表）"""
    plugin_dirs = get_plugin_dirs()
    plugin_modules = []
    
    for plugin_dir in plugin_dirs:
        # 遍历目录下的.py文件（排除__init__.py）
        for file_path in plugin_dir.glob("*.py"):
            if file_path.name == "__init__.py":
                continue
            if file_path.name.startswith("_"):
                continue
            
            # 获取模块名（不带.py）
            module_name = file_path.stem
            plugin_modules.append(module_name)
    
    # 去重并排序
    return sorted(list(set(plugin_modules)))

def load_plugin(module_name: str) -> Type[BaseMusicPlugin]:
    """
    加载单个插件
    :param module_name: 插件模块名（如：netease）
    :return: 插件类
    """
    try:
        # 导入插件模块
        module = importlib.import_module(module_name)
        
        # 查找继承自BaseMusicPlugin的类
        plugin_class = None
        for name, obj in inspect.getmembers(module):
            if (
                inspect.isclass(obj) and 
                issubclass(obj, BaseMusicPlugin) and 
                obj != BaseMusicPlugin
            ):
                plugin_class = obj
                break
        
        if not plugin_class:
            raise PluginLoadError(f"插件{module_name}中未找到BaseMusicPlugin的子类")
        
        # 验证元数据
        if not hasattr(plugin_class, "meta") or not plugin_class.meta.name:
            raise PluginLoadError(f"插件{module_name}缺少必要的元数据")
        
        return plugin_class
    
    except ImportError as e:
        raise PluginLoadError(f"导入插件{module_name}失败：{e}")
    except Exception as e:
        raise PluginLoadError(f"加载插件{module_name}失败：{e}")

def validate_plugin(plugin_instance: BaseMusicPlugin) -> bool:
    """
    验证插件实例是否有效
    :param plugin_instance: 插件实例
    :return: 是否有效
    """
    try:
        # 检查元数据
        if not plugin_instance.meta.name:
            return False
        
        # 调用插件自验证
        return plugin_instance.validate()
    
    except Exception:
        return False