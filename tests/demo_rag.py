#!/usr/bin/env python3
"""
RAG 功能演示
展示如何使用知识检索和添加功能
"""

import sys
import os

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from src.vector_db.providers.chromadb import ChromaDBProvider
from src.vector_db.providers.base import Document


def demo_rag():
    """演示 RAG 功能"""
    
    print("=" * 60)
    print("RAG (检索增强生成) 功能演示")
    print("=" * 60)
    
    # 1. 初始化向量数据库
    print("\n[1] 初始化向量数据库...")
    db = ChromaDBProvider(persist_directory="~/.rush/chromadb_demo")
    db.initialize()
    print(f"✓ 数据库已初始化: {db.get_provider_name()}")
    
    # 2. 添加一些示例知识
    print("\n[2] 添加示例知识到知识库...")
    
    knowledge_items = [
        ("doc_1", "Python 是一种高级编程语言,由 Guido van Rossum 于 1991 年首次发布。", {"source": "维基百科"}),
        ("doc_2", "Python 支持多种编程范式,包括面向对象、函数式和过程式编程。", {"source": "官方文档"}),
        ("doc_3", "虚拟环境是 Python 中隔离项目依赖的重要工具,可以使用 venv 或 conda 创建。", {"source": "最佳实践"}),
        ("doc_4", "pip 是 Python 的包管理工具,用于安装和管理第三方库。", {"source": "Python 教程"}),
    ]
    
    documents = []
    for doc_id, content, metadata in knowledge_items:
        documents.append(Document(
            id=doc_id,
            content=content,
            metadata=metadata
        ))
    
    success = db.add_documents("knowledge_base", documents)
    print(f"✓ 成功添加 {len(documents)} 条知识")
    
    # 3. 执行语义搜索
    print("\n[3] 执行语义搜索测试...")
    
    test_queries = [
        "Python 是什么时候创建的?",
        "如何管理 Python 项目依赖?",
        "Python 支持哪些编程风格?"
    ]
    
    for query in test_queries:
        print(f"\n  查询: '{query}'")
        results = db.query("knowledge_base", query, top_k=2)
        
        if results.documents:
            print(f"  找到 {len(results.documents)} 个相关结果:")
            for i, doc in enumerate(results.documents, 1):
                print(f"    [{i}] {doc.content}")
                if doc.metadata and 'source' in doc.metadata:
                    print(f"        来源: {doc.metadata['source']}")
                if results.distances:
                    print(f"        相似度距离: {results.distances[i-1]:.4f}")
        else:
            print("  未找到相关结果")
    
    # 4. 列出所有集合
    print("\n[4] 查看所有集合...")
    collections = db.list_collections()
    print(f"  集合列表: {collections}")
    
    # 5. 清理演示数据
    print("\n[5] 清理演示数据...")
    db.delete_collection("knowledge_base")
    print("✓ 演示集合已删除")
    
    print("\n" + "=" * 60)
    print("演示完成!")
    print("=" * 60)


if __name__ == "__main__":
    try:
        demo_rag()
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
