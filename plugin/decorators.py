from functools import wraps
from typing import Type
from .base import CLIPlugin
from .registry import PluginRegistry

def register_plugin(cls: Type[CLIPlugin]) -> Type[CLIPlugin]:
    """插件类装饰器"""
    return PluginRegistry.register(cls)