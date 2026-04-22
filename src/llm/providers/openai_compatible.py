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
    
    def __init__(self, api_key: str, base_url: str, model: str, timeout: int = 30):
        """初始化 Provider
        
        Args:
            api_key: API Key
            base_url: API 基础 URL
            model: 模型名称
            timeout: 请求超时时间(秒),默认 30 秒
        """
        from openai import OpenAI, Timeout
        
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=Timeout(timeout=timeout, connect=10.0)
        )
        self.model = model
        self.timeout = timeout
    
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
        """带工具调用的聊天"""
        import time
        import threading
        
        # 启动倒计时线程
        stop_event = threading.Event()
        timeout_occurred = [False]  # 使用列表以便在闭包中修改
        
        def countdown():
            remaining = self.timeout
            while remaining > 0 and not stop_event.is_set():
                msg = f"\r正在调用 LLM... 剩余 {remaining:2d}s   "
                print(msg, end='', flush=True)
                time.sleep(1)
                remaining -= 1
            if not stop_event.is_set():
                timeout_occurred[0] = True
                print("\r正在调用 LLM... 超时!     ", flush=True)
        
        timer_thread = threading.Thread(target=countdown, daemon=True)
        timer_thread.start()
        
        try:
            # 调用 API
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=tools,
                tool_choice="auto"
            )
            
            # 停止倒计时
            stop_event.set()
            timer_thread.join(timeout=0.5)
            print("\r✓ LLM 响应成功              ")
            
        except Exception as e:
            stop_event.set()
            timer_thread.join(timeout=0.5)
            
            error_msg = str(e)
            if "timeout" in error_msg.lower() or "timed out" in error_msg.lower() or timeout_occurred[0]:
                raise TimeoutError(f"LLM 请求超时 ({self.timeout}秒),请检查网络连接或增加超时时间")
            elif "connection" in error_msg.lower():
                raise ConnectionError(f"无法连接到 LLM 服务: {error_msg}")
            else:
                raise Exception(f"LLM 调用失败: {error_msg}")
        
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
