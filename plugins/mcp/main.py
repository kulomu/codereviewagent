from plugin.base import CLIPlugin
from plugin.decorators import register_plugin
import typer
from typing import List, Union, Callable
from typing_extensions import Annotated
from agent.mcpHub.installer import MCPInstaller
from rich.table import Table
from rich.console import Console
from pathlib import Path
import asyncio
import traceback

console = Console()

@register_plugin
class MCPPlugin(CLIPlugin):
    def __init__(self):
        super().__init__()
        config_path = Path(__file__).resolve().parents[2] / "configs" / "mcp_config.json"
        self.installer = MCPInstaller(config_path=str(config_path))

    async def initialize(self):
        # 初始化時自動安裝 code_review（若尚未安裝）
        code_review_installed = "code_review" in self.installer._config
        if not code_review_installed:
            console.print("[yellow]正在自動安裝 code_review...[/yellow]")
            try:
                path = Path(__file__).resolve().parents[2] / "mcp_servers"
                await self.installer.install_mcp("code_review", str(path))
                console.print("[green]已完成 code_review 的安裝。[/green]")
            except Exception as e:
                console.print(f"[red]自動安裝 code_review 失敗: {str(e)}[/red]")

    @property
    def name(self) -> str:
        return "mcp"
    
    @property
    def description(self) -> str:
        return "MCP server 安裝器"

    @property
    def app(self) -> typer.Typer:
        app = typer.Typer(
            name=self.name,
            help=self.description,
            no_args_is_help=True,
        )

        @app.command("ls")
        def list_mcps(
            remote: Annotated[bool, typer.Option("--remote", "-r", help="查看遠端可用的 MCP")] = False
        ):
            """查看可用的 MCP 列表"""
            async def _list():
                table = Table(show_header=True)

                if remote:
                    table.add_column("名稱")
                    table.add_column("狀態")

                    # 取得遠端 MCP 列表
                    mcps = await self.installer.list_remote_mcps()
                    # 取得本地安裝狀態
                    status = await self.installer.compare_mcps()

                    # 比對後展示
                    for mcp in mcps:
                        table.add_row(
                            getattr(mcp, "name", "-"),
                            "已安裝" if status.get(mcp.name) == "installed" else "未安裝"
                        )
                else:
                    table.add_column("名稱")
                    table.add_column("安裝路徑")

                    local_mcps = await self.installer.get_local_mcps()
                    for name in local_mcps:
                        config = self.installer._config.get(name, {})
                        table.add_row(
                            name,
                            config.get("install_path", "未知")
                        )

                console.print(table)

            asyncio.run(_list())

        @app.command("install")
        def install_mcp(
            name: Annotated[str, typer.Argument(help="要安裝的 MCP 名稱")]
        ):
            """安裝指定的 MCP"""
            async def _install():
                path = Path(__file__).resolve().parents[2] / "mcp_servers"
                with console.status(f"正在安裝 {name}..."):
                    try:
                        await self.installer.install_mcp(name, str(path))
                        console.print(f"[green]成功安裝 {name} 到 {path}[/green]")
                    except Exception as e:
                        console.print(f"[red]安裝失敗: {str(e)}[/red]")
                        console.print(traceback.format_exc())

            asyncio.run(_install())

        @app.command("uninstall")
        def uninstall_mcp(
            name: Annotated[str, typer.Argument(help="要卸載的 MCP 名稱")]
        ):
            """卸載指定的 MCP"""
            async def _uninstall():
                try:
                    config = self.installer._config.get(name)
                    if not config:
                        console.print(f"[red]未找到 MCP: {name}[/red]")
                        return

                    self.installer._config.pop(name)
                    self.installer._save_config()

                    install_path = Path(config["install_path"])
                    if install_path.exists():
                        import shutil
                        shutil.rmtree(install_path)

                    console.print(f"[green]成功卸載 {name}[/green]")

                except Exception as e:
                    console.print(f"[red]卸載失敗: {str(e)}[/red]")
                    console.print(traceback.format_exc())

            asyncio.run(_uninstall())

        return app

    @property
    def commands(self) -> List[Union[typer.Typer, Callable]]:
        return [self.app]
