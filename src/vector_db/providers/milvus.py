"""Milvus 向量数据库 Provider 实现"""

from typing import List, Dict, Any, Optional
from src.vector_db.providers.base import VectorDBProvider, Document, QueryResult


class MilvusProvider(VectorDBProvider):
    """Milvus 向量数据库实现
    
    支持本地 Docker 部署和云端 Milvus
    参考: https://milvus.io/docs
    """
    
    def __init__(self, 
                 host: str = "localhost",
                 port: str = "19530",
                 collection_name: str = "rush_knowledge",
                 embedding_dim: int = 384):
        """初始化 Milvus Provider
        
        Args:
            host: Milvus 服务器地址,默认 localhost
            port: Milvus 端口,默认 19530
            collection_name: 默认集合名称
            embedding_dim: 向量维度,默认 384
        """
        self.host = host
        self.port = port
        self.collection_name = collection_name
        self.embedding_dim = embedding_dim
        
        self.client = None
        self.collection = None
        self.embedding_function = None
    
    def initialize(self) -> None:
        """初始化 Milvus 连接"""
        try:
            from pymilvus import connections, Collection, utility
            
            print(f"正在连接到 Milvus ({self.host}:{self.port})...")
            
            # 连接到 Milvus
            connections.connect(
                alias="default",
                host=self.host,
                port=self.port
            )
            
            # 检查连接
            if not utility.has_collection(self.collection_name):
                print(f"创建集合: {self.collection_name}")
                self._create_collection()
            else:
                print(f"使用现有集合: {self.collection_name}")
                self.collection = Collection(self.collection_name)
                self.collection.load()
            
            # 初始化嵌入函数
            self.embedding_function = SimpleEmbeddingFunction(dim=self.embedding_dim)
            
            print(f"✓ Milvus 初始化成功 ({self.host}:{self.port})")
            
        except ImportError:
            raise ImportError(
                "pymilvus 未安装,请运行: pip install pymilvus"
            )
        except Exception as e:
            raise Exception(f"Milvus 初始化失败: {str(e)}\n请确保 Milvus 服务正在运行")
    
    def _create_collection(self):
        """创建 Milvus 集合"""
        from pymilvus import Collection, FieldSchema, CollectionSchema, DataType
        
        # 定义字段
        fields = [
            FieldSchema(name="id", dtype=DataType.VARCHAR, max_length=100, is_primary=True),
            FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=65535),
            FieldSchema(name="metadata", dtype=DataType.JSON),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=self.embedding_dim)
        ]
        
        # 创建 schema
        schema = CollectionSchema(
            fields=fields,
            description="Rush knowledge base collection"
        )
        
        # 创建集合
        self.collection = Collection(name=self.collection_name, schema=schema)
        
        # 创建索引
        index_params = {
            "metric_type": "COSINE",
            "index_type": "IVF_FLAT",
            "params": {"nlist": 128}
        }
        self.collection.create_index(field_name="embedding", index_params=index_params)
        
        # 加载集合到内存
        self.collection.load()
    
    def add_documents(self, collection_name: str, documents: List[Document]) -> bool:
        """添加文档到集合"""
        try:
            # 如果集合名不同,切换集合
            if collection_name != self.collection_name:
                self._switch_collection(collection_name)
            
            # 准备数据
            ids = [doc.id for doc in documents]
            contents = [doc.content for doc in documents]
            metadatas = [doc.metadata or {} for doc in documents]
            
            # 生成嵌入向量
            embeddings = self.embedding_function([doc.content for doc in documents])
            
            # 插入数据
            entities = [
                ids,
                contents,
                metadatas,
                embeddings
            ]
            
            self.collection.insert(entities)
            self.collection.flush()
            
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
            # 如果集合名不同,切换集合
            if collection_name != self.collection_name:
                self._switch_collection(collection_name)
            
            # 生成查询向量
            query_embedding = self.embedding_function([query_text])[0]
            
            # 执行搜索
            search_params = {
                "metric_type": "COSINE",
                "params": {"nprobe": 10}
            }
            
            results = self.collection.search(
                data=[query_embedding],
                anns_field="embedding",
                param=search_params,
                limit=top_k,
                output_fields=["content", "metadata"]
            )
            
            # 解析结果
            documents = []
            distances = []
            metadatas = []
            
            for hit in results[0]:
                document = Document(
                    id=hit.id,
                    content=hit.entity.get("content", ""),
                    metadata=hit.entity.get("metadata", {})
                )
                documents.append(document)
                distances.append(hit.distance)
                metadatas.append(hit.entity.get("metadata", {}))
            
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
            from pymilvus import utility
            
            if utility.has_collection(collection_name):
                utility.drop_collection(collection_name)
                
                # 如果删除的是当前集合,重置
                if collection_name == self.collection_name:
                    self.collection = None
            
            return True
        except Exception as e:
            print(f"删除集合失败: {str(e)}")
            return False
    
    def list_collections(self) -> List[str]:
        """列出所有集合"""
        try:
            from pymilvus import utility
            return utility.list_collections()
        except Exception as e:
            print(f"列出集合失败: {str(e)}")
            return []
    
    def get_provider_name(self) -> str:
        """获取 Provider 名称"""
        return "Milvus"
    
    def close(self) -> None:
        """关闭数据库连接"""
        try:
            from pymilvus import connections
            connections.disconnect("default")
        except:
            pass
        
        self.client = None
        self.collection = None
        self.embedding_function = None
    
    def _switch_collection(self, collection_name: str):
        """切换到指定集合"""
        from pymilvus import Collection, utility
        
        if not utility.has_collection(collection_name):
            # 创建新集合
            old_collection_name = self.collection_name
            self.collection_name = collection_name
            self._create_collection()
        else:
            self.collection_name = collection_name
            self.collection = Collection(collection_name)
            self.collection.load()


class SimpleEmbeddingFunction:
    """轻量级嵌入函数 - 无需下载模型
    
    使用词频哈希方法生成向量
    """
    
    def __init__(self, dim: int = 384):
        """初始化
        
        Args:
            dim: 向量维度
        """
        self.dim = dim
    
    def __call__(self, texts: List[str]) -> List[List[float]]:
        """生成嵌入向量
        
        Args:
            texts: 文本列表
            
        Returns:
            List[List[float]]: 嵌入向量列表
        """
        import re
        
        embeddings = []
        for text in texts:
            # 分词并统计词频
            words = re.findall(r'\w+', text.lower())
            word_freq = {}
            for word in words:
                word_freq[word] = word_freq.get(word, 0) + 1
            
            # 生成向量
            embedding = [0.0] * self.dim
            for word, freq in word_freq.items():
                hash_val = hash(word) % self.dim
                embedding[hash_val] += freq
            
            # 归一化
            norm = sum(x**2 for x in embedding) ** 0.5
            if norm > 0:
                embedding = [x / norm for x in embedding]
            
            embeddings.append(embedding)
        
        return embeddings
