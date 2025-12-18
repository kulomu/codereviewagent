import asyncio
import itertools
from typing import List

class AsyncLoader:
    def __init__(self, desc: str = "思考中", chars: List[str] = None):
        self.desc = desc
        self.chars = chars or ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        self.delay = 0.1
        self._task = None
        self._running = False
        self._current_line_length = 0  # 当前行长度，用于清除行

    async def spinner_task(self):
        """加载动画任务"""
        try:
            while True:  # 改为无限循环，由 _running 标志控制退出
                if not self._running:
                    break
                for char in self.chars:
                    if not self._running:
                        break
                    current_line = f"[💭] {char} {self.desc}..."
                    self._current_line_length = len(current_line) + 5  # 加上颜色代码的长度
                    print(f"\r{current_line}", end="", flush=True)
                    await asyncio.sleep(self.delay)
        except asyncio.CancelledError:
            pass
        finally:
            pass 

    def clear_line(self):
        """清除当前行并将光标移到行首"""
        if self._current_line_length > 0:
            print(f"\r{' ' * self._current_line_length}\r", end="", flush=True)           

    async def start(self):
        """启动加载动画"""
        self._running = True  # 先设置状态
        if not self._task or self._task.done():
            self._task = asyncio.create_task(self.spinner_task())

    async def stop(self):
        """停止加载动画"""
        self._running = False  # 先更新状态
        if self._task and not self._task.done():
            # 等待任务完成
            await asyncio.sleep(self.delay)  # 给一个周期让动画完成
            if not self._task.done():
                self._task.cancel()
                try:
                    await self._task
                except asyncio.CancelledError:
                    pass
