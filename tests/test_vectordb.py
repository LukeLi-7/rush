#!/usr/bin/env python3
"""测试 ChromaDB 向量数据库"""

import sys
import os

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from src.vector_db.providers.chromadb import ChromaDBProvider
from src.vector_db.providers.base import Document

def test_chromadb():
    """测试 ChromaDB 基本功能"""
    print("="*60)
    print("测试 ChromaDB 向量数据库")
    print("="*60)
    
    # 1. 初始化
    print("\n1. 初始化 ChromaDB...")
    db = ChromaDBProvider(persist_directory="~/.rush/test_chromadb")
    db.initialize()
    print(f"   ✓ Provider: {db.get_provider_name()}")
    print(f"   ✓ 持久化目录: {db.persist_directory}")
    
    # 2. 添加文档
    print("\n2. 添加测试文档...")
    documents = [
        Document(id="doc1", content="Python 是一门流行的编程语言", metadata={"source": "test"}),
        Document(id="doc2", content="ReAct 框架用于构建 AI Agent", metadata={"source": "test"}),
        Document(id="doc3", content="ChromaDB 是向量数据库", metadata={"source": "test"})
    ]
    
    success = db.add_documents("test_collection", documents)
    print(f"   {'✓' if success else '✗'} 添加文档: {success}")
    
    # 3. 查询文档
    print("\n3. 查询相似文档...")
    results = db.query("test_collection", "Python 编程", top_k=2)
    print(f"   ✓ 找到 {len(results.documents)} 个结果:")
    for i, doc in enumerate(results.documents, 1):
        print(f"      {i}. {doc.content[:50]}...")
        if results.distances:
            print(f"         距离: {results.distances[i-1]:.4f}")
    
    # 4. 列出集合
    print("\n4. 列出所有集合...")
    collections = db.list_collections()
    print(f"   ✓ 集合列表: {collections}")
    
    # 5. 清理
    print("\n5. 清理测试数据...")
    db.delete_collection("test_collection")
    print("   ✓ 删除测试集合")
    
    # 关闭连接
    db.close()
    
    print("\n" + "="*60)
    print("✓ 所有测试通过!")
    print("="*60)

if __name__ == "__main__":
    try:
        test_chromadb()
    except Exception as e:
        print(f"\n✗ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
