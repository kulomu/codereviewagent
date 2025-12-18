"""
RAG (Retrieval Augmented Generation) 模块
提供知识库检索和文档分段管理功能
"""

from .tools import (
    RAGClient,
    RetrievalModel,
    RerankingModel,
    Segment,
    SegmentContent
)

from .request import (
    RequestClient,
    RequestConfig,
    RetryConfig,
    RequestMethod,
    RequestError,
    EmptyResponseError,
    NetworkError,
    TimeoutError,
    ServerError,
    ClientError,
    create_client
)


__all__ = [
    # RAG相关
    'RAGClient',
    'RetrievalModel',
    'RerankingModel',
    'Segment',
    'SegmentContent',
    
    # 请求相关
    'RequestClient',
    'RequestConfig',
    'RetryConfig',
    'RequestMethod',
    'RequestError',
    'EmptyResponseError',
    'NetworkError',
    'TimeoutError',
    'ServerError',
    'ClientError',
    'create_client'
]


__version__ = '0.1.0'
