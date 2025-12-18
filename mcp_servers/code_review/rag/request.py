import httpx
import logging
import time
import asyncio
from enum import Enum
from typing import Any, Dict, List, Optional, Union, Callable, AsyncGenerator, TypeVar
from urllib.parse import urlparse
import sys
from dataclasses import dataclass, field
from contextlib import asynccontextmanager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout), logging.FileHandler('request.log')]
)
logger = logging.getLogger('RequestClient')

T = TypeVar('T')

class RequestMethod(Enum):
    """HTTP请求方法。"""
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"

# 异常类
class RequestError(Exception):
    """请求错误的基础异常类。"""
    def __init__(self, message: str, status_code: Optional[int] = None, response: Optional[Any] = None):
        self.message = message
        self.status_code = status_code
        self.response = response
        super().__init__(self.message)

class EmptyResponseError(RequestError): """当响应为空时抛出的异常。"""
class NetworkError(RequestError): """网络相关问题抛出的异常。"""
class TimeoutError(RequestError): """请求超时时抛出的异常。"""
class ServerError(RequestError): """服务器错误(5xx)时抛出的异常。"""
class ClientError(RequestError): """客户端错误(4xx)时抛出的异常。"""

@dataclass
class RetryConfig:
    """重试机制的配置。"""
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    retry_status_codes: List[int] = field(default_factory=lambda: [408, 429, 500, 502, 503, 504])
    retry_on_network_errors: bool = True
    jitter: bool = True

@dataclass
class RequestConfig:
    """HTTP请求的配置。"""
    timeout: float = 30.0
    verify_ssl: bool = True
    retry_config: RetryConfig = field(default_factory=RetryConfig)
    follow_redirects: bool = True
    max_redirects: int = 10
    headers: Dict[str, str] = field(default_factory=dict)

class RequestClient:
    """
    HTTP请求客户端,具有高级功能:
    - 空响应验证
    - 高级错误处理
    - 指数退避重试机制
    - 日志记录
    - 流式响应支持
    - 可配置的超时
    - Bearer token认证支持
    """
    
    def __init__(self, base_url: str = "", config: Optional[RequestConfig] = None, api_key: Optional[str] = None):
        """初始化RequestClient。"""
        self.base_url = base_url.rstrip('/') if base_url else ""
        self.config = config or RequestConfig()
        self.api_key = api_key
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.config.timeout,
            verify=self.config.verify_ssl,
            follow_redirects=self.config.follow_redirects,
            max_redirects=self.config.max_redirects,
            headers=self.config.headers
        )
        logger.info(f"RequestClient已初始化,基础URL: {self.base_url}")
    
    async def close(self):
        """关闭HTTP客户端。"""
        await self.client.aclose()
        logger.debug("RequestClient已关闭")
    
    async def __aenter__(self):
        """上下文管理器入口。"""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器退出。"""
        await self.close()
    
    def _calculate_retry_delay(self, retry: int, config: RetryConfig) -> float:
        """计算指数退避延迟时间。"""
        delay = min(config.base_delay * (2 ** retry), config.max_delay)
        return delay * (0.5 + (time.time() % 1)) if config.jitter else delay
    
    def _validate_response(self, response: httpx.Response) -> None:
        """验证HTTP响应状态。"""
        if 400 <= response.status_code < 500:
            raise ClientError(f"客户端错误: {response.status_code}", response.status_code, response)
        elif response.status_code >= 500:
            raise ServerError(f"服务器错误: {response.status_code}", response.status_code, response)
    
    def _validate_empty(self, data: Any) -> None:
        """验证响应数据是否为空。"""
        if data is None or (isinstance(data, (dict, list, str)) and len(data) == 0):
            raise EmptyResponseError("收到空响应")
    
    def _get_full_url(self, url: str) -> str:
        """获取完整URL。"""
        return f"{self.base_url}/{url.lstrip('/')}" if not urlparse(url).netloc and self.base_url else url
    
    def _prepare_headers(self, headers: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """准备请求头，包含Bearer token认证（如果有API key）。"""
        request_headers = dict(self.config.headers)
        if headers:
            request_headers.update(headers)
        if self.api_key:
            request_headers['Authorization'] = f'Bearer {self.api_key}'
        return request_headers
    
    async def request(
        self, 
        method: Union[str, RequestMethod], 
        url: str, 
        *,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Any] = None,
        json_data: Optional[Any] = None,
        files: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
        validate_empty: bool = True,
        retry_config: Optional[RetryConfig] = None
    ) -> Any:
        """发送HTTP请求,包含重试逻辑和错误处理。"""
        if isinstance(method, RequestMethod):
            method = method.value
        
        retry_config = retry_config or self.config.retry_config
        request_timeout = httpx.Timeout(timeout or self.config.timeout)
        full_url = self._get_full_url(url)
        request_headers = self._prepare_headers(headers)
        
        logger.info(f"发送{method}请求到{full_url}")
        if params: logger.debug(f"请求参数: {params}")
        if json_data: logger.debug(f"请求JSON数据: {json_data}")
        if files: logger.debug(f"请求包含文件上传")
        
        retry = 0
        last_error = None
        
        while retry <= retry_config.max_retries:
            try:
                if retry > 0:
                    delay = self._calculate_retry_delay(retry - 1, retry_config)
                    logger.info(f"重试请求(尝试{retry}/{retry_config.max_retries})，延迟{delay:.2f}秒后")
                    await asyncio.sleep(delay)
                
                response = await self.client.request(
                    method=method,
                    url=full_url,
                    params=params,
                    data=data,
                    json=json_data,
                    files=files,
                    headers=request_headers,
                    timeout=request_timeout
                )
                
                # 检查可重试的状态码
                if response.status_code in retry_config.retry_status_codes and retry < retry_config.max_retries:
                    logger.warning(f"收到状态码{response.status_code}，将重试")
                    retry += 1
                    last_error = ServerError(f"服务器错误: {response.status_code}", response.status_code, response)
                    continue
                
                # 验证响应状态
                self._validate_response(response)
                
                # 解析响应
                data = response.json() if "application/json" in response.headers.get("content-type", "") else response.text
                
                # 验证响应是否为空
                if validate_empty:
                    self._validate_empty(data)
                
                logger.info(f"请求成功: {response.status_code}")
                return data
                
            except (httpx.NetworkError, httpx.ConnectError, httpx.ConnectTimeout) as e:
                last_error = NetworkError(f"网络错误: {str(e)}")
                if retry_config.retry_on_network_errors and retry < retry_config.max_retries:
                    logger.warning(f"发生网络错误: {str(e)}，将重试")
                    retry += 1
                    continue
                logger.error(f"网络错误: {str(e)}")
                raise last_error
                
            except httpx.TimeoutException as e:
                last_error = TimeoutError(f"请求超时: {str(e)}")
                if retry < retry_config.max_retries:
                    logger.warning(f"请求超时，将重试")
                    retry += 1
                    continue
                logger.error(f"请求在{retry_config.max_retries}次重试后超时")
                raise last_error
                
            except (ClientError, ServerError, EmptyResponseError) as e:
                last_error = e
                if isinstance(e, ServerError) and retry < retry_config.max_retries:
                    logger.warning(f"服务器错误: {e.message}，将重试")
                    retry += 1
                    continue
                logger.error(f"请求错误: {e.message}")
                raise e
                
            except Exception as e:
                logger.error(f"意外错误: {str(e)}")
                raise RequestError(f"意外错误: {str(e)}")
        
        if last_error:
            logger.error(f"请求在{retry_config.max_retries}次重试后失败: {last_error.message}")
            raise last_error
        
        raise RequestError("请求因未知原因失败")
    
    async def stream(
        self, 
        method: Union[str, RequestMethod], 
        url: str, 
        *,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Any] = None,
        json_data: Optional[Any] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
        chunk_processor: Optional[Callable[[bytes], Any]] = None
    ) -> AsyncGenerator[Any, None]:
        """发送HTTP请求并流式处理响应。"""
        if isinstance(method, RequestMethod):
            method = method.value
        
        request_timeout = httpx.Timeout(timeout or self.config.timeout)
        full_url = self._get_full_url(url)
        request_headers = self._prepare_headers(headers)
        
        logger.info(f"开始流式{method}请求到{full_url}")
        
        try:
            async with self.client.stream(
                method=method,
                url=full_url,
                params=params,
                data=data,
                json=json_data,
                headers=request_headers,
                timeout=request_timeout
            ) as response:
                self._validate_response(response)
                logger.info(f"流连接已建立: {response.status_code}")
                
                async for chunk in response.aiter_bytes():
                    if chunk:
                        yield chunk_processor(chunk) if chunk_processor else chunk
        
        except httpx.NetworkError as e:
            logger.error(f"流式传输中网络错误: {str(e)}")
            raise NetworkError(f"流式传输中网络错误: {str(e)}")
        
        except httpx.TimeoutException as e:
            logger.error(f"流式传输中超时: {str(e)}")
            raise TimeoutError(f"流式传输中超时: {str(e)}")
        
        except Exception as e:
            logger.error(f"流式传输中错误: {str(e)}")
            raise RequestError(f"流式传输中错误: {str(e)}")
    
    # HTTP方法快捷函数
    async def get(self, url: str, **kwargs) -> Any:
        """发送GET请求。"""
        return await self.request(RequestMethod.GET, url, **kwargs)
    
    async def post(self, url: str, **kwargs) -> Any:
        """发送POST请求。"""
        return await self.request(RequestMethod.POST, url, **kwargs)
    
    async def put(self, url: str, **kwargs) -> Any:
        """发送PUT请求。"""
        return await self.request(RequestMethod.PUT, url, **kwargs)
    
    async def delete(self, url: str, **kwargs) -> Any:
        """发送DELETE请求。"""
        return await self.request(RequestMethod.DELETE, url, **kwargs)
    
    async def patch(self, url: str, **kwargs) -> Any:
        """发送PATCH请求。"""
        return await self.request(RequestMethod.PATCH, url, **kwargs)
    
    # 流式请求快捷函数
    async def stream_get(self, url: str, **kwargs) -> AsyncGenerator[Any, None]:
        """流式GET请求。"""
        async for chunk in self.stream(RequestMethod.GET, url, **kwargs):
            yield chunk
    
    async def stream_post(self, url: str, **kwargs) -> AsyncGenerator[Any, None]:
        """流式POST请求。"""
        async for chunk in self.stream(RequestMethod.POST, url, **kwargs):
            yield chunk

# 创建请求上下文管理器
@asynccontextmanager
async def create_client(base_url: str = "", config: Optional[RequestConfig] = None, api_key: Optional[str] = None):
    """创建一个HTTP请求客户端的上下文管理器。"""
    client = RequestClient(base_url, config, api_key)
    try:
        yield client
    finally:
        await client.close()

