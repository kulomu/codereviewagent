from abc import ABC, abstractmethod
from typing import Dict, List, Optional, AsyncGenerator, Any, Union
from dataclasses import dataclass
from enum import Enum
import json
import logging

logger = logging.getLogger(__name__)

class LLMRole(str, Enum):
    """对话角色"""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    FUNCTION = "function"

@dataclass
class Message:
    """对话消息"""
    role: LLMRole
    content: str
    name: Optional[str] = None
    function_call: Optional[Dict[str, Any]] = None
    function_call_id: Optional[str] = None

@dataclass
class Function:
    """函数定义"""
    name: str
    description: str
    parameters: Dict[str, Any]

class LLMConfig:
    """LLM 配置"""
    def __init__(
        self,
        temperature: float = 0.7,
        top_p: float = 1.0,
        max_tokens: Optional[int] = None,
        presence_penalty: float = 0.0,
        frequency_penalty: float = 0.0,
        stream: bool = True,
        stop: Optional[List[str]] = None,
        **kwargs
    ):
        self.temperature = temperature
        self.top_p = top_p
        self.max_tokens = max_tokens
        self.presence_penalty = presence_penalty
        self.frequency_penalty = frequency_penalty
        self.stream = stream
        self.stop = stop
        self.extra_kwargs = kwargs

class BaseLLM(ABC):
    """LLM 基类"""
    
    def __init__(self, config: Optional[LLMConfig] = None):
        self.config = config or LLMConfig()
        self._history: List[Message] = []
    
    @abstractmethod
    async def generate(
        self,
        prompt: Optional[str] = None,
        messages: Optional[List[Message]] = None,
        system: Optional[str] = None,
        functions: Optional[List[Function]] = None,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """生成回复
        
        Args:
            prompt: 用户输入
            messages: 对话历史
            system: 系统提示词
            functions: 可用函数列表
            **kwargs: 其他参数
            
        Yields:
            生成的回复片段
        """
        raise NotImplementedError
    
    @abstractmethod
    async def chat(
        self,
        messages: List[Message],
        functions: Optional[List[Function]] = None,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """对话模式
        
        Args:
            messages: 对话历史
            functions: 可用函数列表
            **kwargs: 其他参数
            
        Yields:
            生成的回复片段
        """
        raise NotImplementedError
    
    def add_message(self, message: Message) -> None:
        """添加消息到历史"""
        self._history.append(message)
    
    def clear_history(self) -> None:
        """清空对话历史"""
        self._history.clear()
    
    @property
    def history(self) -> List[Message]:
        """获取对话历史"""
        return self._history.copy()
    
    async def function_call(
        self,
        function: Function,
        arguments: Dict[str, Any]
    ) -> AsyncGenerator[str, None]:
        """调用函数并返回结果
        
        Args:
            function: 函数定义
            arguments: 函数参数
            
        Yields:
            函数执行结果
        """
        try:
            result = {
                "name": function.name,
                "arguments": arguments
            }
            yield json.dumps(result, ensure_ascii=False)
        except Exception as e:
            logger.error(f"函数调用失败: {str(e)}")
            yield f"函数调用出错: {str(e)}"
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(config={self.config})"

    async def __aenter__(self):
        """异步上下文管理器入口"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        self.clear_history()