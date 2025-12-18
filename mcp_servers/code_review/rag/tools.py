import logging
from typing import List, Dict, Optional, Any, Union, TypeVar
from dataclasses import dataclass, field, asdict
from ..configs.config_manager import get_global_variable_config

from .request import RequestClient, RequestConfig

logger = logging.getLogger('RAGClient')
T = TypeVar('T')

# 讀取配置文件
global_config = get_global_variable_config()
BASE_URL = global_config['dify']['base_url']
API_KEY = global_config['dify']['api_key']

@dataclass
class RerankingModel:
    """重排序模型配置"""
    reranking_provider_name: str = ""
    reranking_model_name: str = ""

@dataclass
class RetrievalModel:
    """检索模型配置"""
    query: str = ""
    search_method: str = "keyword_search"
    reranking_enable: bool = False
    reranking_mode: Optional[str] = None
    reranking_model: RerankingModel = field(default_factory=RerankingModel)
    weights: Optional[Dict[str, float]] = None
    top_k: int = 1
    score_threshold_enabled: bool = False
    score_threshold: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """将对象转换为字典,适用于API请求"""
        result = asdict(self)
        return result

@dataclass
class SegmentContent:
    """文档分段内容"""
    content: str
    answer: Optional[str] = None
    keywords: List[str] = field(default_factory=list)
    enabled: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        """将对象转换为字典,适用于API请求"""
        return asdict(self)

@dataclass
class Segment:
    """文档分段"""
    content: str
    answer: Optional[str] = None
    keywords: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """将对象转换为字典,适用于API请求"""
        return asdict(self)

class RAGClient:
    """
    RAG功能客户端,提供知识库检索和文档分段管理功能
    
    主要功能:
    - 检索知识库: retrieve()
    - 更新文档分段: update_segment()
    - 删除文档分段: delete_segment()
    """
    
    BASE_URL = BASE_URL
    API_KEY = API_KEY
    
    def __init__(
        self,
        base_url: str = None,
        config: Optional[RequestConfig] = None
    ):
        headers = {"Authorization": f"Bearer {self.API_KEY}"}
        if config:
            if hasattr(config, 'headers') and config.headers:
                config.headers.update(headers)
            else:
                config.headers = headers
        else:
            config = RequestConfig(headers=headers)
            
        self.client = RequestClient(base_url or self.BASE_URL, config)
        logger.info(f"RAGClient已初始化,基础URL: {base_url or self.BASE_URL}")
    
    async def close(self) -> None:
        await self.client.close()
    
    async def __aenter__(self) -> "RAGClient":
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()
    
    async def retrieve(
        self,
        dataset_id: str,
        retrieval_model: Optional[RetrievalModel] = None
    ) -> Dict[str, Any]:
        """
        检索知识库
        Args:
            dataset_id: 知识库ID
            retrieval_model: 检索模型配置，不提供则使用默认配置  
        Returns:
            检索结果，包含查询信息和匹配的文档段落
            ```json
            {
              "query": {
            "content": "test"
              },
              "records": [
            {
              "segment": {
                "id": "7fa6f24f-8679-48b3-bc9d-bdf28d73f218",
                "position": 1,
                "document_id": "a8c6c36f-9f5d-4d7a-8472-f5d7b75d71d2",
                "content": "Operation guide",
                "answer": null,
                "word_count": 847,
                "tokens": 280,
                "keywords": [
                  "install",
                  "java",
                  "base",
                  "scripts",
                  "jdk",
                  "manual",
                  "internal",
                  "opens",
                  "add",
                  "vmoptions"
                ],
                "index_node_id": "39dd8443-d960-45a8-bb46-7275ad7fbc8e",
                "index_node_hash": "0189157697b3c6a418ccf8264a09699f25858975578f3467c76d6bfc94df1d73",
                "hit_count": 0,
                "enabled": true,
                "disabled_at": null,
                "disabled_by": null,
                "status": "completed",
                "created_by": "dbcb1ab5-90c8-41a7-8b78-73b235eb6f6f",
                "created_at": 1728734540,
                "indexing_at": 1728734552,
                "completed_at": 1728734584,
                "error": null,
                "stopped_at": null,
                "document": {
                  "id": "a8c6c36f-9f5d-4d7a-8472-f5d7b75d71d2",
                  "data_source_type": "upload_file",
                  "name": "readme.txt",
                  "doc_type": null
                }
              },
              "score": 3.730463140527718e-05,
              "tsne_position": null
            }
              ]
            }
            ```  
        Example:
            ```python
            async with RAGClient() as rag:
                results = await rag.retrieve(
                    dataset_id="dataset_id",
                    retrieval_model=RetrievalModel(query="code review")
                )
            ```
        """
        model = retrieval_model or RetrievalModel()
        payload = {"query": model.query, "retrieval_model": model.to_dict()}
        
        endpoint = f"/datasets/{dataset_id}/retrieve"
        logger.info(f"检索知识库: {dataset_id}, 查询: {model.query}")
        
        res = await self.client.post(endpoint, json_data=payload)
        logger.info(f"检索知识库return: {res}")

        return res
    
    async def update_segment(
        self,
        dataset_id: str,
        document_id: str,
        segment_id: str,
        segment: Union[SegmentContent, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        更新文档分段
        
        Args:
            dataset_id: 知识库ID
            document_id: 文档ID
            segment_id: 分段ID
            segment: 分段内容，可以是SegmentContent对象或字典
            
        Returns:
            更新结果:
            ```json
            {
              "data": [{
            "id": "",
            "position": 1,
            "document_id": "",
            "content": "1",
            "answer": "1",
            "word_count": 25,
            "tokens": 0,
            "keywords": [
              "a"
            ],
            "index_node_id": "",
            "index_node_hash": "",
            "hit_count": 0,
            "enabled": true,
            "disabled_at": null,
            "disabled_by": null,
            "status": "completed",
            "created_by": "",
            "created_at": 1695312007,
            "indexing_at": 1695312007,
            "completed_at": 1695312007,
            "error": null,
            "stopped_at": null
              }],
              "doc_form": "text_model"
            }
            ```
            
        Example:
            ```python
            segment = SegmentContent(
            content="文本内容/问题内容，必填",
            answer="答案内容，非必填，如果知识库的模式为 Q&A 模式则传值",
            keywords=["react", "redux", "next"],
            enabled=True
            )
            
            async with RAGClient("/datasets/{dataset_id}/documents/{document_id}/segments/{segment_id}") as rag:
            result = await rag.update_segment(
                dataset_id="dataset_id",
                document_id="document_id", 
                segment_id="segment_id",
                segment=segment
            )
            ```
        """
        segment_data = segment.to_dict() if isinstance(segment, SegmentContent) else segment
        payload = {"segment": segment_data}
        
        endpoint = f"/datasets/{dataset_id}/documents/{document_id}/segments/{segment_id}"
        logger.info(f"更新文档分段，知识库: {dataset_id}，文档: {document_id}，分段: {segment_id}")
        
        return await self.client.post(endpoint, json_data=payload)
    
    async def delete_segment(
        self,
        dataset_id: str,
        document_id: str,
        segment_id: str
    ) -> Dict[str, Any]:
        """
        删除文档分段
        
        Args:
            dataset_id: 知识库ID
            document_id: 文档ID
            segment_id: 分段ID
            
        Returns:
            删除结果：
            ```json
            {
                "result": "success"
            }
            ```
            
        Example:
            ```python
            async with RAGClient("/datasets/{dataset_id}/documents/{document_id}/segments/{segment_id}") as rag:
                result = await rag.delete_segment(
                    dataset_id="dataset_id",
                    document_id="document_id", 
                    segment_id="segment_id"
                )
            ```
        """
        endpoint = f"/datasets/{dataset_id}/documents/{document_id}/segments/{segment_id}"
        logger.info(f"删除文档分段，知识库: {dataset_id}，文档: {document_id}，分段: {segment_id}")
        
        return await self.client.delete(endpoint)
    
    async def get_segments(
        self,
        dataset_id: str,
        document_id: str,
        keyword: Optional[str] = None,
        status: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        查询文档分段
        
        Args:
            dataset_id: 知识库ID
            document_id: 文档ID
            keyword: 可选，关键词过滤
            status: 可选，状态过滤
            
        Returns:
            分段列表：
            ```json
            {
              "data": [{
            "id": "",
            "position": 1,
            "document_id": "",
            "content": "1",
            "answer": "1",
            "word_count": 25,
            "tokens": 0,
            "keywords": [
              "a"
            ],
            "index_node_id": "",
            "index_node_hash": "",
            "hit_count": 0,
            "enabled": true,
            "disabled_at": null,
            "disabled_by": null,
            "status": "completed",
            "created_by": "",
            "created_at": 1695312007,
            "indexing_at": 1695312007,
            "completed_at": 1695312007,
            "error": null,
            "stopped_at": null
              }],
              "doc_form": "text_model"
            }
            ```
            
        Example:
            ```python
            async with RAGClient("/datasets/{dataset_id}/documents/{document_id}/segments") as rag:
            segments = await rag.get_segments(
                dataset_id="dataset_id",
                document_id="document_id",
                keyword="keyword"
            )
            ```
        """
        payload = {}
        if keyword is not None:
            payload["keyword"] = keyword
        if status is not None:
            payload["status"] = status
            
        endpoint = f"/datasets/{dataset_id}/documents/{document_id}/segments"
        logger.info(f"查询文档分段，知识库: {dataset_id}，文档: {document_id}")
        
        return await self.client.get(endpoint, json_data=payload)
    
    async def add_segments(
        self,
        dataset_id: str,
        document_id: str,
        segments: List[Union[Segment, Dict[str, Any]]]
    ) -> Dict[str, Any]:
        """
        新增文档分段
        
        Args:
            dataset_id: 知识库ID
            document_id: 文档ID
            segments: 分段列表，可以是Segment对象或字典列表
            
        Returns:
            新增结果：
            ```json
            {
              "data": [{
            "id": "",
            "position": 1,
            "document_id": "",
            "content": "1",
            "answer": "1",
            "word_count": 25,
            "tokens": 0,
            "keywords": [
              "a"
            ],
            "index_node_id": "",
            "index_node_hash": "",
            "hit_count": 0,
            "enabled": true,
            "disabled_at": null,
            "disabled_by": null,
            "status": "completed",
            "created_by": "",
            "created_at": 1695312007,
            "indexing_at": 1695312007,
            "completed_at": 1695312007,
            "error": null,
            "stopped_at": null
              }],
              "doc_form": "text_model"
            }
            ```
            
        Example:
            ```python
            segments = [
            Segment(
                content="P(text) 文本内容/问题内容，必填",
                answer="(text) 答案内容，非必填，如果知识库的模式为 Q&A 模式则传值",
                keywords=(list) 关键字，非必填
            ),
            Segment(
                content="(text) 文本内容/问题内容，必填",
                answer="(text) 答案内容，非必填，如果知识库的模式为 Q&A 模式则传值",
                keywords=(list) 关键字，非必填
            )
            ]
            
            async with RAGClient("/datasets/{dataset_id}/documents/{document_id}/segments") as rag:
            result = await rag.add_segments(
                dataset_id="dataset_id",
                document_id="document_id",
                segments=segments
            )
            ```
        """
        segments_data = [
            segment.to_dict() if hasattr(segment, 'to_dict') else segment
            for segment in segments
        ]
        payload = {"segments": segments_data}
        
        endpoint = f"/datasets/{dataset_id}/documents/{document_id}/segments"
        logger.info(f"新增文档分段，知识库: {dataset_id}，文档: {document_id}，分段数量: {len(segments)}")
        
        return await self.client.post(endpoint, json_data=payload)
    
    async def list_documents(
        self,
        dataset_id: str,
        keyword: Optional[str] = None,
        page: Optional[int] = None,
        limit: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        获取知识库文档列表
        
        Args:
            dataset_id: 知识库ID
            keyword: 可选，关键词过滤
            page: 可选，页码
            limit: 可选，每页数量
            
        Returns:
            文档列表
            ```json
            {
              "data": [
            {
              "id": "",
              "position": 1,
              "data_source_type": "file_upload",
              "data_source_info": null,
              "dataset_process_rule_id": null,
              "name": "dify",
              "created_from": "",
              "created_by": "",
              "created_at": 1681623639,
              "tokens": 0,
              "indexing_status": "waiting",
              "error": null,
              "enabled": true,
              "disabled_at": null,
              "disabled_by": null,
              "archived": false
            }
              ],
              "has_more": false,
              "limit": 20,
              "total": 9,
              "page": 1
            }
            ```
            
        Example:
            ```python
            async with RAGClient("/datasets/{dataset_id}/documents") as rag:
            documents = await rag.list_documents(
                dataset_id="dataset_id",
                keyword=None,
                page=1,
                limit=10
            )
            ```
        """
        params = {}
        if keyword is not None:
            params["keyword"] = keyword
        if page is not None:
            params["page"] = page
        if limit is not None:
            params["limit"] = limit
            
        endpoint = f"/datasets/{dataset_id}/documents"
        logger.info(f"获取知识库文档列表，知识库: {dataset_id}")
        
        return await self.client.get(endpoint, params=params)

