"""向量数据库 Provider 模块"""

from src.vector_db.providers.base import VectorDBProvider

# 延迟导入,避免循环依赖和 IDE 警告
__all__ = ['VectorDBProvider']


def __getattr__(name):
    """延迟加载 Provider 类"""
    if name == 'ChromaDBProvider':
        from src.vector_db.providers.chromadb import ChromaDBProvider
        return ChromaDBProvider
    elif name == 'MilvusProvider':
        from src.vector_db.providers.milvus import MilvusProvider
        return MilvusProvider
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
