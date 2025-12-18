from abc import ABC, abstractmethod
from typing import Dict, Optional, AsyncGenerator, Any, List
import logging
from agent.core.base import BaseAgent, StepResult, AgentMemory
from agent.llm.base import Message, LLMRole
from dataclasses import dataclass, asdict
import logging
import json

logger = logging.getLogger(__name__)

@dataclass
class Thought:
    """思考结果"""
    content: str
    next_action: Optional[Dict] = None
    metadata: Dict[str, Any] = None
    finished: bool = False

@dataclass
class Action:
    """行动定义"""
    id: str
    name: str
    parameters: Dict[str, Any]
    description: str
    priority: int = 0

@dataclass
class ActionResult:
    """行动结果"""
    success: bool
    result: Optional[Any] = None
    error: Optional[str] = None

class ReActAgent(BaseAgent):
    """实现 ReAct 模式的 Agent"""
    
    @abstractmethod
    async def think(self, context: str | List[Message]) -> Thought:
        """思考步骤，子类必须实现"""
        pass
    
    @abstractmethod
    async def act(self, action: Action) -> ActionResult:
        """执行行动，子类必须实现"""
        pass
    
    async def step(self, context: str|List[Message]) -> AsyncGenerator[StepResult, None]:
        """实现 ReAct 模式的步骤执行，支持流式输出"""
        try:
            thought_parts = []
            # 1. 思考阶段 - 支持流式输出
            async for think_output in self.think(context):
                # 生成带格式的思考文本
                if think_output.content:
                    # 累积思考内容
                    thought_parts.append(think_output.content)
                
                # 如果思考完成
                if think_output.finished:
                    # 记录完整思考结果
                    self.memory.remember(
                        content=f"{''.join(thought_parts)}",
                        type="thought",
                        metadata={"step": self.executor._step_count}
                    )
                    
                    yield StepResult(
                        output=think_output.content,  # 添加换行
                        next_input=None,
                        is_finished=True,
                        final_answer=None,
                    )
                    return
                
                # 如果有下一步行动
                if think_output.next_action:   
                    # 1. 记录完整思考结果
                    thought_content = ''.join(thought_parts)          
                    # 2. 行动阶段
                    action = self._build_action(think_output.next_action)
                    result = await self.act(action)
                    
                    # 记录行动
                    self.memory.remember(
                        content={
                            "thought": thought_content,
                            "action": action,
                            "result": result
                        },
                        type="action",
                        metadata={"step": self.executor._step_count}
                    )
                    
                    # 3. 生成观察
                    action_text = f"\n[行动] {action.name}\n"
                    messages = self._build_messages()
                    # 生成行动和观察结果
                    yield StepResult(
                        output=action_text,
                        next_input= messages,
                        is_finished=False,
                    )
                    return
                
                # 实时产出思考内容
                yield StepResult(
                    output=think_output.content,
                    next_input=None,
                    is_finished=False,
                    final_answer=None,
                )
                    
        except Exception as e:
            logger.error(f"步骤执行失败: {str(e)}")
            raise

    def _get_current_task_history(self) -> List[Dict]:
        """获取当前任务的所有历史记录"""
        stepLen = self.executor._step_count + 1
        return self.memory.recall(limit=stepLen)
    
    def _build_action(self, action: dict) -> Action:
        """构建行动对象"""
        return Action(
            id=action.get("id", ""),
            name=action.get("name", ""),
            parameters=action.get("input", {}),
            description=action.get("description", "") or action.get("name", ""),
        )
    
    def _build_messages(self) -> List[Message]:
         # 获取当前任务的所有历史记录
        task_history = self._get_current_task_history()
        messages = []
        for memory in task_history:
            if memory.type == "user":
                messages.append(Message(role=LLMRole.USER, content=memory.content))
            elif memory.type == "thought":
                messages.append(Message(role=LLMRole.ASSISTANT, content=memory.content))
            elif memory.type == "action":
                action_data = memory.content
                action = action_data["action"]
                result = action_data["result"]
                messages.append(Message(
                    role=LLMRole.ASSISTANT,
                    content=None,
                    function_call=json.dumps(asdict(action)),
                ))
                messages.append(Message(
                    role=LLMRole.USER,
                    content=json.dumps(asdict(result)),
                    function_call_id=action.id
                ))
        return messages        

    def _format_result(self, result: ActionResult) -> str:
        """格式化行动结果"""
        if result.success:
            return str(result.result)
        return f"错误: {result.error}"