from typing import Dict, List, Optional, AsyncGenerator, Any
from dataclasses import dataclass
import json
import asyncio
import boto3
from ..base import BaseLLM, LLMConfig, Message, Function, LLMRole
import logging
from configs import settings

logger = logging.getLogger(__name__)

@dataclass
class FormatMessages:
    """格式化消息为 Bedrock 格式"""
    messages: List[Dict]
    system: Optional[Dict] = None

@dataclass
class BedrockResponse:
    """Bedrock 响应数据结构"""
    text: str                # 响应文本
    stop_reason: str        # 停止原因
    tool_call: Optional[Dict] = None  # 工具调用信息

class BedrockConfig(LLMConfig):
    """Bedrock 特定配置"""
    def __init__(
        self,
        model_id: str = "us.anthropic.claude-3-7-sonnet-20250219-v1:0",
        aws_access_key_id: str = settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key: str = settings.AWS_SECRET_ACCESS_KEY,
        region_name: str = settings.AWS_REGION,
        anthropic_version: str = "bedrock-2023-05-31",
        **kwargs
    ):
        super().__init__(**kwargs)
        self.model_id = model_id
        self.aws_access_key_id = aws_access_key_id
        self.aws_secret_access_key = aws_secret_access_key
        self.region_name = region_name
        self.anthropic_version = anthropic_version

class BedrockProvider(BaseLLM):
    """Bedrock LLM Provider"""
    
    def __init__(self, config: BedrockConfig):
        super().__init__(config)
        self.client = boto3.client(
            'bedrock-runtime',
            aws_access_key_id=config.aws_access_key_id,
            aws_secret_access_key=config.aws_secret_access_key,
            region_name=config.region_name
        )
        
    def _format_messages(self, messages: List[Message]) -> List[Dict]:
        """格式化消息为 Bedrock 格式"""
        formatted = []
        system = None
        for msg in messages:
            if msg.role == LLMRole.SYSTEM:
                system = [
                    {"text": msg.content}, 
                    {"cachePoint": {"type": "default"}}
                ]
            else: 
                if msg.function_call:
                    tool = json.loads(msg.function_call)
                    tool_use = {
                        "toolUseId": tool.get("id"),
                        "name": tool.get("name"),
                        "input": tool.get("arguments", {})
                    } 
                    content = [{"toolUse": tool_use}]
                elif msg.function_call_id:
                    # 工具调用消息
                    result = json.loads(msg.content)
                    tool_result = {}
                    if result.get("error"):
                        tool_result = {
                            "toolUseId": msg.function_call_id,
                            "content": [{"text": result.get("error", "未知错误")}],
                            "status": "error"
                        }
                    else:
                        tool_result = {
                            "toolUseId": msg.function_call_id,
                            "content": [{"json": json.loads(result.get("result", {}))}],
                            "status": "success"
                        }
                    content = [{"toolResult": tool_result}]
                else:    
                    content = [{"text": msg.content}]
                formatted.append({
                    "role": msg.role.value,
                    "content": content
                })
        return FormatMessages(
            messages=formatted,
            system=system
        )
        
    def _prepare_config(self) -> Dict:
        """准备请求体"""
        config = self.config
        return {
            "maxTokens": config.max_tokens or 6144,
            "temperature": config.temperature,
            "topP": config.top_p,
        }

    def _perpare_tools(self, functions: Optional[List[Function]]) -> Optional[Dict]:
        """准备工具配置
        
        将 Tool 对象转换为 Bedrock toolSpec 格式
        """
        if not functions:
            return None
            
        tools = []
        for func in functions:
            tool_spec = {
                "toolSpec": {
                    "name": func.name,
                    "description": func.description,
                    "inputSchema": {
                        "json": {
                            "type": "object",
                            "properties": func.parameters,
                            "required": [
                                k for k, v in func.parameters.items() 
                                if v.get("default") is None
                            ]
                        }
                    }
                }
            }
            tools.append(tool_spec)
        # tools 添加缓存
        tools.append({
            "cachePoint": {
                "type": "default"
            }
        })
        
        return {"tools": tools} if tools else None

    async def generate(
        self,
        prompt: Optional[str] = None,
        messages: Optional[List[Message]] = None,
        system: Optional[str] = None,
        functions: Optional[List[Function]] = None,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """生成回复"""
        if not prompt and not messages:
            raise ValueError("必须提供 prompt 或 messages 参数")
        if messages is None:
            messages = []
        if prompt:
            messages.append(Message(role=LLMRole.USER, content=prompt))
        if system:
            messages.append(Message(role=LLMRole.SYSTEM, content=system))
            
        async for chunk in self.chat(messages, functions, **kwargs):
            yield chunk

    async def chat(
        self,
        messages: List[Message],
        functions: Optional[List[Function]] = None,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """对话模式"""
        try:
            formatted_messages = self._format_messages(messages)
            inference_config = self._prepare_config()
            tool_config = self._perpare_tools(functions)
            # print('formatted_messages=====>', formatted_messages.messages)
            # 构建基础请求参数
            request_params = {
                "modelId": self.config.model_id,
                "messages": formatted_messages.messages,
                "inferenceConfig": inference_config
            }

            if formatted_messages.system:
                request_params["system"] = formatted_messages.system
            
            # 如果存在工具配置，则添加到请求参数中
            if tool_config:
                request_params["toolConfig"] = tool_config

            isStream = kwargs.get('stream', self.config.stream)
            if isStream:
                # 流式响应
                response = self.client.converse_stream(**request_params)
                current_tool_use = None
            
                for chunk in response["stream"]:
                    # print('chunk====>', chunk)
                    # 处理消息开始
                    if 'messageStart' in chunk:
                        continue

                    # 处理工具调用
                    if 'contentBlockStart' in chunk:
                        start = chunk['contentBlockStart']['start']
                        if 'toolUse' in start:
                            current_tool_use = start['toolUse']

                    # 处理内容块
                    if 'contentBlockDelta' in chunk:
                        delta = chunk['contentBlockDelta']['delta']
                        if 'toolUse' in delta:
                            current_tool_use['input'] = delta['toolUse'].get('input', {})
                        if 'text' in delta:
                            yield BedrockResponse(
                                text=delta['text'],
                                stop_reason="",
                                tool_call=None
                            )
                    
                    # 处理消息结束
                    if 'messageStop' in chunk:
                        stop_reason = chunk['messageStop']['stopReason']
                        if stop_reason == 'tool_use' and current_tool_use:
                            yield BedrockResponse(
                                text="",
                                stop_reason=stop_reason,
                                tool_call=current_tool_use
                            )
                            current_tool_use = None
                        else:
                            yield BedrockResponse(
                                text="",
                                stop_reason=stop_reason,
                                tool_call=None
                            )  
            else:
                # 非流式响应
                response = await asyncio.to_thread(
                    self.client.converse,
                    **request_params
                )
                message = response['output']['message']
                text = ""
                tool_call = None
                
                # 提取文本内容
                if 'content' in message:
                    for content in message['content']:
                        if 'text' in content:
                            text += content['text']
                        if 'toolUse' in content:
                            tool_call = content['toolUse']    
                
                yield BedrockResponse(
                    text=text,
                    stop_reason=response.get('stopReason'),
                    tool_call=tool_call
                )
                
        except Exception as e:
            logger.error(f"Bedrock API 错误: {str(e)}")
            raise        
    async def function_call(
        self,
        function: Function,
        arguments: Dict[str, Any]
    ) -> AsyncGenerator[str, None]:
        """函数调用"""
        try:
            # 调用父类的函数实现
            async for chunk in super().function_call(function, arguments):
                yield chunk
        except Exception as e:
            logger.error(f"函数调用错误: {str(e)}")
            raise