"""ChromaDB 向量数据库 Provider 实现"""

import os
from typing import List, Dict, Any, Optional
from src.vector_db.providers.base import VectorDBProvider, Document, QueryResult


class ChromaDBProvider(VectorDBProvider):
    """ChromaDB 向量数据库实现
    
    使用本地持久化存储,数据保存在指定目录
    """
    
    def __init__(self, persist_directory: str = None):
        """初始化 ChromaDB Provider
        
        Args:
            persist_directory: 持久化目录路径,默认为 ~/.rush/chromadb
        """
        if persist_directory is None:
            persist_directory = os.path.expanduser("~/.rush/chromadb")
        
        self.persist_directory = persist_directory
        self.client = None
        self.embedding_function = None
    
    def initialize(self) -> None:
        """初始化 ChromaDB 连接"""
        try:
            import chromadb
            
            print("正在创建 ChromaDB 客户端...")
            # 创建持久化客户端
            self.client = chromadb.PersistentClient(
                path=self.persist_directory
            )
            
            # 使用轻量级嵌入函数(不需要下载模型,不会卡住)
            self.embedding_function = SimpleEmbeddingFunction()
            print(f"✓ ChromaDB 初始化成功 (持久化目录: {self.persist_directory})")
            
            # 确保目录存在
            os.makedirs(self.persist_directory, exist_ok=True)
            
        except ImportError:
            raise ImportError(
                "ChromaDB 未安装,请运行: pip install chromadb"
            )
        except Exception as e:
            raise Exception(f"ChromaDB 初始化失败: {str(e)}")
    
    def add_documents(self, collection_name: str, documents: List[Document]) -> bool:
        """添加文档到集合"""
        try:
            # 获取或创建集合
            collection = self.client.get_or_create_collection(
                name=collection_name,
                embedding_function=self.embedding_function
            )
            
            # 准备数据
            ids = [doc.id for doc in documents]
            texts = [doc.content for doc in documents]
            metadatas = [doc.metadata or {} for doc in documents]
            
            # 添加到集合
            collection.add(
                ids=ids,
                documents=texts,
                metadatas=metadatas
            )
            
            return True
            
        except Exception as e:
            print(f"添加文档失败: {str(e)}")
            return False
    
    def query(self, 
              collection_name: str, 
              query_text: str, 
              top_k: int = 5) -> QueryResult:
        """查询相似文档"""
        try:
            # 获取集合
            collection = self.client.get_collection(
                name=collection_name,
                embedding_function=self.embedding_function
            )
            
            # 执行查询
            results = collection.query(
                query_texts=[query_text],
                n_results=top_k
            )
            
            # 解析结果
            documents = []
            distances = results.get('distances', [[]])[0]
            metadatas = results.get('metadatas', [[]])[0]
            docs = results.get('documents', [[]])[0]
            ids = results.get('ids', [[]])[0]
            
            for i, (doc_id, content) in enumerate(zip(ids, docs)):
                document = Document(
                    id=doc_id,
                    content=content,
                    metadata=metadatas[i] if i < len(metadatas) else None
                )
                documents.append(document)
            
            return QueryResult(
                documents=documents,
                distances=distances,
                metadatas=metadatas
            )
            
        except Exception as e:
            print(f"查询失败: {str(e)}")
            return QueryResult(documents=[])
    
    def delete_collection(self, collection_name: str) -> bool:
        """删除集合"""
        try:
            self.client.delete_collection(name=collection_name)
            return True
        except Exception as e:
            print(f"删除集合失败: {str(e)}")
            return False
    
    def list_collections(self) -> List[str]:
        """列出所有集合"""
        try:
            collections = self.client.list_collections()
            return [col.name for col in collections]
        except Exception as e:
            print(f"列出集合失败: {str(e)}")
            return []
    
    def get_provider_name(self) -> str:
        """获取 Provider 名称"""
        return "ChromaDB"
    
    def close(self) -> None:
        """关闭数据库连接"""
        # ChromaDB PersistentClient 不需要显式关闭
        self.client = None
        self.embedding_function = None


class SimpleEmbeddingFunction:
    """轻量级嵌入函数 - 无需下载模型
    
    使用词频哈希方法,比纯文本长度更准确
    优点:
    - 不需要安装 torch/sentence-transformers (节省 ~2GB)
    - 不需要下载模型文件 (不会卡住)
    - 启动速度快
    - 有一定的语义区分能力
    """
    
    def __init__(self, dim: int = 384):
        """初始化"""
        self.dim = dim
    
    def name(self) -> str:
        """返回嵌入函数名称 (ChromaDB 要求是方法)"""
        return "simple-embedding-function"
    
    def _text_to_vector(self, text: str) -> List[float]:
        """将文本转换为向量"""
        import re
        words = re.findall(r'\w+', text.lower())
        
        word_freq = {}
        for word in words:
            word_freq[word] = word_freq.get(word, 0) + 1
        
        embedding = [0.0] * self.dim
        
        for word, freq in word_freq.items():
            hash_val = hash(word) % self.dim
            embedding[hash_val] += freq
        
        norm = sum(x**2 for x in embedding) ** 0.5
        if norm > 0:
            embedding = [x / norm for x in embedding]
        
        return embedding
    
    def __call__(self, input: List[str]) -> List[List[float]]:
        """生成嵌入向量 (ChromaDB 要求参数名为 input)"""
        embeddings = []
        for text in input:
            embedding = self._text_to_vector(text)
            embeddings.append(embedding)
        return embeddings
    
    def embed_query(self, input: List[str]) -> List[List[float]]:
        """为查询文本生成嵌入 (ChromaDB 查询时需要)"""
        return self.__call__(input)
