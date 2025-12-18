from typing import Dict, List, Optional, Any, AsyncGenerator, Union
from dataclasses import dataclass
from .toolCall import ToolCallAgent, Tool
from agent.mcpHub.client import MCPClient
from mcp import ClientSession, StdioServerParameters, Tool as MCPTool
import logging
import json
from pathlib import Path
import sys
import os
import shutil
from string import Template
from mcp.types import (
    EmbeddedResource,
    GetPromptResult,
    ImageContent,
    PromptMessage,
    Role,
    TextContent,
    TextResourceContents
)

logger = logging.getLogger(__name__)

@dataclass
class ServerConfig:
    """服务器配置"""
    id: str              # 服务器ID
    command: str         # 命令
    args: List[str]      # 参数列表

@dataclass
class MCPToolWrapper:
    """MCP 工具包装器"""
    name: str
    description: str
    session: ClientSession
    tool: MCPTool

mcpClient = MCPClient()

class MCPToolAgent(ToolCallAgent):
    """集成 MCP 功能的 Tool Agent"""
    
    def __init__(
        self,
        *args,
        mcp_client: Optional[MCPClient] = None,
        config_path: Optional[str] = None,
        **kwargs
    ):
        self.mcp_client = mcp_client or mcpClient # 使用默认的 MCPClient 实例
        self.config_path = config_path or str(self._get_package_root() / "configs" / "mcp_config.json")
        self._sessions: Dict[str, ClientSession] = {}
        self._mcp_tools: Dict[str, MCPToolWrapper] = {}
        
        # 初始化父类
        super().__init__(*args, **kwargs)
    async def initialize(self) -> None:
        """初始化 Agent"""
        try:
            # 1. 加载服务器配置
            configs = self._load_server_configs()

            # 2. 连接所有服务器
            for config in configs:
                try:
                    executable_command = self._check_command_executable(config.command)
                    args = [self._replace_env_vars(arg) for arg in config.args]

                    # 构建连接参数
                    params = StdioServerParameters(
                        command=executable_command,
                        args= args,
                        env=os.environ,  # 使用当前环境变量 
                    )
                    
                    # 连接服务器
                    conn = await self.mcp_client.connect_stdio(config.id, params)
                    if not conn:
                        logger.error(f"连接服务器失败: {config.id}")
                        continue
                    
                    # 创建会话
                    session = await self.mcp_client.create_session(conn.server.id)
                    self._sessions[config.id] = session
                    # 加载工具
                    await self._load_tools()
                    
                except Exception as e:
                    logger.error(f"处理服务器 {config.id} 时出错: {str(e)}")
            
            # 3. 创建工具
            tools = self._create_agent_tools()
            self.tools.update({tool.name: tool for tool in tools})

            # 4. 调用父类初始化
            await super().initialize()
            
        except Exception as e:
            logger.error(f"mcp初始化失败: {str(e)}")
            raise
    
    def get_session(self, server_id: Optional[str] = None) -> Optional[ClientSession]:
        """获取指定服务器的会话
        
        Args:
            server_id: 服务器ID。如果为 None，返回第一个可用的会话
            
        Returns:
            ClientSession: 会话对象，如果未找到返回 None
        """
        try:
            if not self._sessions:
                return None
                
            if server_id is None:
                # 返回第一个可用的会话
                return next(iter(self._sessions.values()))
            
            return self._sessions.get(server_id)
            
        except Exception as e:
            logger.error(f"获取会话失败: {str(e)}")
            return None
            
    async def get_active_sessions(self) -> Dict[str, ClientSession]:
        """获取所有活动的会话
        
        Returns:
            Dict[str, ClientSession]: 服务器ID到会话的映射
        """
        try:
            # 过滤出活动的会话
            active_sessions = {}
            for server_id, session in self._sessions.items():
                try:
                    # 简单检查会话是否可用
                    if session and not session.closed:
                        active_sessions[server_id] = session
                except Exception:
                    continue
                    
            return active_sessions
            
        except Exception as e:
            logger.error(f"获取活动会话列表失败: {str(e)}")
            return {}

    def _load_server_configs(self) -> List[ServerConfig]:
        """从配置文件加载服务器配置"""
        try:
            with open(self.config_path, 'r') as f:
                config_data = json.load(f)
                
            configs = []
            for server_id, server_config in config_data.items():
                configs.append(ServerConfig(
                    id=server_id,
                    command=server_config["command"],
                    args=server_config.get("args", [])
                ))
            return configs
            
        except Exception as e:
            return []
    
    def _get_package_root(self) -> Path:
        """获取包的根目录"""
        if getattr(sys, 'frozen', False):
            return Path(sys._MEIPASS)
        return Path(__file__).parent.parent.parent           
    
    def _replace_env_vars(self, path_str: str) -> str:
            """替换路径中的环境变量"""
            # 添加 ROOT_PATH 到环境变量
            env_vars = {
                "AICR_ROOT_PATH": str(self._get_package_root()),
                **os.environ  # 包含系统环境变量
            }
            
            # 使用 Template 替换变量
            return Template(path_str).safe_substitute(env_vars)    
     
    async def _load_tools(self) -> None:
        """加载所有工具"""
        for server_id, session in self._sessions.items():
            try:
                # 加载工具
                tools_response = await session.list_tools()
                for tool in tools_response.tools:
                    self._mcp_tools[tool.name] = MCPToolWrapper(
                        name=tool.name,
                        description=tool.description,
                        session=session,
                        tool=tool
                    )

            except Exception as e:
                logger.error(f"加载服务器 {server_id} 的工具 时出错: {str(e)}")
    
    def _create_agent_tools(self) -> List[Tool]:
        """创建 Agent 工具列表"""
        tools = []
        
        # 添加 MCP 工具
        for wrapper in self._mcp_tools.values():
            tool = Tool(
                name=f"{wrapper.name}",
                description=wrapper.description,
                parameters=wrapper.tool.inputSchema.get('properties', {}),
                func=self._create_tool_caller(wrapper)
            )
            if self._validate_tool(tool):
                tools.append(tool)
            
        return tools
    
    def _create_tool_caller(self, wrapper: MCPToolWrapper):
        """创建工具调用函数"""
        async def call_tool(**params):
            try:
                result = await wrapper.session.call_tool(
                    wrapper.name,
                    params
                )
                return self._get_text(result.content[0])
            except Exception as e:
                raise Exception(f"调用工具 {wrapper.name} 失败: {str(e)}")
        return call_tool
    
    def _get_text(self, content: Union[TextContent, ImageContent, EmbeddedResource]) -> Optional[str]:
        """
        Extract text content from a content object if available.

        Args:
            content: A content object (TextContent, ImageContent, or EmbeddedResource)

        Returns:
            The text content as a string or None if not a text content
        """
        # print(f"get_text: {content}")
        if isinstance(content, TextContent):
            return self._get_text(content.text)

        if isinstance(content, TextResourceContents):
            return self._get_text(content.text)

        if isinstance(content, EmbeddedResource):
            if isinstance(content.resource, TextResourceContents):
                return self._get_text(content.resource.text)

        if isinstance(content, str):
            return content    

        return None
    
    def _check_command_executable(self, command: str) -> str:
        """检查命令是否可执行，如果不可执行则尝试在 PATH 中查找"""
        try:
            # 如果是完整路径，直接检查是否可执行
            cmd_path = Path(command)
            if cmd_path.is_file() and os.access(cmd_path, os.X_OK):
                return str(cmd_path)
            
            # 在 PATH 中查找可执行文件
            cmd = shutil.which(command)
            if cmd:
                return cmd
                
            # 如果是 Python 脚本，使用当前 Python 解释器执行
            if command.endswith('.py'):
                return sys.executable
                
            raise FileNotFoundError(f"命令不存在或不可执行: {command}")
            
        except Exception as e:
            logger.warning(f"命令检查失败: {str(e)}")
            # 如果找不到命令，使用默认的 Python 解释器
            return sys.executable
        
    async def cleanup(self) -> None:
        """资源清理"""
        try:
            if self._sessions:
                await self.mcp_client.disconnect_all()
            self._sessions.clear()
            self._mcp_tools.clear()
        finally:
            await super().cleanup()