"""ReAct Agent 核心模块

支持 Function Calling 模式,使用结构化 API 进行工具调用
"""

import json
import threading
from typing import Dict, List, Optional

from src.config import read_config
from src.llm.providers.base import LLMProvider
from src.llm.providers.openai_compatible import OpenAICompatibleProvider
from src.vector_db.providers.base import VectorDBProvider
from src.vector_db.providers.chromadb import ChromaDBProvider
from src.vector_db.providers.milvus import MilvusProvider
from src.tools.base import Tool
from src.tools.file_read import FileReadTool
from src.tools.file_write import FileWriteTool
from src.tools.command_exec import CommandExecTool
from src.skills.manager import SkillManager
from src.tools.skill_tool import SkillManagerTool
from src.mcp.manager import MCPManager
from src.tools.mcp_tool import MCPManagerTool


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
        from src.config import load_config
        actual_config_path = load_config(config_path)
        config = read_config(actual_config_path)

        # 初始化 LLM Provider
        self.provider = self._create_provider(config)

        # 初始化向量数据库
        vector_db_config = config.get("vector_db", {})
        self.vector_db = self._init_vector_db(vector_db_config)

        # 初始化 Skill 管理器
        self.skill_manager = SkillManager()

        # 初始化 MCP 管理器
        self.mcp_manager = MCPManager()

        # 注册工具
        self.tools = self._register_tools()

        # 自动连接 MCP servers 并注册 tools
        self._init_mcp_servers()

        # 最大迭代次数
        self.max_iterations = 5

        # 对话历史
        self.conversation_history = []

        # 构建系统提示词(包含 skills)
        self.base_system_prompt = self._build_system_prompt()

    def _create_provider(self, config: Dict) -> LLMProvider:
        """创建 LLM Provider"""
        return OpenAICompatibleProvider(
            api_key=config["api_key"],
            base_url=config.get("base_url", "https://api.deepseek.com/v1"),
            model=config.get("model", "deepseek-chat"),
            timeout=config.get("timeout", 30)
        )

    def _init_vector_db(self, config: Dict) -> Optional[VectorDBProvider]:
        """初始化向量数据库"""
        if not config:
            return None

        # 获取激活的提供者配置
        if "providers" in config:
            active = config.get("active", "chromadb")
            provider_config = config["providers"].get(active)
        else:
            # 兼容旧格式
            active = config.get("provider", "chromadb")
            provider_config = config

        if not provider_config:
            print(f"警告: 提供者 '{active}' 配置不存在")
            return None

        try:
            if active == "chromadb":
                import os
                db = ChromaDBProvider(
                    persist_directory=os.path.expanduser(
                        provider_config.get("persist_directory", "~/.rush/chromadb")
                    )
                )
            elif active == "milvus":
                db = MilvusProvider(
                    host=provider_config.get("host", "localhost"),
                    port=provider_config.get("port", "19530"),
                    collection_name=provider_config.get("collection_name", "rush_knowledge"),
                    embedding_dim=provider_config.get("embedding_dim", 384)
                )
            else:
                print(f"警告: 不支持的向量数据库类型 '{active}'")
                return None

            db.initialize()
            print(f"✓ 向量数据库初始化成功: {db.get_provider_name()}")
            return db

        except Exception as e:
            import traceback
            print(f"警告: 向量数据库初始化失败: {str(e)}")
            print(f"详细错误:\n{traceback.format_exc()}")
            return None

    def _build_system_prompt(self) -> str:
        """构建基础系统提示词(包含 skills)
        
        Returns:
            str: 系统提示词
        """
        base_prompt = """你是一个智能助手,可以使用工具帮助用户解决问题。

重要: 所有回答都必须使用中文(简体中文)。

可用工具:
- file_read: 读取文件内容
- file_write: 写入文件内容
- command_exec: 执行系统命令
- knowledge_search: 从知识库中搜索相关信息(当用户询问知识性问题时使用)
- knowledge_add: 向知识库添加新知识(当用户提供新信息时使用)
- manage_skills: 管理 Agent Skills (list, refresh, enable, disable)

使用建议:
1. 如果用户询问需要专业知识的问题,先使用 knowledge_search 检索相关知识
2. 如果用户提供了新的知识或信息,可以使用 knowledge_add 保存到知识库
3. 如果需要查看或管理 skills,使用 manage_skills
4. 根据需要使用其他工具完成任务

请根据问题选择合适的工具,不要过度调用工具。"""

        # 添加已启用的 skills
        if self.skill_manager:
            skills_content = self.skill_manager.get_enabled_skills_text()
            if skills_content:
                base_prompt += "\n\n=== Agent Skills ==="
                base_prompt += skills_content

        return base_prompt

    def _register_tools(self) -> Dict[str, Tool]:
        """注册可用工具
        
        Returns:
            Dict[str, Tool]: 工具字典
        """
        tools = {
            "file_read": FileReadTool(),
            "file_write": FileWriteTool(),
            "command_exec": CommandExecTool()
        }

        # 如果向量数据库可用,添加 RAG 工具
        if self.vector_db:
            from src.tools.rag import KnowledgeSearchTool, KnowledgeAddTool
            tools["knowledge_search"] = KnowledgeSearchTool(self)
            tools["knowledge_add"] = KnowledgeAddTool(self)
            print("✓ RAG 工具已启用 (knowledge_search, knowledge_add)")

        # 添加 Skill 管理工具
        try:
            tools["manage_skills"] = SkillManagerTool(self)
            print("✓ Skill 管理工具已启用 (manage_skills)")
        except Exception as e:
            print(f"⚠ Skill 工具加载失败: {e}")

        # 添加 MCP 管理工具
        try:
            tools["manage_mcp"] = MCPManagerTool(self.mcp_manager)
            print("✓ MCP 管理工具已启用 (manage_mcp)")
        except Exception as e:
            print(f"⚠ MCP 管理工具加载失败: {e}")

        return tools

    def _init_mcp_servers(self):
        """初始化并连接 MCP servers,注册所有 MCP tools"""
        try:
            import asyncio
            import warnings

            # 连接所有启用的 MCP servers
            loop = asyncio.new_event_loop()
            
            # 抑制事件循环关闭警告
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", ResourceWarning)
                connected_count = loop.run_until_complete(self.mcp_manager.connect_all())
                loop.close()

            if connected_count > 0:
                print(f"✓ 已连接 {connected_count} 个 MCP servers")

                # 注册所有 MCP tools
                self._register_mcp_tools()
            else:
                print("⚠ 没有成功连接的 MCP servers")

        except Exception as e:
            print(f"⚠ MCP servers 初始化失败: {e}")

    def _register_mcp_tools(self):
        """注册所有已连接 MCP servers 的 tools"""
        for server_name, client in self.mcp_manager.clients.items():
            for tool_name, mcp_tool in client.tools.items():
                # 创建工具适配器
                from src.tools.mcp_tool import MCPToolAdapter
                adapter = MCPToolAdapter(
                    mcp_manager=self.mcp_manager,
                    server_name=server_name,
                    tool_name=tool_name,
                    description=mcp_tool.description,
                    input_schema=mcp_tool.input_schema
                )

                # 注册到工具字典
                full_tool_name = f"mcp_{server_name}_{tool_name}"
                self.tools[full_tool_name] = adapter

        mcp_tool_count = sum(len(client.tools) for client in self.mcp_manager.clients.values())
        print(f"✓ 已注册 {mcp_tool_count} 个 MCP tools")

    def _get_tool_schemas(self) -> List[Dict]:
        """获取所有工具的 schema
        
        Returns:
            List[Dict]: 工具定义列表
        """
        schemas = [tool.get_schema() for tool in self.tools.values()]
        return schemas

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

    def set_interrupt_event(self, event: threading.Event):
        """设置中断事件对象
        
        Args:
            event: threading.Event 对象,用于检测中断信号
        """
        self.interrupt_event = event
    
    def _check_interrupted(self) -> bool:
        """检查是否被中断
        
        Returns:
            bool: 是否被中断
        """
        if self.interrupt_event and self.interrupt_event.is_set():
            return True
        return False

    def run(self, query: str) -> str:
        """运行 ReAct 循环 (Function Calling 模式)
        
        Args:
            query: 用户问题
            
        Returns:
            str: 最终答案
        """
        print(f"\n{'=' * 60}")
        print(f"问题: {query}")
        print(f"{'=' * 60}\n")
        print(f"使用 Provider: {self.provider.get_provider_name()}\n")

        # 初始化消息历史
        messages = [
            {
                "role": "system",
                "content": self.base_system_prompt
            },
            {"role": "user", "content": query}
        ]

        iteration = 0
        while iteration < self.max_iterations:
            iteration += 1
            print(f"[迭代 {iteration}/{self.max_iterations}]")

            # 调用 LLM (带工具)
            response = self.provider.chat_with_tools(
                messages=messages,
                tools=self._get_tool_schemas()
            )

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
                    print(f"\n{'=' * 60}")
                    print(f"最终答案: {response.content}")
                    print(f"{'=' * 60}\n")
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
