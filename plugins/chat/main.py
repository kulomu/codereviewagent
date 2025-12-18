from plugin.base import CLIPlugin
from plugin.decorators import register_plugin
from agent.core.mcp import MCPToolAgent, mcpClient
from agent.core.base import AgentConfig
from agent.llm.providers.bedrock import BedrockProvider, BedrockConfig
from share.util import AsyncLoader

import typer
from typing import List, Union, Callable
from typing_extensions import Annotated
from rich.prompt import Prompt
from rich.panel import Panel
from rich.console import Console
from rich.markdown import Markdown
import asyncio
import logging

logger = logging.getLogger(__name__)
console = Console()
print = console.print


@register_plugin
class ChatPlugin(CLIPlugin):
    """交互式对话插件"""
    
    def __init__(self):
        super().__init__()
        self.agent = None
        self._history = []
    
    @property
    def name(self) -> str:
        return "chat"
    
    @property
    def description(self) -> str:
        return "与 AI 助手进行交互式对话"
    
    async def initialize_agent(self):
        """初始化 Agent"""
        try:
            # 配置 LLM
            llm = BedrockProvider(BedrockConfig(stream=True))
            agent_config = AgentConfig(llm=llm)
            
            # 创建 Agent
            self.agent = MCPToolAgent(
                config=agent_config
            )
            await self.agent.initialize()
            return True
        except Exception as e:
            print(f"[red]初始化失败: {str(e)}[/red]")
            return False

    async def safe_cleanup(self):
        """安全清理资源"""
        try:
            if self.agent:
                await self.agent.cleanup()
                self.agent = None
        except Exception as e:
            logger.error(f"清理资源时出错: {str(e)}")

    async def process_chat(self, query: str, debug: bool = False):
        loader = AsyncLoader("思考中")  # 创建加载器实例
        first_response = True  # 添加首次响应标记
        response_text = ""

        """处理单次对话"""
       
        try:
            if first_response:
                await loader.start()
            async for chunk in self.agent.run(query):
                if debug:
                    print(f"\n[dim]Debug: Got chunk: {chunk}[/dim]")
                # 第一个响应块到达时清除加载状态
                if first_response:
                    loader.clear_line()
                    await loader.stop()
                    print("\r[bold blue]>>: [/bold blue]", end="")
                    first_response = False

                response_text += chunk
                print(chunk, end="")
                
            if response_text:
                self._history.append(("assistant", response_text))
                
        except Exception as e:
            print(f"\n[red]执行出错: {str(e)}[/red]")
            if debug:
                logger.exception("执行详细错误")
        finally:
            # 确保加载动画被停止
            if first_response:  # 如果还没有收到任何响应
                await loader.stop()

    @property
    def commands(self) -> List[Union[typer.Typer, Callable]]:
        app = typer.Typer(
            name=self.name,
            help=self.description,
            invoke_without_command=True
        )
        
        @app.callback()
        def default(
            ctx: typer.Context,
            debug: Annotated[bool, typer.Option("--debug", "-d", help="显示调试信息")] = False,
        ):
            """启动交互式对话"""
            async def _chat_session():
                try:
                    # 初始化 Agent
                    if not self.agent and not await self.initialize_agent():
                        return

                    # 显示欢迎信息
                    print(Panel(
                        "[bold blue]AI 助手已准备就绪[/bold blue]\n"
                        "- 输入问题开始对话\n"
                        "- 输入 'clear' 清除历史记录\n"
                        "- 输入 'exit' 或 'quit' 退出\n"
                        "- 按 Ctrl+C 随时中断当前操作",
                        title="欢迎使用",
                        border_style="blue"
                    ))
                    
                    # 开始对话循环
                    while True:
                        try:
                            query = Prompt.ask("\n[bold green]>>[/bold green]")
                            
                            if query.lower() in ['exit', 'quit']:
                                break
                            elif query.lower() == 'clear':
                                self._history.clear()
                                console.clear()
                                continue
                            elif not query.strip():
                                continue
                            
                            self._history.append(("user", query))
                            await self.process_chat(query, debug)
                                        
                        except KeyboardInterrupt:
                            print("\n[yellow]已中断当前操作, 如果需要退出请输入 'exit' 或 'quit'[/yellow]")
                            continue
                            
                except Exception as e:
                    print(f"\n[red]发生错误: {str(e)}[/red]")
                    if debug:
                        logger.exception("Chat 会话错误")
                finally:
                    await self.safe_cleanup()
                    print("\n[blue]对话已结束，欢迎下次使用！[/blue]")
            
            # 运行对话会话
            asyncio.run(_chat_session())
            
        return [app]