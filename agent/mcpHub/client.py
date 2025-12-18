import asyncio
from typing import Optional, List, Dict
from dataclasses import dataclass, field
from contextlib import AsyncExitStack

from mcp import ( ClientSession, StdioServerParameters, stdio_client)

@dataclass
class Server:
    id: str
    params: StdioServerParameters

@dataclass
class McpConnection:
    server: Server
    transport: stdio_client
    session: Optional[ClientSession] = None
    exit_stack: AsyncExitStack = field(default_factory=AsyncExitStack)


class MCPClient:
    def __init__(self):
        self.connections: List[McpConnection] = []
        
    async def connect_stdio(self, server_id: str, server_params: StdioServerParameters) -> McpConnection:
        """连接到标准输入输出服务器"""
        connection = None
        try:
            server = Server(
                id=server_id,
                params=server_params
            )
            connection = McpConnection(server, transport=None)

            transport = await connection.exit_stack.enter_async_context(stdio_client(
                server_params
            ))
            connection.transport = transport
            
            self.connections.append(connection)
            return connection
        except Exception as e:
            if connection:
                await connection.exit_stack.aclose()
            raise Exception(f"Failed to connect to stdio server: {str(e)}")
  
    def get_connection(self, server_id: str) -> Optional[McpConnection]:
        """获取指定服务器的连接"""
        for conn in self.connections:
            if conn.server.id == server_id:
                return conn
        return None

    async def create_session(self, server_id: str) -> ClientSession:
        """创建新的会话"""
        conn = self.get_connection(server_id)
        if not conn:
            raise Exception(f"No connection found for server {server_id}")
        read, write = conn.transport    
        session = await conn.exit_stack.enter_async_context(ClientSession(read, write))
        conn.session = session
        await session.initialize()
        return session
    
    async def get_or_create_session(self, server_id: str) -> ClientSession:
        """获取现有会话或创建新会话"""
        conn = self.get_connection(server_id)
        if not conn:
            raise Exception(f"No connection found for server {server_id}")
            
        if conn.session and not conn.session.closed:
            return conn.session
            
        return await self.create_session(server_id)

    async def disconnect(self, server_id: str):
        """断开指定服务器的连接,同时关闭会话"""
        conn = self.get_connection(server_id)
        if conn:
            self.connections.remove(conn)
            await conn.exit_stack.aclose()

    async def disconnect_all(self):
        """断开所有服务器连接并关闭所有会话"""
        for conn in self.connections[:]:
            self.connections.remove(conn)
            await conn.exit_stack.aclose()