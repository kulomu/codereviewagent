from typing import Dict, List, Optional, Any, AsyncGenerator
from dataclasses import dataclass
from .react import ReActAgent, Thought, Action, ActionResult
from agent.llm.base import Function, Message, LLMRole
import json
import logging
import xml.etree.ElementTree as ET
from pathlib import Path
import sys

logger = logging.getLogger(__name__)

@dataclass
class Tool:
    """工具定义"""
    name: str                    # 工具名称
    description: str             # 工具描述
    parameters: Dict[str, Any]   # 工具参数定义
    func: callable              # 实际执行的函数

class ToolCallAgent(ReActAgent):
    """工具调用 Agent"""
    DEFAULT_SYSTEM_PROMPT = """你是一个专业的工具调用助手。请按照以下步骤工作：

1. 理解用户需求
2. 选择合适的工具
3. 使用正确的参数调用工具
4. 解释执行结果

可用工具列表:
{{tools}}

注意事项：
- 优先使用工具解决问题
- 确保参数格式正确
- 清晰解释每个步骤
"""
    
    def __init__(self, *args, tools: Optional[List[Tool]] = None, **kwargs):
        super().__init__(*args, **kwargs)
        valid_tools = []
        if tools:
            for tool in tools: 
                if self._validate_tool(tool):
                    valid_tools.append(tool)
        self.tools = {tool.name: tool for tool in valid_tools}
    

    async def initialize(self) -> None:
        if not self.config.system_prompt:
            self.config.system_prompt = await self.load_system_prompt()

            # 准备工具描述
            tools_desc = self._format_tools_description()
            self.config.system_prompt = self.config.system_prompt.replace("{{tools}}", tools_desc)
    
    async def think(self, context: str | List[Message] ) -> AsyncGenerator[Thought, None]:
        """基于上下文思考下一步行动"""
        # 使用 LLM 分析上下文
        # print('system====>', self.system_prompt)
        try:
            async for response in self.config.llm.generate(
                prompt = context if isinstance(context, str) else None,
                messages = context if isinstance(context, list) else None,
                system=self.config.system_prompt, 
                functions=self.tools.values(),
                ):
                # 如果是工具调用
                if response.stop_reason == 'tool_use' and response.tool_call:
                    tool_call = self._format_next_action(response.tool_call)  # 获取工具调用
                    yield Thought(
                        content=response.text,
                        next_action=tool_call,
                    )
                
                # 如果是最终答案
                if response.stop_reason == 'end_turn':
                    yield Thought(
                        content=response.text,
                        finished=True
                    )
                
                # 其他情况
                yield Thought(content=response.text)
        except Exception as e:
            logger.error(f"思考过程出错: {str(e)}")
            yield Thought(
                content=f"思考过程出错: {str(e)}",
                finished=True
            )
    
    async def act(self, action: Action) -> ActionResult:
        """执行工具调用"""
        try:
            # 解析工具调用信息
            tool_name = action.name
            parameters = action.parameters or {}
            # 获取工具
            if tool_name not in self.tools:
                return ActionResult(
                    success=False,
                    error=f"未知工具: {tool_name}"
                )
                
            tool = self.tools[tool_name]
            
            # 执行工具调用
            result = await tool.func(**parameters)
            return ActionResult(success=True, result=result)
            
        except Exception as e:
            return ActionResult(
                success=False,
                error=f"工具调用失败: {str(e)}"
            )
    
    async def load_system_prompt(self) -> str:
        """加载系统提示词模板"""
        try:
            # 1. 尝试从默认位置加载
            default_path = self._get_package_root() / "agent" / "prompts" / "system_prompt.xml"
            if default_path.exists():
                content = None
                with open(default_path) as f:
                    content = f.read().strip()  
                if content:
                    return content

            # 2. 使用默认提示词
            return self.DEFAULT_SYSTEM_PROMPT

        except Exception as e:
            logger.error(f"加载系统提示词失败: {str(e)}")
            return self.DEFAULT_SYSTEM_PROMPT
    
    def _get_package_root(self) -> Path:
        """获取包的根目录"""
        if getattr(sys, 'frozen', False):
            return Path(sys._MEIPASS)
        return Path(__file__).parent.parent.parent

    def _validate_tool(self, tool: Tool) -> bool:
        """
        校验工具的可用性
        检查工具参数是否包含 $ref 引用类型
        返回 True 表示工具可用，False 表示不可用
        """
        try:
            # 检查工具参数
            if not tool.parameters:
                return True
                
            # 递归检查参数中是否包含 $ref
            def check_ref_in_params(params: dict) -> bool:
                for key, value in params.items():
                    # 检查字典类型的值
                    if isinstance(value, dict):
                        # 如果包含 $ref 键，工具不可用
                        if '$ref' in value:
                            print(f"工具 {tool.name} 包含不支持的引用类型参数: {key}")
                            return False
                        # 递归检查嵌套字典
                        if not check_ref_in_params(value):
                            return False
                    # 检查列表类型的值
                    elif isinstance(value, list):
                        for item in value:
                            if isinstance(item, dict) and not check_ref_in_params(item):
                                return False
                return True
                
            return check_ref_in_params(tool.parameters)
            
        except Exception as e:
            logger.error(f"校验工具 {tool.name} 失败: {str(e)}")
            return False

    def _format_next_action(self, tool_call: Dict) -> Action:
        """格式化下一步行动"""
        tool_id = tool_call.get("toolUseId")
        tool_name = tool_call.get("name")
        parameters = tool_call.get("parameters", {})
        
        if tool_name not in self.tools:
            return None
        
        tool = self.tools[tool_name]
        
        return {
            "id": tool_id,
            "name": tool.name,
            "description": tool.description,
            "parameters": parameters
        }
    
    def _format_tools_description(self) -> str:
        """格式化工具描述"""
        descriptions = []
        if not self.tools:
            return "当前没有可用的工具。请联系管理员添加工具。"
        for tool in self.tools.values():
            params_desc = json.dumps(tool.parameters, indent=2, ensure_ascii=False)
            descriptions.append(f"""
工具名称: {tool.name}
描述: {tool.description}
参数:
{params_desc}
""")
        return "\n".join(descriptions)
    
    def _parse_tool_call(self, thought: str) -> Optional[Dict]:
        """从思考结果中解析工具调用"""
        try:
            if "行动:" not in thought:
                return None
                
            action_line = thought.split("行动:")[1].split("\n")[0].strip()
            if "(" not in action_line or ")" not in action_line:
                return None
                
            tool_name = action_line[:action_line.find("(")]
            params_str = action_line[action_line.find("(")+1:action_line.find(")")]
            
            # 解析参数
            params = {}
            if params_str:
                for param in params_str.split(","):
                    key, value = param.split("=")
                    params[key.strip()] = eval(value.strip())
                    
            return {
                "name": tool_name,
                "parameters": params
            }
            
        except Exception as e:
            logger.error(f"解析工具调用失败: {str(e)}")
            return None