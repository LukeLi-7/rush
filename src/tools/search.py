"""搜索工具"""

from typing import Dict, Any

from src.tools.base import Tool


class SearchTool(Tool):
    """搜索工具 - 搜索信息(模拟)"""
    
    def __init__(self):
        super().__init__(
            name="search",
            description="搜索信息。用法: search(query), 例如 search('Python ReAct 框架')"
        )
    
    def execute(self, query: str) -> str:
        """执行搜索
        
        Args:
            query: 搜索查询字符串
            
        Returns:
            str: 搜索结果
        """
        # 这里可以集成真实的搜索引擎 API
        return f"[搜索结果] 关于 '{query}' 的信息: (这是一个模拟搜索结果)"
    
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
                            "description": "搜索关键词或问题"
                        }
                    },
                    "required": ["query"]
                }
            }
        }
