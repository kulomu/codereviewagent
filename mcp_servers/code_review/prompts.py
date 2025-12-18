import os
from pathlib import Path
from typing import Dict, List
from pydantic import Field
from mcp.types import Prompt, PromptArgument
from .instance import airc
from .configs.config_manager import get_template_dir

PROMPTS = {
    "common_code_review": Prompt(
        name="common_code_review",
        description="代碼審查的通用提示詞",
        arguments=[
            PromptArgument(name="code", description="要被審查的代碼", required=True),
            PromptArgument(name="knowledge", description="知識庫內容", required=False),
        ]
    ),
    "analyze_changes": Prompt(
        name="analyze_changes",
        description="分析代碼變動涉及的維度的提示詞",
        arguments=[
            PromptArgument(name="changes", description="代碼變動", required=True),
            PromptArgument(name="project_info", description="項目信息", required=True),
        ]
    ),
    "standard_summary": Prompt(
        name="standard_summary",
        description="總結知識庫內容並提煉審查標準的提示詞",
        arguments=[
            PromptArgument(name="standards", description="企業規範陣列", required=True),
        ]
    )
}

def get_prompt_files() -> List[Path]:
    """獲取所有提示文件"""
    template_dir = get_template_dir()
    prompt_dir = template_dir / 'prompts'
    return list(prompt_dir.glob('*.xml'))

def load_prompt(prompt_file: Path) -> str:
    """載入提示文件內容"""
    with open(prompt_file, 'r', encoding='utf-8') as f:
        return f.read()

def get_prompts() -> Dict[str, str]:
    """獲取所有提示"""
    return {f.stem: load_prompt(f) for f in get_prompt_files()}

@airc.prompt("get_code_review_prompt", "代碼審查的通用提示詞")
async def get_code_review_prompt(
    code: str = Field(description="要被審查的代碼", default="", required=True),
    kb: str = Field(description="知識庫內容", default="", required=False)
) -> str:
    template_dir = get_template_dir()
    template_path = template_dir / "common_code_review.xml"
    text = template_path.read_text(encoding="utf-8")
    if code:
        text = text.replace("{{code}}", code)
    if kb:
        text = text.replace("{{knowledge}}", kb)
    return text

@airc.prompt("get_analyze_changes_prompt", "總結代碼變動涉及的維度的提示詞")
async def get_analyze_changes_prompt(
    code: str = Field(description="要被審查的代碼", default="", required=True),
    project_info: str = Field(description="項目信息", default="", required=True)
) -> str:
    template_dir = get_template_dir()
    template_path = template_dir / "analyze_changes.xml"
    text = template_path.read_text(encoding="utf-8")
    return text.replace("{{code}}", code).replace("{{project_info}}", project_info)

@airc.prompt("get_standard_summary_prompt", "總結知識庫內容並提煉審查標準的提示詞")
async def get_standard_summary_prompt(
    standards: str = Field(description="知識庫召回信息", default="", required=True)
) -> str:
    template_dir = get_template_dir()
    template_path = template_dir / "standard_summary.xml"
    text = template_path.read_text(encoding="utf-8")
    return text.replace("{{standards}}", standards)

@airc.prompt("get_large_code_review_prompt", "批量文件代碼審查的通用提示詞")
async def get_large_code_review_prompt(
    code: str = Field(description="要被審查的代碼", default="", required=True),
    kb: str = Field(description="知識庫內容", default="", required=False),
    total_files: str = Field(description="需要审批的文件总数", default="", required=False),
    batch_info: str = Field(description="当前review的批次信息", default="", required=False),
) -> str:
    template_dir = get_template_dir()
    template_path = template_dir / "large_code_review.xml"
    text = template_path.read_text(encoding="utf-8")
    if code:
        text = text.replace("{{code}}", code)
    if kb:
        text = text.replace("{{knowledge}}", kb)
    if total_files:
        text = text.replace("{{total_files}}", total_files)    
    if batch_info:
        text = text.replace("{{batch_info}}", batch_info)        
    return text

@airc.prompt("get_lark_summary_prompt", "根据review结果生成lark消息提示词")
async def get_lark_summary_prompt(
    comments: str = Field(description="review结果", default="", required=True)
) -> str:
    template_dir = get_template_dir()
    template_path = template_dir / "lark_review.xml"
    text = template_path.read_text(encoding="utf-8")
    return text.replace("{{comments}}", comments)