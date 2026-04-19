"""ReAct Agent 核心模块

支持 Function Calling 模式,使用结构化 API 进行工具调用
"""

import json
from typing import Dict, List

from src.config import read_config
from src.llm.providers.base import LLMProvider
from src.llm.providers.openai_compatible import OpenAICompatibleProvider
from src.tools.base import Tool
from src.tools.file_read import FileReadTool
from src.tools.file_write import FileWriteTool
from src.tools.command_exec import CommandExecTool


class ReActAgent:
    """ReAct 框架 AI Agent
    
    使用 Function Calling 实现 Reasoning + Acting 循环
    """
    
    def __init__(self, config_path: str = None):
        """初始化 ReAct Agent
        
        Args:
            config_path: 配置文件路径
        """
        # 加载配置
        config = read_config(config_path)
        
        # 初始化 LLM Provider
        self.provider = self._create_provider(config)
        
        # 注册工具
        self.tools = self._register_tools()
        
        # 最大迭代次数
        self.max_iterations = 5
        
        # 对话历史
        self.conversation_history = []
    
    def _create_provider(self, config: Dict) -> LLMProvider:
        """创建 LLM Provider
        
        Args:
            config: 配置字典
            
        Returns:
            LLMProvider: Provider 实例
        """
        return OpenAICompatibleProvider(
            api_key=config["api_key"],
            base_url=config.get("base_url", "https://api.deepseek.com/v1"),
            model=config.get("model", "deepseek-chat")
        )
    
    def _register_tools(self) -> Dict[str, Tool]:
        """注册可用工具
        
        Returns:
            Dict[str, Tool]: 工具字典
        """
        return {
            "file_read": FileReadTool(),
            "file_write": FileWriteTool(),
            "command_exec": CommandExecTool()
        }
    
    def _get_tool_schemas(self) -> List[Dict]:
        """获取所有工具的 schema
        
        Returns:
            List[Dict]: 工具定义列表
        """
        return [tool.get_schema() for tool in self.tools.values()]
    
    def _execute_function(self, name: str, arguments: Dict) -> str:
        """执行函数调用
        
        Args:
            name: 函数名称
            arguments: 函数字典
            
        Returns:
            str: 执行结果
        """
        if name not in self.tools:
            return f"错误: 未知工具 '{name}'"
        
        tool = self.tools[name]
        try:
            # 将参数字典转换为关键字参数
            return tool.execute(**arguments)
        except Exception as e:
            return f"工具执行错误: {str(e)}"
    
    def run(self, query: str) -> str:
        """运行 ReAct 循环 (Function Calling 模式)
        
        Args:
            query: 用户问题
            
        Returns:
            str: 最终答案
        """
        print(f"\n{'='*60}")
        print(f"问题: {query}")
        print(f"{'='*60}\n")
        print(f"使用 Provider: {self.provider.get_provider_name()}\n")
        
        # 初始化消息历史
        messages = [
            {
                "role": "system", 
                "content": "你是一个智能助手,可以使用工具帮助用户解决问题。请根据需要使用可用的工具。"
            },
            {"role": "user", "content": query}
        ]
        
        iteration = 0
        while iteration < self.max_iterations:
            iteration += 1
            print(f"[迭代 {iteration}/{self.max_iterations}]")
            
            # 调用 LLM (带工具)
            try:
                response = self.provider.chat_with_tools(
                    messages=messages,
                    tools=self._get_tool_schemas()
                )
                
            except Exception as e:
                return f"API 调用错误: {str(e)}"
            
            # 情况 1: 有工具调用
            if response.has_tool_calls:
                for tool_call in response.tool_calls:
                    print(f"调用工具: {tool_call.name}({tool_call.arguments})")
                    
                    # 执行工具
                    result = self._execute_function(
                        tool_call.name, 
                        tool_call.arguments
                    )
                    print(f"工具结果: {result}\n")
                    
                    # 添加工具调用和结果到消息历史
                    messages.append({
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": tool_call.id,
                                "type": "function",
                                "function": {
                                    "name": tool_call.name,
                                    "arguments": json.dumps(tool_call.arguments)
                                }
                            }
                        ]
                    })
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result
                    })
            
            # 情况 2: 没有工具调用,直接返回文本
            else:
                if response.content:
                    print(f"\n{'='*60}")
                    print(f"最终答案: {response.content}")
                    print(f"{'='*60}\n")
                    return response.content
                else:
                    return "未收到有效响应"
        
        return "达到最大迭代次数,未能找到答案"
    
    def clear_history(self):
        """清除对话历史"""
        self.conversation_history = []
        print("对话历史已清除")
    
    def get_available_tools(self) -> List[Tool]:
        """获取可用工具列表
        
        Returns:
            List[Tool]: 工具列表
        """
        return list(self.tools.values())
