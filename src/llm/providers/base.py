"""LLM Provider 抽象基类"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class ToolCall:
    """工具调用对象"""
    id: str                    # 工具调用 ID
    name: str                  # 工具名称
    arguments: Dict[str, Any]  # 工具参数


@dataclass
class ChatResponse:
    """聊天响应对象"""
    content: Optional[str]              # 文本内容
    tool_calls: Optional[List[ToolCall]] # 工具调用列表
    
    @property
    def has_tool_calls(self) -> bool:
        """是否有工具调用"""
        return self.tool_calls is not None and len(self.tool_calls) > 0


class LLMProvider(ABC):
    """LLM Provider 抽象基类
    
    所有 LLM 提供者必须实现此接口
    """
    
    @abstractmethod
    def chat(self, messages: List[Dict[str, str]]) -> str:
        """普通聊天(无工具调用)
        
        Args:
            messages: 消息历史列表
            
        Returns:
            str: AI 回复内容
        """
        pass
    
    @abstractmethod
    def chat_with_tools(
        self, 
        messages: List[Dict[str, Any]], 
        tools: List[Dict[str, Any]]
    ) -> ChatResponse:
        """带工具调用的聊天
        
        Args:
            messages: 消息历史列表
            tools: 工具定义列表
            
        Returns:
            ChatResponse: 包含文本或工具调用的响应
        """
        pass
    
    @abstractmethod
    def get_provider_name(self) -> str:
        """获取 Provider 名称
        
        Returns:
            str: Provider 名称
        """
        pass
