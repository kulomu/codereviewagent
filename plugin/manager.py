from typing import Dict, List, Optional, Union, Any
import typer
import logging
from .base import CLIPlugin
from .registry import PluginRegistry

logger = logging.getLogger(__name__)

class PluginManager:
    """插件管理器"""
    
    def __init__(self):
        self._loaded_plugins: Dict[str, CLIPlugin] = {}
        self._initialized = False
        
    def load_all(self) -> None:
        """加载所有已注册的插件"""
        try:
            for plugin_cls in PluginRegistry._plugins.values():
                try:
                    plugin = plugin_cls()
                    self._loaded_plugins[plugin.name] = plugin
                    logger.info(f"加载插件: {plugin.name}")
                except Exception as e:
                    logger.error(f"加载插件 {plugin_cls.__name__} 失败: {str(e)}")
        except Exception as e:
            logger.error(f"插件加载过程出错: {str(e)}")
            
    async def initialize_all(self) -> None:
        """初始化所有插件"""
        if self._initialized:
            return
            
        for plugin in self._loaded_plugins.values():
            try:
                await plugin.initialize()
                logger.info(f"初始化插件: {plugin.name}")
            except Exception as e:
                logger.error(f"初始化插件 {plugin.name} 失败: {str(e)}")
                
        self._initialized = True
    
    async def shutdown_all(self) -> None:
        """关闭所有插件"""
        for plugin in self._loaded_plugins.values():
            try:
                await plugin.shutdown()
                logger.info(f"关闭插件: {plugin.name}")
            except Exception as e:
                logger.error(f"关闭插件 {plugin.name} 失败: {str(e)}")
    
    def get_plugins(self) -> List[CLIPlugin]:
        """获取所有已加载的插件"""
        return list(self._loaded_plugins.values())
    
    def get_plugin(self, name: str) -> Optional[CLIPlugin]:
        """获取指定名称的插件"""
        return self._loaded_plugins.get(name)
    
    def get_all_commands(self) -> List[Union[typer.Typer, Any]]:
        """获取所有插件命令"""
        commands = []
        for plugin in self._loaded_plugins.values():
            try:
                commands.extend(plugin.commands)
            except Exception as e:
                logger.error(f"获取插件 {plugin.name} 命令失败: {str(e)}")
        return commands
    
    def get_plugin_commands(self, name: str) -> List[Union[typer.Typer, Any]]:
        """获取指定插件的命令"""
        plugin = self.get_plugin(name)
        if plugin:
            return plugin.commands
        return []
    
    @property
    def plugin_count(self) -> int:
        """已加载的插件数量"""
        return len(self._loaded_plugins)
    
    def is_plugin_loaded(self, name: str) -> bool:
        """检查插件是否已加载"""
        return name in self._loaded_plugins
    
    def __repr__(self) -> str:
        return f"PluginManager(plugins={list(self._loaded_plugins.keys())})"