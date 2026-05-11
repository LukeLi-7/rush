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

        # 对话历史 - 用于多轮对话
        self.conversation_history = []
        
        # 最大历史长度（系统提示 + N轮对话）
        self.max_history_length = 41  # system + 20*2 (user + assistant)
        
        # 中断事件（可选，由 main.py 设置）
        self.interrupt_event = None

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
        """构建基础系统提示词

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
- manage_skills: 管理 Agent Skills (list, refresh, enable, disable, 执行 skill)

使用建议:
1. 如果用户询问需要专业知识的问题,先使用 knowledge_search 检索相关知识
2. 如果用户提供了新的知识或信息,可以使用 knowledge_add 保存到知识库
3. 如果需要查看或管理 skills,使用 manage_skills
4. 如果用户需要执行特定任务,检查 manage_skills 工具描述中是否有合适的 skill 可以帮助完成任务
5. 根据需要使用其他工具完成任务

请根据问题选择合适的工具,不要过度调用工具。"""

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

    def _validate_tool_arguments(self, tool: Tool, arguments: Dict) -> Dict:
        """验证工具参数
        
        Args:
            tool: 工具对象
            arguments: 参数字典
            
        Returns:
            Dict: 验证结果 {"valid": bool, "message": str}
        """
        try:
            schema = tool.get_schema()
            params_schema = schema.get("function", {}).get("parameters", {})
            
            if not params_schema:
                # 没有参数schema，跳过验证
                return {"valid": True, "message": ""}
            
            required_params = params_schema.get("required", [])
            properties = params_schema.get("properties", {})
            
            # 检查必填参数
            missing_params = [p for p in required_params if p not in arguments]
            if missing_params:
                return {
                    "valid": False,
                    "message": f"缺少必填参数: {', '.join(missing_params)}"
                }
            
            # 检查参数类型
            for param_name, param_value in arguments.items():
                if param_name in properties:
                    expected_type = properties[param_name].get("type")
                    if expected_type and not self._check_type(param_value, expected_type):
                        return {
                            "valid": False,
                            "message": f"参数 '{param_name}' 类型错误，期望 {expected_type}，实际 {type(param_value).__name__}"
                        }
            
            return {"valid": True, "message": ""}
            
        except Exception as e:
            # 验证过程出错，不阻断执行
            return {"valid": True, "message": f"验证警告: {str(e)}"}
    
    def _check_type(self, value, expected_type: str) -> bool:
        """检查值是否符合预期类型
        
        Args:
            value: 要检查的值
            expected_type: 期望的类型 (string, number, boolean, array, object)
            
        Returns:
            bool: 是否符合类型
        """
        type_map = {
            "string": str,
            "number": (int, float),
            "integer": int,
            "boolean": bool,
            "array": (list, tuple),
            "object": dict
        }
        
        expected_python_type = type_map.get(expected_type)
        if expected_python_type:
            return isinstance(value, expected_python_type)
        
        # 未知类型，默认通过
        return True
    
    def _execute_function(self, name: str, arguments: Dict) -> str:
        """执行函数调用
        
        Args:
            name: 函数名称
            arguments: 函数字典
            
        Returns:
            str: 执行结果（JSON格式）
        """
        import time
        
        # 检查工具是否存在
        if name not in self.tools:
            return json.dumps({
                "success": False,
                "error": f"未知工具: {name}",
                "available_tools": list(self.tools.keys())
            }, ensure_ascii=False)

        tool = self.tools[name]
        
        # 验证参数
        validation_result = self._validate_tool_arguments(tool, arguments)
        if not validation_result["valid"]:
            return json.dumps({
                "success": False,
                "error": validation_result["message"],
                "tool": name,
                "expected_schema": tool.get_schema().get("function", {}).get("parameters", {})
            }, ensure_ascii=False)
        
        # 执行工具（带重试）
        max_retries = 2
        last_error = None
        
        for attempt in range(max_retries):
            try:
                # 将参数字典转换为关键字参数
                result = tool.execute(**arguments)
                
                # 成功执行，返回结果
                return json.dumps({
                    "success": True,
                    "result": result,
                    "attempt": attempt + 1
                }, ensure_ascii=False)
                
            except TypeError as e:
                # 参数类型错误，不重试
                error_msg = str(e)
                if "got an unexpected keyword argument" in error_msg or "missing" in error_msg:
                    return json.dumps({
                        "success": False,
                        "error": f"参数错误: {error_msg}",
                        "tool": name,
                        "provided_args": list(arguments.keys())
                    }, ensure_ascii=False)
                last_error = e
                
            except Exception as e:
                last_error = e
                
                # 如果不是最后一次尝试，等待后重试
                if attempt < max_retries - 1:
                    wait_time = 1 * (attempt + 1)  # 指数退避：1s, 2s
                    print(f"  ⚠️  工具执行失败，{wait_time}秒后重试 ({attempt + 1}/{max_retries})...")
                    time.sleep(wait_time)
                else:
                    # 所有重试都失败
                    break
        
        # 所有重试都失败，返回错误信息
        return json.dumps({
            "success": False,
            "error": f"工具执行失败: {str(last_error)}",
            "tool": name,
            "attempts": max_retries
        }, ensure_ascii=False)

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
    
    def _handle_interruption(self):
        """处理中断 - 清理资源并返回
        
        Returns:
            str: 中断消息
        """
        print("\n⚠️  操作已中断")
        # 不清理所有资源，只重置中断状态
        if self.interrupt_event:
            self.interrupt_event.clear()
        return "操作已中断"

    def run(self, query: str, use_streaming: bool = True) -> str:
        """运行 ReAct 循环 (Function Calling 模式)
        
        Args:
            query: 用户问题
            use_streaming: 是否使用流式输出，默认为True
            
        Returns:
            str: 最终答案
        """
        print(f"\n{'=' * 60}")
        print(f"问题: {query}")
        print(f"{'=' * 60}\n")
        print(f"使用 Provider: {self.provider.get_provider_name()}\n")

        # 如果是对话的第一轮，初始化系统提示
        if not self.conversation_history:
            self.conversation_history.append({
                "role": "system",
                "content": self.base_system_prompt
            })
        
        # 添加用户问题到历史
        self.conversation_history.append({"role": "user", "content": query})
        
        # 使用完整的历史记录进行对话
        messages = self.conversation_history.copy()

        iteration = 0
        while iteration < self.max_iterations:
            # 检查是否被中断
            if self._check_interrupted():
                return self._handle_interruption()

            iteration += 1
            print(f"\n{'─' * 60}")
            print(f"[迭代 {iteration}/{self.max_iterations}]")
            print(f"{'─' * 60}")

            # 调用 LLM (带工具)
            if use_streaming:
                # 定义回调函数用于流式输出 - 区分思考过程
                print("\n💭 Agent 思考中...")
                thinking_content = []
                
                def stream_callback(chunk):
                    thinking_content.append(chunk)
                    print(chunk, end='', flush=True)
                
                response = self.provider.chat_with_tools_stream(
                    messages=messages,
                    tools=self._get_tool_schemas(),
                    callback=stream_callback
                )
                print()  # 换行
            else:
                response = self.provider.chat_with_tools(
                    messages=messages,
                    tools=self._get_tool_schemas()
                )

            # 情况 1: 有工具调用
            if response.has_tool_calls:
                print(f"\n🔧 需要调用工具...")
                
                for tool_call in response.tool_calls:
                    print(f"\n  📞 调用工具: {tool_call.name}")
                    print(f"     参数: {json.dumps(tool_call.arguments, ensure_ascii=False, indent=2)}")

                    # 执行工具
                    result = self._execute_function(
                        tool_call.name,
                        tool_call.arguments
                    )
                    
                    # 解析JSON格式的结果
                    try:
                        result_data = json.loads(result)
                        if result_data.get("success"):
                            # 成功，提取实际结果
                            actual_result = result_data.get("result", "")
                            attempt_info = f" (第{result_data.get('attempt', 1)}次尝试)" if result_data.get('attempt', 1) > 1 else ""
                            print(f"\n  ✅ 工具返回{attempt_info}:")
                            # 格式化显示结果
                            if isinstance(actual_result, str) and len(actual_result) > 200:
                                print(f"     {actual_result[:200]}...")
                            else:
                                print(f"     {actual_result}")
                            result_for_llm = actual_result
                        else:
                            # 失败，返回错误信息
                            error_msg = result_data.get("error", "未知错误")
                            print(f"\n  ❌ 工具执行失败:")
                            print(f"     {error_msg}")
                            result_for_llm = result  # 将完整JSON返回给LLM，让它理解错误
                    except json.JSONDecodeError:
                        # 如果不是JSON格式，直接使用原始结果（向后兼容）
                        print(f"\n  📄 工具返回:")
                        print(f"     {result}")
                        result_for_llm = result

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
                        "content": result_for_llm
                    })
                
                print(f"\n{'─' * 60}")

            # 情况 2: 没有工具调用,直接返回文本
            else:
                if response.content:
                    # 将助手回复添加到对话历史
                    self.conversation_history.append({
                        "role": "assistant",
                        "content": response.content
                    })
                    
                    # 限制历史长度，避免超出上下文窗口
                    self._trim_conversation_history()
                    
                    print(f"\n{'=' * 60}")
                    print(f"💡 最终答案:")
                    print(f"{'=' * 60}")
                    # 如果是流式模式，已经输出过了，这里只打印分隔线
                    if not use_streaming:
                        print(response.content)
                    print(f"{'=' * 60}\n")
                    return response.content
                else:
                    return "未收到有效响应"

        return "达到最大迭代次数,未能找到答案"

    def clear_history(self):
        """清除对话历史"""
        self.conversation_history = []
        print("对话历史已清除")
    
    def cleanup(self):
        """清理所有资源
        
        确保 MCP connections、asyncio loop 等资源正确关闭
        """
        print("\n🧹 正在清理资源...")
        
        try:
            # 1. 断开所有 MCP connections
            if self.mcp_manager and self.mcp_manager.clients:
                import asyncio
                import warnings
                
                # 为每个server创建新的loop
                for server_name in list(self.mcp_manager.clients.keys()):
                    try:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        with warnings.catch_warnings():
                            warnings.simplefilter("ignore", ResourceWarning)
                            
                            # 断开 server
                            loop.run_until_complete(
                                self.mcp_manager.disconnect_server(server_name)
                            )
                            print(f"  ✓ 已断开 MCP server: {server_name}")
                        
                        loop.close()
                    except Exception as e:
                        print(f"  ⚠️  断开 {server_name} 失败: {e}")
                
                print(f"  ✓ 已清理 {len(self.mcp_manager.clients)} 个 MCP connections")
            
            # 2. 清除工具注册
            self.tools.clear()
            print("  ✓ 已清除工具注册")
            
            # 3. 清除对话历史
            self.conversation_history.clear()
            print("  ✓ 已清除对话历史")
            
            # 4. 重置中断事件
            if self.interrupt_event:
                self.interrupt_event.clear()
            
            print("✅ 资源清理完成\n")
            
        except Exception as e:
            print(f"⚠️  资源清理出错: {e}")
    
    def __del__(self):
        """析构函数 - 确保资源被清理"""
        try:
            self.cleanup()
        except:
            pass  # 析构函数中忽略异常
    
    def _trim_conversation_history(self):
        """裁剪对话历史，避免超出上下文窗口
        
        保留系统提示和最近的 N 轮对话
        """
        if len(self.conversation_history) <= self.max_history_length:
            return
        
        # 保留系统提示
        system_message = self.conversation_history[0]
        
        # 保留最近的 max_history_length - 1 条消息
        recent_messages = self.conversation_history[-(self.max_history_length - 1):]
        
        # 重新组合
        self.conversation_history = [system_message] + recent_messages
        
        print(f"⚠️  对话历史过长，已裁剪至最近 {len(recent_messages)//2} 轮对话")
    
    def get_history_summary(self) -> str:
        """获取对话历史摘要
        
        Returns:
            str: 历史摘要信息
        """
        if not self.conversation_history:
            return "暂无对话历史"
        
        # 计算对话轮数（减去系统提示）
        conversation_count = len(self.conversation_history) - 1
        rounds = conversation_count // 2
        
        summary_lines = [
            f"对话历史统计:",
            f"  总消息数: {len(self.conversation_history)}",
            f"  对话轮数: {rounds}",
            f"  最大允许: {(self.max_history_length - 1) // 2} 轮"
        ]
        
        # 显示最近几轮对话的简要信息
        if conversation_count > 0:
            summary_lines.append(f"\n最近对话:")
            # 显示最近 3 轮
            recent_start = max(1, len(self.conversation_history) - 6)
            for i in range(recent_start, len(self.conversation_history)):
                msg = self.conversation_history[i]
                role = msg.get("role", "unknown")
                content = msg.get("content", "")
                if role == "user":
                    preview = content[:50] + "..." if len(content) > 50 else content
                    summary_lines.append(f"  用户: {preview}")
                elif role == "assistant":
                    preview = content[:50] + "..." if len(content) > 50 else content
                    summary_lines.append(f"  AI: {preview}")
        
        return "\n".join(summary_lines)

    def get_available_tools(self) -> List[Tool]:
        """获取可用工具列表
        
        Returns:
            List[Tool]: 工具列表
        """
        return list(self.tools.values())
