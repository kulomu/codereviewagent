import time
from typing import List, Optional, Dict, Any
from .types import AgentMemory

class MemoryManager:
    """记忆管理器"""
    def __init__(self, memory_limit: int = 1000):
        self.memory_limit = memory_limit
        self._memory: List[AgentMemory] = []
    
    def remember(self, content: Any, type: str = "default", metadata: Dict[str, Any] = None) -> str:
        """记住信息"""
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
            
    def clear(self) -> None:
        """清空记忆"""
        self._memory.clear()