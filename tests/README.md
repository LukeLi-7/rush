# 测试和演示脚本

本目录包含 Rush 项目的测试脚本和演示程序。

## 测试脚本

### test_vectordb.py
测试 ChromaDB 向量数据库的基本功能:
- 初始化数据库
- 添加文档
- 查询相似文档
- 列出集合
- 删除集合

**运行方式:**
```bash
python tests/test_vectordb.py
```

### test_rag_agent.py
端到端测试 Agent 的 RAG 功能:
- 初始化 Agent 和向量数据库
- 添加测试知识
- 测试知识检索
- 验证工具注册

**运行方式:**
```bash
python tests/test_rag_agent.py
```

## 演示脚本

### demo_rag.py
演示 RAG (检索增强生成) 的完整工作流程:
- 创建向量数据库
- 添加示例知识
- 执行语义搜索
- 展示搜索结果

**运行方式:**
```bash
python tests/demo_rag.py
```

## 注意事项

1. 所有测试脚本都会自动清理测试数据
2. 测试数据存储在 `~/.rush/test_chromadb` 或 `~/.rush/chromadb_demo`
3. 确保已安装依赖: `pip install -r requirements.txt`
4. 确保配置文件 `~/.rush/config.json` 已正确配置
