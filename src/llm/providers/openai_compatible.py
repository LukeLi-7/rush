"""OpenAI 兼容的 LLM Provider

支持: OpenAI, DeepSeek, Qwen(通义千问) 等兼容 OpenAI API 格式的模型
"""

import json
import time
import threading
from typing import List, Dict, Any, Optional

from openai import OpenAI

from src.llm.providers.base import LLMProvider, ChatResponse, ToolCall
from src.error_handler import RetryConfig, CircuitBreaker, ResponseCache, retry_with_backoff


class OpenAICompatibleProvider(LLMProvider):
    """OpenAI 兼容的 LLM Provider
    
    适用于所有兼容 OpenAI API 格式的服务商
    """
    
    def __init__(
        self, 
        api_key: str, 
        base_url: str, 
        model: str, 
        timeout: int = 30,
        enable_retry: bool = True,
        enable_cache: bool = False,
        cache_ttl: int = 3600
    ):
        """初始化 Provider
        
        Args:
            api_key: API Key
            base_url: API 基础 URL
            model: 模型名称
            timeout: 请求超时时间(秒),默认 30 秒
            enable_retry: 是否启用重试机制
            enable_cache: 是否启用响应缓存
            cache_ttl: 缓存有效期（秒）
        """
        from openai import OpenAI, Timeout
        
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=Timeout(timeout=timeout, connect=10.0)
        )
        self.model = model
        self.timeout = timeout
        
        # 错误处理配置
        self.enable_retry = enable_retry
        self.retry_config = RetryConfig(
            max_retries=3,
            base_delay=1.0,
            max_delay=30.0
        )
        
        # 熔断器
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=5,
            recovery_timeout=60.0
        )
        
        # 响应缓存
        self.enable_cache = enable_cache
        if enable_cache:
            self.cache = ResponseCache(ttl=cache_ttl)
        else:
            self.cache = None
    
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
    
    def chat_stream(
        self,
        messages: List[Dict[str, str]],
        callback=None
    ) -> str:
        """流式聊天
        
        Args:
            messages: 消息历史
            callback: 回调函数，用于处理每个流式片段
            
        Returns:
            str: AI 回复
        """
        full_content = []
        stream = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            stream=True
        )
        
        for chunk in stream:
            if chunk.choices[0].delta.content is not None:
                content = chunk.choices[0].delta.content
                full_content.append(content)
                if callback:
                    callback(content)
        
        return ''.join(full_content)
    
    def chat_with_tools(
        self, 
        messages: List[Dict[str, Any]], 
        tools: List[Dict[str, Any]]
    ) -> ChatResponse:
        """带工具调用的聊天"""
        
        # 尝试从缓存获取
        if self.enable_cache and self.cache:
            cached_response = self.cache.get(messages, tools)
            if cached_response:
                print("✓ 使用缓存响应")
                return ChatResponse.from_dict(cached_response)
        
        # 定义实际API调用函数
        def _call_api():
            return self._execute_chat_with_tools(messages, tools)
        
        # 定义降级函数
        def _fallback():
            print("⚠️  API调用失败，使用离线模式")
            return ChatResponse(
                content="抱歉，目前无法连接到AI服务。请稍后重试。",
                tool_calls=None
            )
        
        # 执行（带重试）
        if self.enable_retry:
            response = retry_with_backoff(
                _call_api,
                config=self.retry_config,
                fallback=_fallback,
                circuit_breaker=self.circuit_breaker
            )()
        else:
            response = _call_api()
        
        # 缓存响应
        if self.enable_cache and self.cache and response.content:
            self.cache.set(messages, response.to_dict(), tools)
        
        return response
    
    def _execute_chat_with_tools(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]]
    ) -> ChatResponse:
        """执行实际的API调用"""
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
    
    def chat_stream(
        self,
        messages: List[Dict[str, str]],
        callback=None
    ) -> str:
        """流式聊天
        
        Args:
            messages: 消息历史
            callback: 回调函数，用于处理每个流式片段
            
        Returns:
            str: AI 回复
        """
        full_content = []
        stream = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            stream=True
        )
        
        for chunk in stream:
            if chunk.choices[0].delta.content is not None:
                content = chunk.choices[0].delta.content
                full_content.append(content)
                if callback:
                    callback(content)
        
        return ''.join(full_content)
    
    def chat_with_tools_stream(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        callback=None
    ) -> ChatResponse:
        """带工具调用的流式聊天"""
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
            # 调用 API (流式)
            stream = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=tools,
                tool_choice="auto",
                stream=True
            )
            
            # 停止倒计时
            stop_event.set()
            timer_thread.join(timeout=0.5)
            print("\r✓ LLM 响应成功              ")
            
            # 处理流式响应
            full_content = []
            tool_calls = []
            current_tool_call = None
            
            for chunk in stream:
                delta = chunk.choices[0].delta
                
                # 处理文本内容
                if delta.content is not None:
                    content = delta.content
                    full_content.append(content)
                    if callback:
                        callback(content)
                
                # 处理工具调用
                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        # 检查是否有新的工具调用开始
                        if tc.index is not None and tc.id is not None:
                            # 新的工具调用
                            current_tool_call = {
                                'id': tc.id,
                                'name': tc.function.name if tc.function else None,
                                'arguments': ''
                            }
                            # 确保索引位置存在
                            while len(tool_calls) <= tc.index:
                                tool_calls.append(None)
                            tool_calls[tc.index] = current_tool_call
                        elif current_tool_call is not None:
                            # 继续当前工具调用的参数
                            if tc.function and tc.function.arguments:
                                current_tool_call['arguments'] += tc.function.arguments
            
            # 解析工具调用参数
            parsed_tool_calls = []
            for tc in tool_calls:
                if tc is not None:
                    try:
                        arguments = json.loads(tc['arguments']) if tc['arguments'] else {}
                        parsed_tool_calls.append(ToolCall(
                            id=tc['id'],
                            name=tc['name'],
                            arguments=arguments
                        ))
                    except json.JSONDecodeError:
                        # 如果参数解析失败，保留原始字符串
                        parsed_tool_calls.append(ToolCall(
                            id=tc['id'],
                            name=tc['name'],
                            arguments={'raw_arguments': tc['arguments']}
                        ))
            
            if parsed_tool_calls:
                return ChatResponse(
                    content=''.join(full_content) if full_content else None,
                    tool_calls=parsed_tool_calls
                )
            else:
                # 没有工具调用,直接返回文本
                return ChatResponse(
                    content=''.join(full_content) if full_content else None,
                    tool_calls=None
                )
            
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
    
    def get_provider_name(self) -> str:
        """获取 Provider 名称"""
        return f"OpenAI-Compatible ({self.model})"
