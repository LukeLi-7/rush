"""
RAG 知识检索工具
让 Agent 可以从向量数据库中检索相关知识
"""

from typing import TYPE_CHECKING, Optional, Dict, Any
from src.tools.base import Tool

if TYPE_CHECKING:
    from src.agent import ReActAgent


class KnowledgeSearchTool(Tool):
    """基于向量数据库的知识检索工具"""
    
    def __init__(self, agent: 'ReActAgent'):
        super().__init__(
            name="knowledge_search",
            description="从知识库中搜索相关信息。用法: knowledge_search(query)"
        )
        self.agent = agent
    
    def execute(self, query: str) -> str:
        """执行知识检索"""
        if not self.agent.vector_db:
            return "错误: 向量数据库未初始化"
        
        try:
            # 在知识库集合中搜索
            results = self.agent.vector_db.query(
                collection_name="knowledge_base",
                query_text=query,
                top_k=3
            )
            
            if not results.documents:
                return "未在知识库中找到相关信息"
            
            # 格式化检索结果
            formatted_results = []
            for i, doc in enumerate(results.documents, 1):
                content = doc.content
                # 如果有元数据,也显示出来
                if doc.metadata and doc.metadata.get('source'):
                    source = doc.metadata['source']
                    formatted_results.append(f"[{i}] {content}\n   来源: {source}")
                else:
                    formatted_results.append(f"[{i}] {content}")
            
            return "\n\n".join(formatted_results)
            
        except Exception as e:
            return f"知识检索失败: {str(e)}"
    
    def get_schema(self) -> Dict[str, Any]:
        """获取工具的 Function Calling schema"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "搜索查询文本,描述你想要查找的知识"
                        }
                    },
                    "required": ["query"]
                }
            }
        }


class KnowledgeAddTool(Tool):
    """向知识库添加文档的工具"""
    
    def __init__(self, agent: 'ReActAgent'):
        super().__init__(
            name="knowledge_add",
            description="向知识库添加知识。用法: knowledge_add(content, source=None)"
        )
        self.agent = agent
    
    def execute(self, content: str, source: Optional[str] = None) -> str:
        """添加知识到向量数据库"""
        if not self.agent.vector_db:
            return "错误: 向量数据库未初始化"
        
        try:
            from src.vector_db.providers.base import Document
            
            # 生成简单的 ID
            import hashlib
            import time
            doc_id = hashlib.md5(f"{content}{time.time()}".encode()).hexdigest()[:12]
            
            metadata = {}
            if source:
                metadata['source'] = source
            
            document = Document(
                id=doc_id,
                content=content,
                metadata=metadata if metadata else None
            )
            
            success = self.agent.vector_db.add_documents(
                collection_name="knowledge_base",
                documents=[document]
            )
            
            if success:
                return f"✓ 知识已添加到知识库 (ID: {doc_id})"
            else:
                return "✗ 添加知识失败"
                
        except Exception as e:
            return f"添加知识失败: {str(e)}"
    
    def get_schema(self) -> Dict[str, Any]:
        """获取工具的 Function Calling schema"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "content": {
                            "type": "string",
                            "description": "要添加到知识库的内容"
                        },
                        "source": {
                            "type": "string",
                            "description": "内容的来源(可选)",
                            "default": None
                        }
                    },
                    "required": ["content"]
                }
            }
        }
