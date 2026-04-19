#!/usr/bin/env python3
"""
RAG 端到端测试
测试 Agent 如何使用 RAG 工具
"""

import sys
import os

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from src.agent import ReActAgent


def test_rag_with_agent():
    """测试 Agent 的 RAG 功能"""
    
    print("=" * 60)
    print("RAG 端到端测试")
    print("=" * 60)
    
    # 1. 初始化 Agent
    print("\n[1] 初始化 Agent...")
    agent = ReActAgent()
    
    if not agent.vector_db:
        print("✗ 向量数据库未初始化,无法测试 RAG")
        return
    
    print(f"✓ Agent 已初始化")
    print(f"  Provider: {agent.provider.get_provider_name()}")
    print(f"  Vector DB: {agent.vector_db.get_provider_name()}")
    print(f"  可用工具: {list(agent.tools.keys())}")
    
    # 2. 先手动添加一些知识
    print("\n[2] 向知识库添加测试数据...")
    from src.vector_db.providers.base import Document
    
    test_knowledge = [
        Document(
            id="test_1",
            content="Rush 是一个基于 ReAct 框架的 AI Agent CLI 工具,支持 Function Calling。",
            metadata={"source": "项目文档"}
        ),
        Document(
            id="test_2",
            content="ReAct 框架结合了推理(Reasoning)和行动(Action),让 AI Agent 能够使用工具解决问题。",
            metadata={"source": "AI 论文"}
        ),
        Document(
            id="test_3",
            content="ChromaDB 是一个轻量级的向量数据库,支持本地持久化存储。",
            metadata={"source": "技术文档"}
        )
    ]
    
    success = agent.vector_db.add_documents("knowledge_base", test_knowledge)
    if success:
        print(f"✓ 成功添加 {len(test_knowledge)} 条测试知识")
    else:
        print("✗ 添加知识失败")
        return
    
    # 3. 测试知识检索
    print("\n[3] 测试知识检索...")
    query = "Rush 是什么?"
    print(f"  查询: '{query}'")
    
    results = agent.vector_db.query("knowledge_base", query, top_k=2)
    if results.documents:
        print(f"  ✓ 找到 {len(results.documents)} 个相关结果:")
        for i, doc in enumerate(results.documents, 1):
            print(f"    [{i}] {doc.content}")
    else:
        print("  ✗ 未找到相关结果")
    
    # 4. 列出集合
    print("\n[4] 查看知识库状态...")
    collections = agent.vector_db.list_collections()
    print(f"  集合列表: {collections}")
    
    # 5. 清理测试数据
    print("\n[5] 清理测试数据...")
    agent.vector_db.delete_collection("knowledge_base")
    print("✓ 测试完成!")
    
    print("\n" + "=" * 60)
    print("提示: 现在可以运行 'python main.py' 与 Agent 对话")
    print("      尝试问: 'Rush 是什么?' 或 '什么是 ReAct 框架?'")
    print("=" * 60)


if __name__ == "__main__":
    try:
        test_rag_with_agent()
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
