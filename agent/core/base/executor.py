import asyncio
import logging
from typing import AsyncGenerator
from .types import AgentState, StepResult

logger = logging.getLogger(__name__)

class AgentExecutor:
    """Agent 执行器"""
    def __init__(self, max_steps: int = 10, step_timeout: float = 30.0):
        self.max_steps = max_steps
        self.step_timeout = step_timeout
        self._step_count = 0
        self._state = AgentState.READY

    async def execute(
        self, 
        step_func, 
        context: str
    ) -> AsyncGenerator[str, None]:
        """执行任务流程"""
        if self._state != AgentState.RUNNING:
            if self._state == AgentState.READY:
                self._state = AgentState.RUNNING
            else:
                raise RuntimeError(f"Agent 状态错误: {self._state}")

        try:
            # 重置步骤计数
            self._step_count = 0
            while self._step_count < self.max_steps:
                self._step_count += 1
                
                async with asyncio.timeout(self.step_timeout):
                    async for result in step_func(context):
                        # 校验结果类型
                        if not isinstance(result, StepResult):
                            logger.error(f"步骤返回结果类型错误: {type(result)}")
                            raise TypeError(f"步骤必须返回 StepResult 类型，而不是 {type(result)}")
                        # 校验必要字段
                        if result.output is None:
                            logger.error("步骤返回结果缺少 output 字段")
                            raise ValueError("步骤返回结果必须包含 output 字段")
                    
                        yield result.output
                        
                        if result.is_finished:
                            if result.final_answer:
                                yield f"\n=== 任务完成 ===\n{result.final_answer}\n"
                            self._step_count = 0    
                            return

                        if result.next_input is not None:                      
                            context = result.next_input

            if self._step_count >= self.max_steps:
                yield self._get_max_steps_error()
                self._step_count = 0
                
        except Exception as e:
            self._state = AgentState.ERROR
            logger.error(f"执行失败: {str(e)}")
            raise

    def _get_max_steps_error(self) -> str:
        """获取超出最大步骤限制的错误信息"""
        return (
            f"\n[错误] 任务执行步骤超过最大限制 ({self.max_steps} 步)，建议:\n"
            "1. 尝试将问题拆分为更小的部分\n"
            "2. 使用更明确的指令\n"
            "3. 如果确实需要更多步骤，可以调整 max_steps 参数\n"
        )