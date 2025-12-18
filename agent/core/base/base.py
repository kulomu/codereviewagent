from abc import ABC, abstractmethod
from typing import AsyncGenerator, List
from pathlib import Path
import sys

from .types import AgentConfig, StepResult
from .executor import AgentExecutor
from .memory import MemoryManager
from agent.llm.base import Message

class BaseAgent(ABC):
    """Agent 基类"""
    
    def __init__(self, config: AgentConfig):
        self.config = config
        self.executor = AgentExecutor(config.max_steps, config.step_timeout)
        self.memory = MemoryManager(config.memory_limit)
        
    @abstractmethod
    async def step(self, context: str | List[Message]) -> AsyncGenerator[StepResult, None]:
        """执行单个步骤"""
        pass

    async def run(self, input_text: str) -> AsyncGenerator[str, None]:
        """执行任务"""
        self.memory.remember(input_text, type="user")
        async for output in self.executor.execute(self.step, input_text):
            yield output

    async def cleanup(self) -> None:
        """资源清理"""
        self.memory.clear()