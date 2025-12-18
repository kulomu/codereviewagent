from dataclasses import dataclass, asdict
from typing import List, Dict, Optional, AsyncGenerator, Union
import json
import asyncio
import os
import re
from string import Template
from agent.core.mcp import MCPToolAgent
from pathlib import Path
from mcp.types import (
    EmbeddedResource,
    GetPromptResult,
    ImageContent,
    PromptMessage,
    Role,
    TextContent,
    TextResourceContents
)
import requests
import aiohttp
from functools import lru_cache


class SecurityError(Exception):
    """安全相关异常"""
    pass


@dataclass
class DiffContent:
    file_path: str
    content: str

@dataclass
class StandardContent:
    name: str
    content: str
    case: str

@dataclass 
class ReviewStandards:
    name: str
    standards: List[StandardContent]

@dataclass
class ReviewResult:
    file_path: str
    comments: List[Dict[str, str]]

@dataclass
class ReviewDimensions:  
    dimension: str
    knowledge: List[str]
    frameworks: List[str]  

@dataclass
class MergeRequestInfo:
    project_id: str
    project_url: str
    merge_request_iid: int
    commit_sha: str
    diff_refs: dict

class Reviewer(MCPToolAgent):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 支持通过环境变量或配置调整批次大小
        self.batch_size = int(os.getenv('REVIEW_BATCH_SIZE', 6))
        # 控制最大并发批次数，避免API过载
        self.max_concurrent_batches = min(3, max(1, int(os.getenv('REVIEW_MAX_CONCURRENT', 3))))

    async def initialize(self) -> None:
        # 1. 调用父类初始化
        await super().initialize()
        # 2. 获取review session
        self.review_session = self.get_session('code_review')


    async def run(self, group: Optional[str] = None):
        """处理代码审核流程"""
        if not self.review_session:
           raise Exception('reviewer初始化失败, 请先安装mcp服务: code_review')
        try:
            async for result in self._execute_review_flow(group):
                yield result
            yield "Done"
        except Exception as e:
            print(f"代码审核过程中出现错误: {str(e)}")        

    async def ci_run(self, mr_info: MergeRequestInfo, group: Optional[str] = None):
        """ ci 代码审核流程"""
        try:
            async for result in self._execute_review_flow(group, mr_info):
                yield result
            yield "Done"
        except Exception as e:
            error_comment = f"🚨 代码审核过程中出现错误:\n```\n{str(e)}\n```"
            res = await self.post_review_comment(mr_info, error_comment) 
            yield res   

    def _parse_mcp_response(self, response, expect_content=True) -> tuple[bool, any]:
        """统一解析MCP响应的公共方法"""
        if response.isError:
            return False, None
        try:
            content = json.loads(self._get_text(response.content[0]))
            is_error = content.get('isError', False)
            if is_error:
                return False, None
            
            if expect_content:
                result = content.get('content', [])
                return True, result
            return True, content
        except Exception as e:
            return False, None

    async def set_group_mode(self, group) -> bool:
        """设置代码审核模式"""
        res = await self.review_session.call_tool('set_group_name', {
            'group_name': group or 'web'
        })
        success, _ = self._parse_mcp_response(res, expect_content=False)
        return success
    
    async def _execute_review_flow(self, group: Optional[str] = None, mr_info: Optional[MergeRequestInfo] = None):
        """统一的审查流程核心逻辑"""
        # 1. 设置审核模式
        success = await self.set_group_mode(group)
        if not success:
            yield f"当前不支持{group}端代码审核，请联系开发者增加配置"
            return
            
        # 2. 获取diff内容
        if mr_info:
            diff_contents = await self.get_mr_diff(mr_info)
            project_info = await self.get_mr_project_info(mr_info)
        else:
            diff_contents = await self.get_diff_contents()
            project_info = await self.get_project_info()
            
        if not diff_contents:
            yield "没有获取到diff内容"
            return
        
        # 3. 分析改动点和确定审核维度
        dimensions = await self.analyze_changes(diff_contents, project_info)
        
        # 4. 获取审核标准
        standards = await self.get_review_standards(dimensions)
        
        # 5. standards summary
        summary = await self.get_standards_summary(standards)
        
        # 6. 执行代码审核
        comments = ""
        review_results = self.review_code(diff_contents, summary)
        async for result in review_results:
            if mr_info:
                comments += result
            else:
                yield result
        
        # 7. CI模式的后续处理
        if mr_info:
            # 发布评论
            comment_res = await self.post_review_comment(mr_info, comments)
            yield comment_res
            
            # 总结和记录
            metrics, review_summary = await self.summarize_review(comments, mr_info)
            if metrics and review_summary:
                lark_res = await self.post_to_lark(review_summary)
                yield lark_res
                
                record_cr_res = await self.post_to_lark_sheet(metrics, mr_info)
                yield record_cr_res
            else:
                yield "生成總結失敗，跳過記錄到 Lark"

    async def summarize_review(self, comments: str, mr_info: MergeRequestInfo) -> tuple:
        """
        一次性獲取結構化數據和總結
        
        Args:
            comments: 代碼審查評論內容
            mr_info: Merge Request 信息
            
        Returns:
            tuple: (metrics_dict, summary_text)
                - metrics_dict: 用於記錄到 sheet 的結構化數據
                - summary_text: 用於發送到 Lark 群組的總結文本
        """
        try:
            # 獲取 prompt
            prompt_response = await self.review_session.get_prompt('get_lark_summary_prompt', {
                'comments': comments
            })
            prompt = self._get_text(prompt_response.messages[0].content)
            
            # 調用 LLM 一次
            result = ""
            async for chunk in self.config.llm.generate(prompt):
                result += chunk.text
            
            # 檢查結果是否為空
            if not result or result.strip() == "":
                print("LLM 返回空結果")
                return None, None
                
            # 嘗試提取 JSON 部分
            try:
                # 如果結果包含 ```json 標記，提取其中的內容
                if "```json" in result:
                    json_str = result.split("```json")[1].split("```")[0].strip()
                else:
                    # 否則嘗試直接解析整個結果
                    json_str = result.strip()
                
                # 解析 JSON
                data = json.loads(json_str)
                
                # 檢查必要的字段
                if 'metrics' not in data or 'summary' not in data:
                    print("JSON 缺少必要字段")
                    print("原始輸出：", result)
                    return None, None
                
                # 提取結構化數據
                metrics = data['metrics']
                
                # 生成人類可讀的總結
                summary = f"""### 基本统计
- 审查文件数量：{data['summary']['file_count']}
- 严重问题数量：{data['summary']['critical_issues']}
- 代码质量评分：{data['summary']['score']}

### 严重问题清单
{self._format_critical_problems(data['summary']['critical_problems'])}

### 总体评估
1. 合并建议：{'✅ 可以合并' if data['summary']['review']['can_merge'] else '❌ 需要修改后再合并'}
2. 阻断性问题：{self._format_blocking_issues(data['summary']['review']['blocking_issues'])}
3. 总体结论：{data['summary']['review']['conclusion']}

查看详细CR结果：{mr_info.project_url}/-/merge_requests/{mr_info.merge_request_iid}"""

                return metrics, summary
                
            except json.JSONDecodeError as e:
                print(f"JSON 解析錯誤：{str(e)}")
                print("原始輸出：", result)
                return None, None
                
        except Exception as e:
            print(f"生成總結失敗: {str(e)}")
            import traceback
            print("錯誤詳情：")
            print(traceback.format_exc())
            return None, None
            
    def _format_critical_problems(self, problems: list) -> str:
        """格式化嚴重問題列表"""
        if not problems:
            return "本次审查未发现严重问题"
            
        result = []
        for problem in problems:
            result.append(f"""#### {problem['file']}
                - {problem['description']}
                - 影响：{problem['impact']}
                - 建议：{problem['suggestion']}""")
                        
        return "\n\n".join(result)
        
    def _format_blocking_issues(self, issues: list) -> str:
        """格式化阻斷性問題"""
        if not issues:
            return "不存在"
        return "、".join(issues)

    async def post_to_lark(self, summary: str):
        """将审核结果发布到Lark"""
        lark_res = await self.review_session.call_tool('send_lark_message', {
            "message": summary
        })
        if lark_res.isError:
            return "发布到Lark失败"
        try:
            content = json.loads(self._get_text(lark_res.content[0]))
            comment = content.get('content', [])[0]
            return comment.get('text', '')
        except Exception as e:
            return f"发布到Lark失败: {e}"

    async def post_to_lark_sheet(self, metrics, mr_info: MergeRequestInfo):
        """将审核结果发布到Lark sheet"""
        record_cr_res = await self.review_session.call_tool('add_row_to_lark_sheet', {
            "metrics": metrics,
            "mr_info": {
                "project_id": mr_info.project_id,
                "project_url": mr_info.project_url,
                "merge_request_iid": mr_info.merge_request_iid,
                "commit_sha": mr_info.commit_sha or "",
                "diff_refs": mr_info.diff_refs or {}
            }
        })
        if record_cr_res.isError:
            return "发布到Lark Sheet失败"
        try:
            content = json.loads(self._get_text(record_cr_res.content[0]))
            comment = content.get('content', [])[0]
            return comment.get('text', '')
        except Exception as e:
            return f"发布到Lark Sheet失败: {e}"

    async def get_mr_diff(self, mr_info: MergeRequestInfo):
        """获取mr diff""" 
        diff_res = await self.review_session.call_tool('get_gitlab_mr_diff', {
            "project_id": f"{mr_info.project_id}",
            "mr_iid": f"{mr_info.merge_request_iid}"
        })
        success, diff = self._parse_mcp_response(diff_res)
        if not success or not diff:
            return []
        try:
            return [DiffContent(**json.loads(content['text'])) for content in diff]
        except Exception:
            return []

    async def get_mr_project_info(self, mr_info: MergeRequestInfo):
        """获取 mr projectInfo"""    
        project_info_res = await self.review_session.call_tool('get_framework_info_by_gitlab', {
            "project_id": f"{mr_info.project_id}"
        })
        success, project_info_list = self._parse_mcp_response(project_info_res)
        if not success or not project_info_list:
            return {}
        try:
            project_info = project_info_list[0]
            return {
                'frameworks': project_info.get('text', '')
            }
        except Exception:
            return {}

    async def post_review_comment(self, mr_info: MergeRequestInfo, comment: str):
        """发布评论到 MR"""    
        comment_res = await self.review_session.call_tool('post_mr_comment', {
            "project_id": f"{mr_info.project_id}",
            "mr_iid": f"{mr_info.merge_request_iid}",
            "comment": comment
        })
        if comment_res.isError:
            return "留言失败"
        # 解析评论结果
        try:
            comment_content = json.loads(self._get_text(comment_res.content[0]))
            comment = comment_content.get('content', [])[0]
            return comment.get('text', '')
        except Exception as e:
            return f"留言失败: {e}"

    async def get_diff_contents(self) -> List[DiffContent]:
        """从MCP Server获取diff内容"""
        diff_res = await self.review_session.call_tool('get_current_working_diff')
        success, diff = self._parse_mcp_response(diff_res)
        if not success or not diff:
            return []
        try:
            return [DiffContent(**json.loads(content['text'])) for content in diff]
        except Exception:
            return []

    async def get_project_info(self) -> Dict[str, str]: 
        """获取项目基本信息"""
        project_info_res = await self.review_session.call_tool('get_project_framework_info')
        success, project_info_list = self._parse_mcp_response(project_info_res)
        if not success or not project_info_list:
            return {}
        try:
            project_info = project_info_list[0]
            return {
                'frameworks': project_info.get('text', '')
            }
        except Exception:
            return {}
    
    async def analyze_changes(self, diff_contents: List[DiffContent], project_info: Dict) -> List[ReviewDimensions]:
        """分析改动并确定需要的审核维度"""
        # diff_contents to str
        diff_contents_str = "\n".join([f"{diff.file_path}:\n{diff.content}" for diff in diff_contents])
        # project_info to str
        project_info_str = "\n".join([f"{key}: {value}" for key, value in project_info.items()])
        
        # 调用模型进行分析
        response = await self.review_session.get_prompt('get_analyze_changes_prompt',{
            'code': diff_contents_str, 
            'project_info': project_info_str
        })

        prompt = self._get_text(response.messages[0].content)

        dimensions = ""
        async for chunk in self.config.llm.generate(prompt):
            dimensions += chunk.text
        # 解析返回的维度
        try:
            return json.loads(''.join(dimensions))
        except json.JSONDecodeError:
            # 如果解析失败，返回默认维度
            return [{"dimension": "code_quality", "knowledge": [], "frameworks": []}]
    
    async def get_review_standards(self, dimensions: List[ReviewDimensions]) -> List[ReviewStandards]:
        """获取每个维度的审核标准"""
        tasks = [self.review_session.call_tool('get_knowledge_base_chunks', {**dim}) for dim in dimensions]
        standards_responses = await asyncio.gather(*tasks)  # kb 知识召回
        
        result = []
        for i, standards_response in enumerate(standards_responses):
            success, standards = self._parse_mcp_response(standards_response)
            if not success or not standards:
                continue
            try:
                result.append(ReviewStandards(
                    name=dimensions[i]['dimension'], 
                    standards=[content['text'] for content in standards]
                ))
            except Exception:
                continue
        return result
    
    async def get_standards_summary(self, standards: List[ReviewStandards]) -> str:
        """学习并总结出审核标准"""
        standards_formated = [f"{s.name}: {','.join(s.standards)}" for s in standards or []]
        return  ",".join(standards_formated)
    
    @lru_cache(maxsize=1)
    def _load_review_prompt_template(self) -> str:
        """加载代码审核提示词模板 - LRU缓存优化"""
        # 支持通过环境变量配置模板路径
        template_path = os.getenv('REVIEW_TEMPLATE_PATH')
        if template_path:
            prompt_file_path = Path(template_path)
        else:
            # 默认路径 - 确保在当前模块目录内
            prompt_file_path = Path(__file__).parent / 'prompts' / 'common_code_review.xml'
        
        try:
            # 确保文件存在且可读
            if not prompt_file_path.exists():
                raise FileNotFoundError(f"审核提示词模板文件未找到: {prompt_file_path}")
            
            if not prompt_file_path.is_file():
                raise ValueError(f"指定路径不是文件: {prompt_file_path}")
            
            with open(prompt_file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # 基本内容验证
            if not content.strip():
                raise ValueError("模板文件内容为空")
            
            return content
            
        except FileNotFoundError:
            raise FileNotFoundError(f"审核提示词模板文件未找到: {prompt_file_path}")
        except PermissionError:
            raise PermissionError(f"无权限读取模板文件: {prompt_file_path}")
        except Exception as e:
            raise Exception(f"加载审核提示词模板失败: {str(e)}")

    def _render_review_prompt(self, code: str, standard: str, total_files: int, 
                             batch_info: str = "", is_batch: bool = False) -> str:
        """渲染审核提示词模板，支持扩展更多变量"""
        template_content = self._load_review_prompt_template()
        
        # 定义所有可能的模板变量
        template_vars = {
            "code": self._escape_template_value(code),
            "standard": self._escape_template_value(standard),
            "total_files": str(total_files),
            "batch_info": self._escape_template_value(batch_info),
            "is_batch": "true" if is_batch else "false"
        }
        
        try:
            # 使用更安全的模板替换方式
            # 先将双花括号格式转换为${}格式
            converted_template = self._convert_template_format(template_content)
            
            # 使用string.Template进行安全替换
            template = Template(converted_template)
            rendered_prompt = template.safe_substitute(**template_vars)

            return rendered_prompt
            
        except Exception as e:
            raise Exception(f"模板渲染失败: {str(e)}")
    
    def _convert_template_format(self, template: str) -> str:
        """将{{variable}}格式转换为${variable}格式，但只转换input部分，保留output部分的Handlebars语法"""
        # 找到input部分的边界
        input_start = template.find('<input>')
        input_end = template.find('</input>')
        
        if input_start == -1 or input_end == -1:
            # 没有找到input标签，说明可能是简单模板，转换所有变量
            pattern = r'\{\{(\w+)\}\}'
            return re.sub(pattern, r'${\1}', template)
        
        # 分离input部分和其他部分
        before_input = template[:input_start]
        input_section = template[input_start:input_end + 8]  # 包含</input>
        after_input = template[input_end + 8:]
        
        # 只转换input部分的{{variable}}格式
        pattern = r'\{\{(\w+)\}\}'
        converted_input = re.sub(pattern, r'${\1}', input_section)
        
        # 重新组装模板，保持output部分的Handlebars语法不变
        return before_input + converted_input + after_input
    
    def _escape_template_value(self, value: str) -> str:
        """转义模板变量值中的特殊字符，防止模板注入"""
        if not isinstance(value, str):
            return str(value)
        
        # 转义可能导致模板注入的字符
        # 保护${和}字符，防止意外的模板变量替换
        escaped_value = value.replace('${', '\\${').replace('}', '\\}')
        
        return escaped_value
    
    async def review_code(self, diff_contents: List[DiffContent], summary: str) -> AsyncGenerator[str, None]:
        """执行代码审核 - 优化的批量处理版本"""
        try:
            total_files = len(diff_contents)
            
            # 决定处理策略
            if total_files > self.batch_size:
                # 大批量：分组处理
                async for chunk in self._review_large_changes(diff_contents, summary):
                    yield chunk
            else:
                # 单文件并行处理
                async for chunk in self._review_parallel_batch(diff_contents, summary):
                    yield chunk        
        except Exception as e:
            yield f"代码审核过程出错: {str(e)}"

    async def _review_parallel_batch(self, diff_contents: List[DiffContent], summary: str) -> AsyncGenerator[str, None]:
        """并行处理多个文件"""
        try:
            # 创建并行任务
            async def review_single_file(diff: DiffContent):
                diff_content_str = f"// {diff.file_path}:\n\n{diff.content}\n"
                prompt = self._render_review_prompt(
                    code=diff_content_str,
                    standard=summary,
                    total_files=len(diff_contents),
                    batch_info=f"并行审核文件 {diff.file_path}",
                    is_batch=False
                )
                
                result = ""
                async for chunk in self.config.llm.generate(prompt):
                    result += chunk.text
                return f"""【{diff.file_path}】审查报告 \n --- \n{result}\n\n"""
            
            # 并行执行，但限制并发数以避免过载
            results = []
            for i in range(0, len(diff_contents), 3):  # 每次处理3个文件
                batch = diff_contents[i:i+3]
                tasks = [review_single_file(diff) for diff in batch]
                batch_results = await asyncio.gather(*tasks)
                results.extend(batch_results)
            
            # 输出结果
            for result in results:
                yield result
                
        except Exception as e:
            yield f"并行审核失败: {str(e)}"

    async def _review_large_changes(self, diff_contents: List[DiffContent], 
                                summary: str) -> AsyncGenerator[str, None]:
        """处理大型变更的审核 - 优化版本，支持并行批处理"""
        try:
            # 分组处理文件
            batches = [diff_contents[i:i + self.batch_size] 
                    for i in range(0, len(diff_contents), self.batch_size)]
            
            total_files = len(diff_contents)
            total_batches = len(batches)
            
            # 并行处理批次的辅助函数
            async def process_batch(batch_index: int, batch: List[DiffContent]) -> tuple[int, str]:
                """处理单个批次"""
                try:
                    # 合并当前批次的 diff 内容
                    combined_diff = "\n".join([
                        f"// {diff.file_path}:\n\n{diff.content}\n"
                        for diff in batch
                    ])
                    
                    # 准备批次信息
                    batch_info = f"第 {batch_index + 1}/{total_batches} 批次，当前批次包含 {len(batch)} 个文件"
                    
                    # 使用公共函数渲染提示词
                    prompt = self._render_review_prompt(
                        code=combined_diff,
                        standard=summary,
                        total_files=total_files,
                        batch_info=batch_info,
                        is_batch=True
                    )
                        
                    # 收集当前批次的审核结果
                    batch_result = ""
                    async for chunk in self.config.llm.generate(prompt):
                        batch_result += chunk.text
                    
                    return batch_index, batch_result
                    
                except Exception as e:
                    return batch_index, f"批次 {batch_index + 1} 处理失败: {str(e)}"
            
            # 控制并发数量，避免过载
            max_concurrent_batches = min(self.max_concurrent_batches, total_batches)
            all_results = [None] * total_batches  # 预分配结果数组
            
            # 分批并行处理
            for i in range(0, total_batches, max_concurrent_batches):
                # 获取当前并发批次
                current_batches = batches[i:i + max_concurrent_batches]
                current_indices = list(range(i, min(i + max_concurrent_batches, total_batches)))
                
                # 并行处理当前批次组
                tasks = [
                    process_batch(idx, batch) 
                    for idx, batch in zip(current_indices, current_batches)
                ]
                
                # 等待当前批次组完成
                batch_results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # 处理结果
                for result in batch_results:
                    if isinstance(result, Exception):
                        # 异常处理
                        yield f"批次处理异常: {str(result)}\n"
                        continue
                    
                    batch_index, batch_result = result
                    all_results[batch_index] = batch_result

            # 生成最终总结
            yield "# 📋 大型变更审查报告\n"
            yield f"总计 {total_files} 个文件，分 {total_batches} 个批次并行处理\n\n"
            
            # 按顺序输出各批次结果
            for i, result in enumerate(all_results, 1):
                if result is not None:
                    yield f"## 批次 {i} 审查结果\n"
                    yield f"{result}\n"
                    yield "\n---\n\n"
                else:
                    yield f"## 批次 {i} 处理失败\n\n"

        except Exception as e:
            yield f"大型变更审核失败: {str(e)}"
    def _get_text(self, content: Union[TextContent, ImageContent, EmbeddedResource]) -> Optional[str]:
        """
        Extract text content from a content object if available.

        Args:
            content: A content object (TextContent, ImageContent, or EmbeddedResource)

        Returns:
            The text content as a string or None if not a text content
        """
        # print(f"get_text: {content}")
        if isinstance(content, TextContent):
            return self._get_text(content.text)

        if isinstance(content, TextResourceContents):
            return self._get_text(content.text)

        if isinstance(content, EmbeddedResource):
            if isinstance(content.resource, TextResourceContents):
                return self._get_text(content.resource.text)

        if isinstance(content, str):
            return content    

        return None
