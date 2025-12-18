from typing import Any, List
from pathlib import Path
import subprocess
import re
from mcp.types import CallToolResult, TextContent
import json
from pydantic import BaseModel
import requests
from urllib.parse import quote
from pathlib import Path
import os
import asyncio
from datetime import datetime
from dataclasses import dataclass
from .configs.config_manager import get_global_variable_config, get_current_group_variable_config, set_current_group

from .rag.tools import RAGClient, RetrievalModel
from .instance import airc

CONFIG_PATH = Path(__file__).parent / "configs" / "config.yml"

# 讀取全局配置（這是固定的，不需要動態獲取）
global_config = get_global_variable_config()
GITLAB_BASE_URL = global_config['gitlab']['base_url']
GITLAB_BASE_API_URL = global_config['gitlab']['base_api_url']
GITLAB_TOKEN = os.getenv("GITLAB_TOKEN", "")
DIFY_BASE_URL = global_config['dify']['base_url']

allowed_group_list = ['web', 'app']

def parse_package_json(content: str) -> List[str]:
    """解析 package.json 文件"""
    package = json.loads(content)
    # 合并所有依赖
    all_deps = {
        **package.get("dependencies", {}),
    }
    return [f"{name} {version}" for name, version in all_deps.items()]

def parse_pubspec_yaml(content: str) -> dict:
    """
    解析 pubspec.yaml 文件，返回项目框架信息和依赖
    Returns:
        dict: 包含 environment 和 dependencies 的字典
    """
    try:
        result = {
            "environment": [],  # 环境依赖
            "dependencies": []  # 项目依赖
        }
        
        in_environment = False
        in_dependencies = False
        
        for line in content.splitlines():
            line = line.strip()
            # 跳过空行、注释和文档标记
            if line.startswith('#') or line.startswith('---'):
                continue
                
            # 检查区块
            if line == 'environment:':
                in_environment = True
                in_dependencies = False
                continue
            elif line == 'dependencies:':
                in_environment = False
                in_dependencies = True
                continue
            elif line == 'dev_dependencies:':
                # 遇到 dev_dependencies 就停止解析
                break
            elif not line:
                in_environment = False
                in_dependencies = False
                continue
            
            # 解析环境依赖
            if in_environment and line.startswith(''):
                line = line.lstrip()
                if ':' in line:
                    name, version = line.split(':', 1)
                    name = name.strip()
                    version = version.strip().strip('"\'')
                    if name == 'sdk':
                        result["environment"].append(f"dart_sdk {version}")
                    elif name == 'flutter':
                        result["environment"].append(f"flutter_sdk {version}")
            
            # 解析项目依赖
            if in_dependencies and line.startswith(''):
                line = line.lstrip()
                # 跳过 Flutter SDK 声明
                if line.startswith('flutter:') and 'sdk:' in line:
                    continue
                # 跳过嵌套配置
                if line.startswith(' '):
                    continue
                # 解析依赖行
                if ':' in line:
                    name, version = line.split(':', 1)
                    name = name.strip()
                    version = version.strip().strip('"\'')
                    if version and not version.startswith('sdk'):
                        result["dependencies"].append(f"{name} {version}")
        return [*result["environment"], *result["dependencies"]]
    except Exception as e:
        raise ValueError(f"YAML解析错误: {str(e)}")

@airc.tool()
async def set_group_name(group_name: str) -> CallToolResult:
    """
    設置當前使用的配置組別。
    Args:
        group_name: 要設置的組別名稱，目前只允許 'web' 或 'app'
    Returns:
        設置結果
    """
    try:
        if group_name not in allowed_group_list:
            return CallToolResult(
                isError=True,
                content=[TextContent(
                    type="text",
                    text=f"無效的組別名稱：{group_name}，目前只允許 'web' 或 'app'"
                )]
            )
            
        set_current_group(group_name)
        return CallToolResult(
            content=[TextContent(
                type="text",
                text=f"已成功切換到 {group_name} 組別"
            )]
        )
    except Exception as e:
        return CallToolResult(
            isError=True,
            content=[TextContent(
                type="text",
                text=f"切換組別失敗：{str(e)}"
            )]
        )

@airc.tool()
async def get_framework_info_by_gitlab(project_id: str, branch: str = "main") -> CallToolResult:
    """
    從 GitLab 項目中讀取指定檔案，並解析出所有依賴與版本。
    Args:
        project_id: GitLab 項目的 project_id
        branch: 來源分支（默認 main）
    Returns:
        所有依賴的列表，格式為 ["package_name version"]
    """
    try:
        # 只動態獲取當前組別配置
        current_group_config = get_current_group_variable_config()
        
        # 從配置文件中獲取 repo_info_file
        file_path = current_group_config.get('repo_info_file', '')
        file_path_encoded = quote(file_path, safe='')
        url = f"{GITLAB_BASE_API_URL}/projects/{project_id}/repository/files/{file_path_encoded}/raw"
        headers = {"PRIVATE-TOKEN": GITLAB_TOKEN}
        params = {"ref": branch}

        res = requests.get(url, headers=headers, params=params)

        if res.status_code != 200:
            return CallToolResult(isError=True, content=[TextContent(type="text", text=f"無法讀取（{res.status_code}）\n內容：{res.text[:300]}")])

        content = res.text
            
        # 根据文件扩展名选择解析方法
        if file_path == 'package.json':
            deps_list = parse_package_json(content)
        elif file_path == 'pubspec.yaml':
            deps_list = parse_pubspec_yaml(content)
        else:
            return CallToolResult(
                isError=True,
                content=[TextContent(
                    type="text",
                    text=f"不支持的配置文件格式: {file_path}"
                )]
            )

        return CallToolResult(
            content=[TextContent(
                type="text",
                text=json.dumps(deps_list, ensure_ascii=False)
            )]
        )

    except json.JSONDecodeError as e:
        return CallToolResult(
            isError=True,
            content=[TextContent(
                type="text",
                text=f"JSON 解析失败：{e}\n内容：{content[:300]}"
            )]
        )

    except Exception as e:
        return CallToolResult(isError=True, content=[TextContent(type="text", text=f"發生未知錯誤：{e}")])


@airc.tool()
async def get_gitlab_mr_diff(project_id: str, mr_iid: str) -> CallToolResult:
    """
    根據 GitLab 專案 ID 和 Merge Request IID 取得完整 diff，
    僅保留特定副檔名（副檔名從配置文件內獲取，如果沒有就不過濾），
    並排除被刪除的檔案。
    回傳每個檔案的 diff，格式為 JSON 字串：
    { "file_path": "xxx", "content": "完整 diff 區塊" }
    """
    try:
        # 只動態獲取當前組別配置
        current_group_config = get_current_group_variable_config()
        
        headers = {"PRIVATE-TOKEN": GITLAB_TOKEN}
        url = f"{GITLAB_BASE_API_URL}/projects/{project_id}/merge_requests/{mr_iid}/changes"
        response = requests.get(url, headers=headers)

        if response.status_code != 200:
            return CallToolResult(
                isError=True,
                content=[
                    TextContent(
                        type="text",
                        text=f"GitLab API 錯誤：{response.status_code} - {response.text}"
                    )
                ]
            )

        data = response.json()
        changes = data.get("changes", [])
        if not changes:
            return CallToolResult(content=[TextContent(type="text", text="[]")])

        # 從配置文件中獲取允許的副檔名，如果沒有則使用空列表（不過濾任何副檔名）
        allowed_extensions = tuple(current_group_config.get('extensions', []))
        
        content_blocks = []
        for change in changes:
            # 過濾掉刪除的檔案
            if change.get("deleted_file", False):
                continue

            # 取得檔案路徑
            file_path = change.get("new_path") or change.get("old_path") or "未知檔案"

            # 如果有設定副檔名過濾，則進行過濾
            if allowed_extensions and not file_path.endswith(allowed_extensions):
                continue

            content_blocks.append(
                TextContent(
                    type="text",
                    text=json.dumps({
                        "file_path": file_path,
                        "content": change.get("diff", "")
                    }, ensure_ascii=False)
                )
            )

        return CallToolResult(content=content_blocks)

    except Exception as e:
        return CallToolResult(
            isError=True,
            content=[
                TextContent(
                    type="text",
                    text=f"發生錯誤：{e}"
                )
            ]
        )



@airc.tool()
async def get_current_working_diff() -> CallToolResult:
    """
    回傳目前工作目錄與 HEAD 的完整 diff（含 staged 和 unstaged），依檔案分類。
    每個項目為 TextContent，其中 text 是 JSON 字串：
    { "file_path": "xxx", "content": "完整 diff 區塊" }
    """
    try:
        unstaged = subprocess.run(["git", "diff", "--unified=3", ":(exclude)*.log"], capture_output=True, text=True, check=True).stdout
        staged = subprocess.run(["git", "diff", "--cached", "--unified=3", ":(exclude)*.log"], capture_output=True, text=True, check=True).stdout
        full_diff = unstaged + staged
        file_diffs = {}
        current_file = None
        current_diff_block = []

        for line in full_diff.splitlines():
            if line.startswith("diff --git"):
                if current_file and current_diff_block:
                    # 跳过 .log 文件
                    if not current_file.endswith('.log'):
                        file_diffs[current_file] = "\n".join(current_diff_block)
                match = re.match(r'diff --git a/(.+?) b/(.+)', line)
                if match:
                    current_file = match.group(2)
                    current_diff_block = [line]
            elif current_file and not current_file.endswith('.log'):
                current_diff_block.append(line)

        if current_file and current_diff_block and not current_file.endswith('.log'):
            file_diffs[current_file] = "\n".join(current_diff_block)

        content_blocks = [TextContent(type="text", text=json.dumps({"file_path": file_path, "content": diff}, ensure_ascii=False)) for file_path, diff in file_diffs.items()]

        return CallToolResult(isError=False, content=content_blocks or [TextContent(type="text", text="[]")])

    except subprocess.CalledProcessError as e:
        return CallToolResult(isError=True, content=[TextContent(type="text", text=f"執行 git diff 時發生錯誤：{e.stderr}")])


@airc.tool()
async def get_project_framework_info() -> CallToolResult:
    """
    獲取當前項目的所有依賴與版本。
    Returns:
        所有依賴的列表，格式為 ["package_name version"]
    """
    try:
        # 只動態獲取當前組別配置
        current_group_config = get_current_group_variable_config()
        
        # 從配置文件中獲取 repo_info_file
        file_path = current_group_config.get('repo_info_file', '')
        package_path = Path(file_path)
        if not package_path.exists():
            return CallToolResult(isError=True, content=[TextContent(type="text", text=f"找不到{file_path}")])

        content = package_path.read_text(encoding="utf-8")
            
        # 根据文件扩展名选择解析方法
        if file_path == 'package.json':
            deps_list = parse_package_json(content)
        elif file_path == 'pubspec.yaml':
            deps_list = parse_pubspec_yaml(content)
        else:
            return CallToolResult(
                isError=True,
                content=[TextContent(
                    type="text",
                    text=f"不支持的配置文件格式: {file_path}"
                )]
            )

        return CallToolResult(
            isError=False,
            content=[TextContent(
                type="text",
                text=json.dumps(deps_list, ensure_ascii=False)
            )]
        )

    except Exception as e:
        return CallToolResult(isError=True, content=[TextContent(type="text", text=f"發生錯誤：{e}")])


class ReviewDimensions(BaseModel):
    dimension: str
    knowledge: list[str]
    frameworks: list[str]

class InputWrapper(BaseModel):
    query: ReviewDimensions


@airc.tool()
async def get_knowledge_base_chunks(dimension: str,  knowledge: list[str], frameworks: list[str]) -> CallToolResult:
    """
    從知識庫檢索與主題相關的內容。
    """
    try:
        # 只動態獲取當前組別配置
        current_group_config = get_current_group_variable_config()
        
        topic = ",".join([dimension] + frameworks + knowledge)
        async with RAGClient(DIFY_BASE_URL) as rag:
            dataset_id = current_group_config['dify'].get('dataset_id', '') 
            results = await rag.retrieve(
                dataset_id=dataset_id,
                retrieval_model=RetrievalModel(query=topic, top_k=5, search_method='semantic_search')
            )
            chunks = [r["segment"]["content"] for r in results.get("records", [])]
            text = "\n\n".join(f"- {chunk}" for chunk in (chunks or []))
            return CallToolResult(isError=False, content=[TextContent(type="text", text=text)])

    except Exception as e:
        return CallToolResult(isError=True, content=[TextContent(type="text", text=f"知識檢索失敗：{e}")])


@airc.tool()
async def post_mr_comment(project_id: str, mr_iid: str, comment: str) -> CallToolResult:
    """
    發布留言到 GitLab Merge Request（PR）的留言區。

    Args:
        project_id: GitLab 項目的 ID
        mr_iid: Merge Request 的 IID
        comment: 要發送的留言內容

    Returns:
        CallToolResult: 包含成功訊息或錯誤資訊
    """
    try:
        url = f"{GITLAB_BASE_API_URL}/projects/{project_id}/merge_requests/{mr_iid}/notes"
        res = requests.post(url, headers={"PRIVATE-TOKEN": GITLAB_TOKEN}, data={"body": comment})
        if res.status_code == 201:
            return CallToolResult(content=[TextContent(type="text", text="留言成功")])
        return CallToolResult(isError=True, content=[TextContent(type="text", text=f"留言失敗（{res.status_code}）: {res.text[:300]}")])

    except Exception as e:
        return CallToolResult(isError=True, content=[TextContent(type="text", text=f"發生例外錯誤：{e}")])


@airc.tool()
async def send_lark_message(message: str) -> CallToolResult:
    """
    傳送文字訊息到指定的 Lark 群組（透過 Webhook）。
    """
    # 只動態獲取當前組別配置
    current_group_config = get_current_group_variable_config()
    
    webhook_id = current_group_config['lark'].get('webhook_id', '')
    webhook_url = f"https://open.larksuite.com/open-apis/bot/v2/hook/{webhook_id}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "msg_type": "text",
        "content": {"text": message}
    }

    try:
        response = await asyncio.to_thread(
            requests.post,
            webhook_url,
            headers=headers,
            json=payload,
            timeout=10
        )
        response.raise_for_status()

        result_json = response.json()

        if result_json.get("code") == 0:
            return CallToolResult(
                success=True,
                message="訊息發送成功！",
                content=[TextContent(type="text", text="訊息發送成功！")]
            )
        else:
            return CallToolResult(
                success=False,
                message=f"Lark 回傳錯誤：{result_json.get('msg')}",
                content=[TextContent(type="text", text=f"Lark 回傳錯誤：{result_json.get('msg')}")]
            )

    except requests.exceptions.RequestException as e:
        return CallToolResult(
            success=False,
            message=f"HTTP 請求錯誤：{str(e)}",
            content=[TextContent(type="text", text=f"HTTP 請求錯誤：{str(e)}")]
        )
    except Exception as e:
        return CallToolResult(
            success=False,
            message=f"未知錯誤：{str(e)}",
            content=[TextContent(type="text", text=f"未知錯誤：{str(e)}")]
        )

async def get_code_review(
    repo_url: str,
    branch: str = "main",
    frameworks: List[str] = None,
    knowledge: List[str] = None,
    dimension: str = "code_review"
) -> str:
    """獲取代碼審查結果"""
    try:
        # 只動態獲取當前組別配置
        current_group_config = get_current_group_variable_config()
        
        topic = ",".join([dimension] + frameworks + knowledge)
        async with RAGClient(DIFY_BASE_URL) as rag:
            dataset_id = current_group_config['dify'].get('dataset_id', '') 
            results = await rag.retrieve(
                dataset_id=dataset_id,
                retrieval_model=RetrievalModel(query=topic, top_k=10, search_method='semantic_search')
            )
            chunks = [r["segment"]["content"] for r in results.get("records", [])]
            text = "\n\n".join(f"- {chunk}" for chunk in (chunks or []))
            return text

    except Exception as e:
        return f"知識檢索失敗：{e}"

@dataclass
class MergeRequestInfo:
    project_id: str
    project_url: str
    merge_request_iid: int
    commit_sha: str
    diff_refs: dict

@airc.tool()
async def add_row_to_lark_sheet(metrics: dict, mr_info: MergeRequestInfo) -> CallToolResult:
    """
    在工作表的最後一行添加新數據
    
    Args:
        metrics: 從 summarize_review 獲取的結構化數據
        mr_info: Merge Request 信息
        
    Returns:
        CallToolResult: 操作結果
    """
    try:
        # 獲取當前組別配置
        current_group_config = get_current_group_variable_config()
        lark_config = current_group_config.get('lark', {})
        
        app_id = lark_config.get('app_id')
        app_secret_key = lark_config.get('app_secret_key')
        spreadsheet_token = lark_config.get('spreadsheet_token')
        sheet_id = lark_config.get('sheet_id')
        
        if not all([app_id, app_secret_key, spreadsheet_token, sheet_id]):
            return CallToolResult(
                isError=True,
                content=[TextContent(
                    type="text",
                    text="缺少必要的 Lark 配置"
                )]
            )
            
        # 獲取 access token
        url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        headers = {
            "Content-Type": "application/json; charset=utf-8",
        }
        payload = {
            "app_id": app_id,
            "app_secret": app_secret_key,
        }

        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
        lark_access_token = data.get("tenant_access_token")
        
        if not lark_access_token:
            return CallToolResult(
                isError=True,
                content=[TextContent(
                    type="text",
                    text=f"無法取得 Lark access token：{data.get('msg', '未知錯誤')}"
                )]
            )
            
        # 獲取最後一行索引
        url = f"https://open.larksuite.com/open-apis/sheets/v2/spreadsheets/{spreadsheet_token}/values/{sheet_id}!A:B"
        headers = {
            "Authorization": f"Bearer {lark_access_token}",
            "Content-Type": "application/json; charset=utf-8"
        }
        response = requests.get(url, headers=headers)
        response.raise_for_status()

        res_json = response.json()
        values = res_json.get("data", {}).get("valueRange", {}).get("values")
        last_row_index = len(values) if values else 0
        append_row_index = last_row_index + 1
        
        # 獲取當前時間
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 構建 MR 鏈接
        mr_link = f'{mr_info.project_url}/-/merge_requests/{mr_info.merge_request_iid}'
        
        # 格式化嚴重錯誤原因
        critical_reasons = "、".join(metrics.get('critical_reasons', []))
        if not critical_reasons:
            critical_reasons = "無"
            
        # 格式化維度
        dimensions = "、".join(metrics.get('dimensions', []))
        if not dimensions:
            dimensions = "無"
            
        # 格式化標籤
        tags = "、".join(metrics.get('tags', []))
        if not tags:
            tags = "無"
        
        # 構建要寫入的數據
        values = [
            current_time,
            mr_link,
            str(metrics.get('score', 0)),
            str(metrics.get('critical_issues', 0)),
            str(metrics.get('medium_issues', 0)),
            str(metrics.get('minor_issues', 0)),
            critical_reasons,
            dimensions,
            tags
        ]

        url = f"https://open.larksuite.com/open-apis/sheets/v2/spreadsheets/{spreadsheet_token}/values"
        payload = {
            "valueRange": {
                "range": f"{sheet_id}!A{append_row_index}:I{append_row_index}",
                "values": [values]
            }
        }

        headers = {
            "Authorization": f"Bearer {lark_access_token}",
            "Content-Type": "application/json; charset=utf-8"
        }

        response = requests.put(url, headers=headers, json=payload)
        response.raise_for_status()

        res_json = response.json()
        if res_json.get("code") == 0:
            return CallToolResult(
                content=[TextContent(
                    type="text",
                    text="成功在最後一行添加資料"
                )]
            )
        else:
            return CallToolResult(
                isError=True,
                content=[TextContent(
                    type="text",
                    text=f"添加數據失敗: {res_json.get('msg', '未知錯誤')}"
                )]
            )

    except Exception as e:
        return CallToolResult(
            isError=True,
            content=[TextContent(
                type="text",
                text=f"添加新行失敗: {str(e)}"
            )]
        )