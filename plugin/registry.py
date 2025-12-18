from typing import Dict, Type, List
import importlib
import pkgutil
from pathlib import Path
from functools import wraps
from .base import CLIPlugin

class PluginRegistry:
    """插件注册中心"""
    _plugins: Dict[str, Type[CLIPlugin]] = {}
    
    @classmethod
    def register(cls, plugin_cls: Type[CLIPlugin]) -> Type[CLIPlugin]:
        """注册插件的装饰器"""
        cls._plugins[plugin_cls.__name__] = plugin_cls
        return plugin_cls
    
    @classmethod
    def discover_plugins(cls, package_path: str, plugins_dir: str) -> None:
        """自动发现并加载插件
        
        Args:
            package_path: 插件包的导入路径
            plugins_dir: 插件目录的实际路径
        """
        try:
            
            # 扫描插件目录
            for finder, name, is_pkg in pkgutil.iter_modules([plugins_dir]):
                if not name.startswith('_'):  # 跳过私有模块
                    try:
                        importlib.import_module(f"{package_path}.{name}")
                    except Exception as e:
                        print(f"加载插件 {name} 失败: {str(e)}")
                        
        except Exception as e:
            print(f"插件发现过程失败: {str(e)}")