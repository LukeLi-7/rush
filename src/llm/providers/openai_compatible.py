"""OpenAI 兼容的 LLM Provider

支持: OpenAI, DeepSeek, Qwen(通义千问) 等兼容 OpenAI API 格式的模型
"""

import json
from typing import List, Dict, Any

from openai import OpenAI

from src.llm.providers.base import LLMProvider, ChatResponse, ToolCall


class OpenAICompatibleProvider(LLMProvider):
    """OpenAI 兼容的 LLM Provider
    
    适用于所有兼容 OpenAI API 格式的服务商
    """
    
    def __init__(self, api_key: str, base_url: str, model: str):
        """初始化 Provider
        
        Args:
            api_key: API Key
            base_url: API 基础 URL
            model: 模型名称
        """
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url
        )
        self.model = model
    
    def chat(self, messages: List[Dict[str, str]]) -> str:
        """普通聊天
        
        Args:
            messages: 消息历史
            
        Returns:
            str: AI 回复
        """
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages
        )
        return response.choices[0].message.content or ""
    
    def chat_with_tools(
        self, 
        messages: List[Dict[str, Any]], 
        tools: List[Dict[str, Any]]
    ) -> ChatResponse:
        """带工具调用的聊天
        
        Args:
            messages: 消息历史
            tools: 工具定义列表
            
        Returns:
            ChatResponse: 响应对象
        """
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=tools,
            tool_choice="auto"
        )
        
        message = response.choices[0].message
        
        # 检查是否有工具调用
        if message.tool_calls:
            tool_calls = []
            for tc in message.tool_calls:
                tool_call = ToolCall(
                    id=tc.id,
                    name=tc.function.name,
                    arguments=json.loads(tc.function.arguments)
                )
                tool_calls.append(tool_call)
            
            return ChatResponse(
                content=message.content,
                tool_calls=tool_calls
            )
        else:
            # 没有工具调用,直接返回文本
            return ChatResponse(
                content=message.content,
                tool_calls=None
            )
    
    def get_provider_name(self) -> str:
        """获取 Provider 名称"""
        return f"OpenAI-Compatible ({self.model})"
