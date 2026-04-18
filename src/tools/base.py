"""工具基类"""

from abc import ABC, abstractmethod


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
    
    def __repr__(self):
        return f"Tool(name='{self.name}', description='{self.description}')"
