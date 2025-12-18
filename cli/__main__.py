import asyncio
import typer
import os
from pathlib import Path
from typing import Optional
from plugin.manager import PluginManager
from plugin.registry import PluginRegistry
from prompt_toolkit.styles import Style

# 创建应用实例
app = typer.Typer(
    name="aicr",
    help="AI 助手 - 企业级智能工具",
    add_completion=True,
    no_args_is_help=True,
)

# 创建插件管理器
plugin_manager = PluginManager()

def run_async(coro):
    """包装异步函数为同步执行"""
    try:
        asyncio.run(coro)
    except KeyboardInterrupt:
        print("\n[系统] 程序被用户中断")
    except Exception as e:
        print(f"[错误] {str(e)}")

async def initialize():
    """初始化系统"""
    try:
        # 获取项目根目录
        root_dir = Path(__file__).parent.parent
        plugins_dir = root_dir / "plugins"
        
        if not plugins_dir.exists():
            raise RuntimeError(f"插件目录不存在: {plugins_dir}")
            
        # 发现并加载插件
        PluginRegistry.discover_plugins(
            package_path="plugins",
            plugins_dir=str(plugins_dir)
        )
        
        plugin_manager.load_all()
        await plugin_manager.initialize_all()
        
        
        # 注册插件命令
        for plugin in plugin_manager.get_plugins():
            for command in plugin.commands:
                if isinstance(command, typer.Typer):
                    app.add_typer(command, name=plugin.name)
                    
    except Exception as e:
        print(f"[系统] 初始化失败: {str(e)}")
        raise

@app.callback()
def callback():
    """AICR AI 助手 - 让开发更智能"""
    pass

@app.command()
def version():
    """显示版本信息"""
    print("AICR AI 助手 v0.1.0")

@app.command()
def plugins():
    """列出已安装的插件"""
    print("\n已安装的插件:")
    for plugin in plugin_manager.get_plugins():
        print(f"- {plugin.name}: {plugin.description}")

def main():
    """CLI 入口函数"""
    # 初始化系统
    run_async(initialize())
    
    # 启动 CLI
    app()

if __name__ == "__main__":
    main()