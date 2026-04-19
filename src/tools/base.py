"""工具基类"""

from abc import ABC, abstractmethod
from typing import Dict, Any


class Tool(ABC):
    """工具基类"""
    
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
    
    @abstractmethod
    def execute(self, *args, **kwargs) -> str:
        """执行工具
        
        Returns:
            str: 工具执行结果
        """
        raise NotImplementedError
    
    @abstractmethod
    def get_schema(self) -> Dict[str, Any]:
        """获取工具的 Function Calling schema
        
        Returns:
            Dict: OpenAI 格式的工具定义
        """
        pass
    
    def __repr__(self):
        return f"Tool(name='{self.name}', description='{self.description}')"
