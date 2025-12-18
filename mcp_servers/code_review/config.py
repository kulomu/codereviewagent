def define_mcp() -> dict:
    return {
        "name": "code_review",
        "version": "0.1.0",
        "description": "提供代碼審查工具與提示詞的 MCP Server",
        "entry": "main.py",  # 重點：main.py 是在 MCP 安裝資料夾根目錄下
        "command": {
            "run": {
                "command": "uv",
                "args": ["--directory", ".", "run", "main.py"]
            }
        }
    }
