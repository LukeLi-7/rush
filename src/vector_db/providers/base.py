"""向量数据库 Provider 抽象基类"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class Document:
    """文档对象"""
    id: str
    content: str
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class QueryResult:
    """查询结果"""
    documents: List[Document]
    distances: Optional[List[float]] = None
    metadatas: Optional[List[Dict[str, Any]]] = None


class VectorDBProvider(ABC):
    """向量数据库 Provider 抽象基类
    
    所有向量数据库实现都必须继承此类
    """
    
    @abstractmethod
    def initialize(self) -> None:
        """初始化向量数据库连接
        
        Raises:
            Exception: 初始化失败时抛出异常
        """
        pass
    
    @abstractmethod
    def add_documents(self, collection_name: str, documents: List[Document]) -> bool:
        """添加文档到集合
        
        Args:
            collection_name: 集合名称
            documents: 文档列表
            
        Returns:
            bool: 是否成功
        """
        pass
    
    @abstractmethod
    def query(self, 
              collection_name: str, 
              query_text: str, 
              top_k: int = 5) -> QueryResult:
        """查询相似文档
        
        Args:
            collection_name: 集合名称
            query_text: 查询文本
            top_k: 返回结果数量
            
        Returns:
            QueryResult: 查询结果
        """
        pass
    
    @abstractmethod
    def delete_collection(self, collection_name: str) -> bool:
        """删除集合
        
        Args:
            collection_name: 集合名称
            
        Returns:
            bool: 是否成功
        """
        pass
    
    @abstractmethod
    def list_collections(self) -> List[str]:
        """列出所有集合
        
        Returns:
            List[str]: 集合名称列表
        """
        pass
    
    @abstractmethod
    def get_provider_name(self) -> str:
        """获取 Provider 名称
        
        Returns:
            str: Provider 名称
        """
        pass
    
    @abstractmethod
    def close(self) -> None:
        """关闭数据库连接"""
        pass
