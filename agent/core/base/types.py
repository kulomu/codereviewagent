from dataclasses import dataclass
from enum import Enum
from typing import Dict, Any, Optional, List
from agent.llm.base import BaseLLM, Function

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

@dataclass
class AgentConfig:
    """Agent 配置"""
    llm: BaseLLM
    system_prompt: Optional[str] = None
    functions: Optional[List[Function]] = None
    max_steps: int = 10
    step_timeout: float = 30.0
    memory_limit: int = 1000