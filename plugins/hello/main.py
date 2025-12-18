from plugin.base import CLIPlugin
from plugin.decorators import register_plugin
import typer
from typing import List, Union, Callable


@register_plugin
class HelloPlugin(CLIPlugin):
    @property
    def name(self) -> str:
        return "hello"
    
    @property
    def description(self) -> str:
        return "示例插件"
    
    @property
    def commands(self) -> List[Union[typer.Typer, Callable]]:
        app = typer.Typer(
            name=self.name,
            help=self.description,
            invoke_without_command=True
        )

        @app.callback()
        def default(ctx: typer.Context, name: str = typer.Argument("world")):
            """打招呼命令
            
            Args:
                name: 打招呼的对象名称
            """
            if ctx.invoked_subcommand is None:
                print(f"Hello {name}!")
        
        @app.command()
        def bye(name: str = typer.Option("world", "--name", "-n")):
            """告别命令
            
            Args:
                name: 告别的对象名称
            """
            print(f"Goodbye {name}!")
            
        return [app]
