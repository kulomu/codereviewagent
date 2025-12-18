from abc import ABC, abstractmethod
from typing import Dict, List, Optional, AsyncGenerator, Any, Union, TypeVar, Generic
from dataclasses import dataclass
from enum import Enum
import time
import asyncio
from agent.llm.base import BaseLLM, Message, LLMRole, Function
import logging
from pathlib import Path
import sys

logger = logging.getLogger(__name__)

class AgentState(Enum):
    """Agent 状态"""
    READY = "ready"      # 已初始化，可以开始工作
    RUNNING = "running"  # 正在执行任务
    ERROR = "error"      # 发生错误
    STOPPED = "stopped"  # 已停止

@dataclass
class AgentMemory:
    """Agent 记忆单元"""
    id: str                    # 记忆ID
    type: str                  # 记忆类型
    content: Any              # 记忆内容
    timestamp: float          # 时间戳
    metadata: Dict[str, Any]  # 元数据

@dataclass
class StepResult:
    """步骤执行结果"""
    output: str           # 当前步骤的输出
    next_input: str      # 下一步骤的输入
    is_finished: bool    # 是否完成
    final_answer: Optional[str] = None  # 最终答案

class BaseAgent(ABC):
    """ Agent 基类"""
    
    def __init__(
        self,
        llm: BaseLLM,
        system_prompt: Optional[str] = None,
        functions: Optional[List[Function]] = None,
        max_steps: int = 10,
        step_timeout: float = 30.0,
        memory_limit: int = 1000
    ):
        self.llm = llm
        self.system_prompt = system_prompt
        self.functions = functions or []
        self.max_steps = max_steps
        self.step_timeout = step_timeout
        self.memory_limit = memory_limit
        
        # 状态管理
        self._state = AgentState.READY
        self._step_count = 0
        self._last_action_time = time.time()
        
        # 记忆管理
        self._memory: List[AgentMemory] = []
        self._context: Dict[str, Any] = {}
        self._message_history: List[Message] = []
    
    @property
    def state(self) -> AgentState:
        """获取当前状态"""
        return self._state
    
    async def start(self) -> None:
        """启动 Agent"""
        if self._state != AgentState.READY:
            raise RuntimeError("Agent 状态错误")
        self._state = AgentState.RUNNING
        
    async def stop(self) -> None:
        """停止 Agent"""
        self._state = AgentState.STOPPED
        await self.cleanup()
    
    @abstractmethod
    async def step(self, context: str| List[Message]) -> AsyncGenerator[StepResult, None]:
        """执行单个步骤
        
        子类必须实现此方法定义具体的步骤执行逻辑
        
        Args:
            context: 当前上下文
            
        Yields:
            StepResult: 步骤执行结果
        """
        pass

    async def run(self, input_text: str) -> AsyncGenerator[str, None]:
        """执行任务"""
        if self._state != AgentState.RUNNING:
            if self._state == AgentState.READY:
                await self.start()
            else:
                raise RuntimeError(f"Agent 状态错误: {self._state}")
        
        context = input_text
        self.remember(input_text, type="user")
        try:
            # 重置步骤计数
            self._step_count = 0
            while self._step_count < self.max_steps:
                self._step_count += 1
                
                async with asyncio.timeout(self.step_timeout):
                    async for result in self.step(context):
                        yield result.output
                        
                        if result.is_finished:
                            if result.final_answer:
                                yield f"\n=== 任务完成 ===\n{result.final_answer}\n"
                            # 任务完成后重置步骤计数
                            self._step_count = 0    
                            return

                        if result.next_input is not None:                      
                            context = result.next_input
            if self._step_count >= self.max_steps:
                yield f"\n[错误] 任务执行步骤超过最大限制 ({self.max_steps} 步)，建议:\n"
                yield "1. 尝试将问题拆分为更小的部分\n"
                yield "2. 使用更明确的指令\n"
                yield "3. 如果确实需要更多步骤，可以调整 max_steps 参数\n"
                # 重置步骤计数
                self._step_count = 0        
        except Exception as e:
            self._state = AgentState.ERROR
            logger.error(f"执行失败: {str(e)}")
            raise

    def remember(self, content: Any, type: str = "default", metadata: Dict[str, Any] = None) -> str:
        """记住信息
        
        Args:
            content: 记忆内容
            type: 记忆类型
            metadata: 元数据
        """
        memory_id = f"mem_{len(self._memory)}"
        memory = AgentMemory(
            id=memory_id,
            type=type,
            content=content,
            timestamp=time.time(),
            metadata=metadata or {}
        )
        
        self._memory.append(memory)
        self._trim_memory()
        return memory_id
    
    def recall(
        self,
        memory_id: Optional[str] = None,
        type: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[AgentMemory]:
        """回忆信息"""
        memories = self._memory
        
        if memory_id:
            memories = [m for m in memories if m.id == memory_id]
        if type:
            memories = [m for m in memories if m.type == type]
        if limit:
            memories = memories[-limit:]
            
        return memories
    
    def _trim_memory(self) -> None:
        """清理超出限制的记忆"""
        if len(self._memory) > self.memory_limit:
            self._memory = self._memory[-self.memory_limit:]
    
    def _prepare_messages(self, input_text: str) -> List[Message]:
        """准备对话消息"""
        messages = []
        if self.system_prompt:
            messages.append(Message(
                role=LLMRole.SYSTEM,
                content=self.system_prompt
            ))
        messages.extend(self._message_history)
        messages.append(Message(
            role=LLMRole.USER,
            content=input_text
        ))
        return messages
    
    def _parse_next_action(self, thought: str) -> Optional[str]:
        """从思考结果中解析下一个行动"""
        # 实现行动解析逻辑
        return None
        
    def _is_task_complete(self, context: str) -> bool:
        """检查任务是否完成"""
        return context is None
    
    def _get_package_root(self) -> Path:
        """获取包的根目录"""
        if getattr(sys, 'frozen', False):
            # PyInstaller 打包情况
            return Path(sys._MEIPASS)
        else:
            # 正常安装情况
            return Path(__file__).parent.parent.parent    


    async def cleanup(self) -> None:
        """资源清理"""
        self._context.clear()
        self._message_history.clear()
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.stop()