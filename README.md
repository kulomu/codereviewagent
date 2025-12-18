# AICR - 企业级AI智能助手

## 项目介绍

AICR是一个功能强大的企业级AI智能助手平台，主要专注于代码审查和开发效率提升。该项目采用模块化的插件架构设计，集成了先进的大语言模型（LLM）和模型上下文协议（MCP），为开发团队提供智能化的代码质量保障和开发工具链支持。

### 核心特性

- 🤖 **智能代码审查**: 基于AI的自动代码审查，支持多种编程语言和代码规范
- 🔌 **插件化架构**: 灵活的插件系统，支持功能扩展和自定义开发
- 🌐 **MCP协议支持**: 集成模型上下文协议，实现与外部工具的无缝连接
- 💬 **对话式交互**: 直观的命令行界面，支持自然语言交互
- ☁️ **云原生设计**: 支持AWS Bedrock等云端LLM服务
- 🔧 **多工具集成**: 支持GitLab集成、批量文件处理等企业级功能

### 技术栈

- **后端框架**: Python 3.13+
- **LLM集成**: AWS Bedrock、Llama Index
- **CLI框架**: Typer、Prompt Toolkit
- **协议支持**: Model Context Protocol (MCP)
- **包管理**: UV (现代Python包管理工具)
- **异步处理**: AsyncIO
- **配置管理**: YAML、环境变量

## 环境要求

- Python 3.13+ (项目使用最新Python特性)
- UV 包管理工具
- AWS账户 (用于Bedrock LLM服务)
- Git (版本控制)

## 快速开始

### 1. 克隆仓库

```bash
git clone https://github.com/kulomu/codereviewagent.git
cd codereviewagent
```

### 2. 环境配置

创建 `.env` 文件并配置必要的环境变量：

```bash
# AWS Bedrock 配置
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_REGION=us-east-1

# GitLab 集成 (可选)
GITLAB_TOKEN=your_gitlab_token
GITLAB_BASE_URL=https://gitlab.example.com
```

### 3. 安装依赖

```bash
# 安装 UV (如果尚未安装)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 安装项目依赖
uv sync
```

### 4. 运行应用

```bash
# 开发模式运行
uv run main.py

# 或使用CLI命令
uv run python -m cli
```

### 5. 安装为全局命令

```bash
# 构建并安装
uv build
pipx install dist/*.whl

# 使用全局命令
airc --help
ty --help  # 短命令别名
```

## 使用示例

### 代码审查

```bash
# 查看可用插件
airc plugins

# 使用代码审查功能
airc review --help

# 审查当前目录的代码
airc review analyze .

# 审查特定文件
airc review file src/main.py
```

### MCP服务器管理

```bash
# 查看已安装的MCP服务器
airc mcp ls

# 安装新的MCP服务器
airc mcp install <server_name> <path>

# 卸载MCP服务器
airc mcp uninstall <server_name>
```

### 聊天交互

```bash
# 启动交互式聊天
aicr chat

# 单次对话
aicr chat --message "请帮我分析这段代码"
```

## 架构设计

### 核心模块

#### 1. Agent系统 (`agent/`)

- **BaseAgent**: Agent基类，定义统一的执行接口
- **AgentExecutor**: 执行器，负责步骤控制和超时管理
- **MemoryManager**: 记忆管理，维护对话历史和上下文
- **Types**: 核心数据类型定义

#### 2. LLM抽象层 (`llm/`)

- **BaseLLM**: LLM提供商抽象基类
- **BedrockProvider**: AWS Bedrock集成实现
- **Message/Function**: 统一的消息和函数调用接口

#### 3. 插件系统 (`plugin/`)

- **CLIPlugin**: 插件基类，定义插件接口
- **PluginManager**: 插件管理器，负责加载和生命周期管理
- **PluginRegistry**: 插件注册表，实现插件发现机制

#### 4. MCP集成 (`mcpHub/`)

- **MCPClient**: MCP协议客户端实现
- **MCPInstaller**: MCP服务器安装和管理
- **Server管理**: 服务器连接和会话管理

### 插件生态

当前已实现的插件：

- **Review Plugin**: 智能代码审查，支持多种代码质量检查
- **MCP Plugin**: MCP服务器管理，简化外部工具集成
- **Chat Plugin**: 对话式交互，支持自然语言查询
- **Hello Plugin**: 示例插件，演示插件开发模式

## 工具安装

### 必要工具

#### python and uv

1. 安装python3.9以上
2. 安装uv管理工具

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

3. 验证安装：

```bash
python3 --version
uv --version
```

## 开发指南

### 插件开发

1. **创建插件目录**

   ```bash
   mkdir plugins/your_plugin_name
   cd plugins/your_plugin_name
   ```
2. **实现插件类**

   ```python
   from plugin.base import CLIPlugin 
   from plugin.decorators import register_plugin
   import typer

   @register_plugin
   class YourPlugin(CLIPlugin):
       @property
       def name(self) -> str:
           return "your_plugin"

       @property  
       def description(self) -> str:
           return "Your plugin description"

       @property
       def commands(self):
           app = typer.Typer()

           @app.command()
           def hello():
               print("Hello from your plugin!")

           return [app]
   ```

### 贡献指南

1. Fork 项目
2. 创建功能分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'Add amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 创建 Pull Request

### 测试

```bash
# 运行测试
uv run pytest

# 代码格式检查
uv run black .
uv run isort .

# 类型检查
uv run mypy .
```

---

*AICR - 让AI助力开发，让代码更智能* 🚀

## 目录结构

```text
codereviewagent/
├── agent/                    # Agent系统
│   ├── __init__.py
│   ├── mcp.py               # MCP集成Agent
│   ├── react.py             # ReAct模式Agent
│   ├── toolCall.py          # 工具调用Agent
│   └── core/                # Agent核心组件
│       ├── __init__.py
│       ├── base.py          # Agent基类
│       ├── executor.py      # 执行器
│       ├── memory.py        # 记忆管理
│       └── types.py         # 类型定义
├── cli/                     # 命令行界面
│   └── __main__.py          # CLI入口
├── configs/                 # 配置管理
│   ├── __init__.py
│   └── settings.py          # 配置类
├── llm/                     # LLM抽象层
│   ├── __init__.py
│   ├── base.py              # LLM基类
│   └── providers/           # LLM提供商实现
│       └── bedrock.py       # AWS Bedrock实现
├── mcpHub/                  # MCP协议支持
│   ├── __init__.py
│   ├── client.py            # MCP客户端
│   ├── installer.py         # MCP安装器
│   └── server.py            # MCP服务器
├── plugin/                  # 插件系统核心
│   ├── __init__.py
│   ├── base.py              # 插件基类
│   ├── decorators.py        # 插件装饰器
│   ├── manager.py           # 插件管理器
│   └── registry.py          # 插件注册表
├── plugins/                 # 插件实现
│   ├── __init__.py
│   ├── chat/                # 聊天插件
│   ├── hello/               # 示例插件
│   ├── mcp/                 # MCP管理插件
│   └── review/              # 代码审查插件
├── prompts/                 # 提示词模板
│   └── system_prompt.xml    # 系统提示词
├── share/                   # 共享工具
│   ├── __init__.py
│   └── util.py              # 工具函数
├── main.py                  # 应用入口
├── pyproject.toml           # 项目配置
└── README.md                # 项目文档
```
