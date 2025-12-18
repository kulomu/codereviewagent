from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, AsyncGenerator, Union, Callable
from dataclasses import dataclass
import typer
import click
from prompt_toolkit.styles import Style

@dataclass
class CommandHelp:
    """命令帮助信息"""
    command: str
    description: str
    usage: str = ""
    examples: List[str] = None

class CLIPlugin(ABC):
    """CLI 插件基类"""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """插件名称"""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """插件描述"""
        pass
    
    @property
    def version(self) -> str:
        """插件版本"""
        return "0.1.0"
    
    @property
    def commands(self) -> List[Union[typer.Typer, Callable]]:
        """CLI 命令列表
        
        Returns:
            List[Union[typer.Typer, Callable]]: 返回命令列表，可以是 typer.Typer 实例或者函数
            
        Example:
            ```python
            @property
            def commands(self):
                app = typer.Typer()
                
                @app.command()
                def hello(name: str):
                    print(f"Hello {name}!")
                    
                return [app]
            ```
        """
        return []
    
    @property
    def chat_commands(self) -> Dict[str, CommandHelp]:
        """聊天命令列表，返回命令帮助信息字典"""
        return {}
    
    @property
    def styles(self) -> Style:
        """插件自定义样式"""
        return Style.from_dict({})
    
    async def initialize(self, context: Dict[str, Any] = None) -> None:
        """插件初始化
        
        Args:
            context: 初始化上下文
        """
        pass
    
    async def shutdown(self) -> None:
        """插件清理"""
        pass
    
    async def on_chat_command(self, command: str, args: str, context: Dict[str, Any]) -> AsyncGenerator[str, None]:
        """处理聊天命令
        
        Args:
            command: 命令名称
            args: 命令参数
            context: 上下文信息
            
        Yields:
            命令执行结果
        """
        yield f"[插件 {self.name}] 命令 {command} 未实现"
    
    async def on_chat_message(self, message: str, context: Dict[str, Any]) -> AsyncGenerator[str, None]:
        """处理聊天消息
        
        Args:
            message: 用户消息
            context: 上下文信息
            
        Yields:
            处理结果
        """
        pass
    
    def get_command_help(self, command: str) -> Optional[CommandHelp]:
        """获取命令帮助信息"""
        return self.chat_commands.get(command)
    
    def format_help(self) -> str:
        """格式化插件帮助信息"""
        help_text = [f"\n{self.description} (v{self.version})"]
        
        if self.chat_commands:
            help_text.append("\n支持的命令：")
            for cmd, help_info in self.chat_commands.items():
                help_text.append(f":{cmd} - {help_info.description}")
                if help_info.usage:
                    help_text.append(f"  用法：{help_info.usage}")
                if help_info.examples:
                    help_text.append("  示例：")
                    for example in help_info.examples:
                        help_text.append(f"    {example}")
                        
        return "\n".join(help_text)

class BuiltinPlugin(CLIPlugin):
    """内置插件基类"""
    
    @property
    def is_builtin(self) -> bool:
        return True