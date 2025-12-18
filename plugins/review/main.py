from plugin.base import CLIPlugin
from plugin.decorators import register_plugin
from agent.core.base import AgentConfig
from agent.llm.providers.bedrock import BedrockProvider, BedrockConfig
from share.util import AsyncLoader
from agent.custom.reviewer import Reviewer, MergeRequestInfo

import typer
from typing import List, Union, Callable
from typing_extensions import Annotated
from rich.prompt import Prompt
from rich.panel import Panel
from rich.console import Console
from rich.markdown import Markdown
import asyncio
import logging
import os


logger = logging.getLogger(__name__)
console = Console()
print = console.print

@register_plugin
class ReviewPlugin(CLIPlugin):
    @property
    def name(self) -> str:
        return "review"
    
    @property
    def description(self) -> str:
        return "代码review插件，提供代码审查和质量检查功能"
    

    def __init__(self):
        super().__init__()
        self.reviewer=None 
 
    async def initialize_reviewer(self) -> bool:
        """初始化插件"""
        try:
            # 配置 LLM
            llm = BedrockProvider(BedrockConfig(stream=True))
            agent_config = AgentConfig(llm=llm)
            
            # 创建 Agent
            self.reviewer = Reviewer(
                config=agent_config,
            )
            await self.reviewer.initialize()
        
            return True
        except Exception as e:
            logger.error(f"插件初始化失败: {str(e)}")
            return False

    async def cleanup(self):
        """清理资源"""
        try:
            if self.reviewer:
                await self.reviewer.cleanup()
                self.reviewer = None
        except Exception as e:
            logger.error(f"清理资源失败: {str(e)}")    
    
    @property
    def commands(self) -> List[Union[typer.Typer, Callable]]:
        app = typer.Typer(
            name=self.name,
            help=self.description,
            invoke_without_command=True
        )

        @app.callback()
        def default(ctx: typer.Context, 
                    ci: Annotated[bool, typer.Option("--ci", "-c", help="是否在 CI 环境下运行")] = False,
                    debug: Annotated[bool, typer.Option("--debug", "-d", help="显示调试信息")] = False,
                    group: Annotated[str, typer.Option("--group", "-g", help="各端标志")] = 'web'
                    ):
            """本地代码审查命令"""
            async def _review_session():
                try:
                    # 初始化 Agent
                    if not self.reviewer:
                        if not await self.initialize_reviewer():
                            return
                    if ci:
                        project_id = os.getenv('CI_PROJECT_ID')
                        project_url = os.getenv('CI_PROJECT_URL')
                        mr_iid = os.getenv('CI_MERGE_REQUEST_IID')
                        commit_sha = os.getenv('CI_COMMIT_SHA')
                        
                        if not all([project_id, mr_iid]):
                            print("错误: 缺少必要的 CI 环境变量")
                            return
                        
                        mr_info = MergeRequestInfo(
                            project_id=project_id,
                            project_url=project_url,
                            merge_request_iid=int(mr_iid),
                            commit_sha=commit_sha,
                            diff_refs={}
                        )  
                        try:
                            # 运行审查流程
                            async for result in self.reviewer.ci_run(mr_info, group):
                                if result == "Done":
                                    continue
                                print(result, end="")
                            
                        except Exception as e:
                            print(f"\n[red]审查过程出错: {str(e)}[/red]")
                            if debug:
                                logger.exception("审查详细错误")
                            return
                    else:
                        # 显示开始信息
                        print(Panel.fit("[bold blue]开始代码审查...[/bold blue]"))
                        
                        try:
                            # 运行审查流程
                            async for result in self.reviewer.run(group):
                                if result == "Done":
                                    continue
                                print(result, end="")
                            
                        except Exception as e:
                            print(f"\n[red]审查过程出错: {str(e)}[/red]")
                            if debug:
                                logger.exception("审查详细错误")
                            return
                        
                except Exception as e:
                    print(f"[red]执行出错: {str(e)}[/red]")
                finally:
                    await self.cleanup()
        
            # 运行异步审查会话
            asyncio.run(_review_session())

        return [app]
