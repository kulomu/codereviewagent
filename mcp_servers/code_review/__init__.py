"""
airc Code Review MCP server

這個模組提供與Code Review相關的工具與提示詞，
可透過 airc MCP 架構擴充使用，支援自動取得 git diff、
檢索知識庫、發送 prompt 生成審查建議等功能。
"""

# 導入 tool 與 prompt，讓使用者可直接使用
from .tools import (
    get_current_working_diff,
    get_gitlab_mr_diff,
    get_project_framework_info,
    get_framework_info_by_gitlab,
    get_knowledge_base_chunks,
    post_mr_comment,
    # list_prompt_templates,
    # get_prompt_template,
)

from .prompts import (
    get_code_review_prompt,
    get_analyze_changes_prompt,
    get_standard_summary_prompt
)

__all__ = [
    # Tools
    "get_current_working_diff",
    "get_gitlab_mr_diff",
    "get_project_framework_info",
    "get_framework_info_by_gitlab",
    "get_knowledge_base_chunks",
    "post_mr_comment",
    # "list_prompt_templates",
    # "get_prompt_template",

    # Prompts
    "get_code_review_prompt",
    "get_analyze_changes_prompt",
    "get_standard_summary_prompt",
]

__version__ = '0.1.0'