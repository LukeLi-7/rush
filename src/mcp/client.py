"""
MCP (Model Context Protocol) 客户端

支持通过 stdio 和 SSE 协议连接 MCP servers
参考: https://modelcontextprotocol.io/
"""

import os
import json
import asyncio
import shutil
from typing import Dict, List, Any
from dataclasses import dataclass, field


@dataclass
class MCPTool:
    """MCP Tool 定义"""
    name: str
    description: str
    input_schema: Dict[str, Any] = field(default_factory=dict)

    def to_function_schema(self) -> Dict[str, Any]:
        """转换为 OpenAI Function Calling schema"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.input_schema if self.input_schema else {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        }


@dataclass
class MCPResource:
    """MCP Resource 定义"""
    uri: str
    name: str
    description: str = ""
    mime_type: str = ""


class MCPClient:
    """MCP 客户端
    
    支持与 MCP server 通信,获取 tools 和 resources
    当前实现基于 stdio 协议
    """

    def __init__(self, command: str, args: List[str] = None, env: Dict[str, str] = None):
        """初始化 MCP 客户端
        
        Args:
            command: MCP server 启动命令 (如: npx, python)
            args: 命令参数
            env: 环境变量
        """
        self.command = command
        self.args = args or []
        self.env = env or {}

        # 状态
        self.connected = False
        self.tools: Dict[str, MCPTool] = {}
        self.resources: Dict[str, MCPResource] = {}
        self.server_info: Dict[str, Any] = {}

        # 进程引用
        self.process = None
        self._message_id = 0

    async def connect(self) -> bool:
        """连接到 MCP server
        
        Returns:
            bool: 是否成功连接
        """
        try:
            # 启动子进程
            full_args = [self.command] + self.args

            # 如果命令不是绝对路径,尝试查找完整路径
            if not os.path.isabs(self.command):
                command_path = shutil.which(self.command)
                if command_path:
                    full_args[0] = command_path
                    print(f"找到命令路径: {command_path}")
                else:
                    raise FileNotFoundError(f"找不到命令: {self.command}")

            print(f"正在启动 MCP server: {' '.join(full_args)}")

            # 合并环境变量
            env = {**os.environ, **self.env}

            self.process = await asyncio.create_subprocess_exec(
                *full_args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env
            )

            # 发送初始化请求
            init_result = await self._send_request("initialize", {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {}
                },
                "clientInfo": {
                    "name": "rush-agent",
                    "version": "1.0.0"
                }
            })

            self.server_info = init_result.get("serverInfo", {})
            print(f"✓ 已连接到 MCP server: {self.server_info.get('name', 'unknown')}")

            # 发送 initialized 通知
            await self._send_notification("notifications/initialized", {})

            # 获取可用工具
            await self._list_tools()

            # 获取可用资源
            await self._list_resources()

            self.connected = True
            return True

        except Exception as e:
            print(f"✗ 连接 MCP server 失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    async def disconnect(self):
        """断开与 MCP server 的连接"""
        if self.process:
            try:
                self.process.terminate()
                await self.process.wait()
            except Exception as e:
                print(f"关闭 MCP server 时出错: {e}")

            self.process = None
            self.connected = False
            print("已断开 MCP server 连接")

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """调用 MCP tool
        
        Args:
            tool_name: 工具名称
            arguments: 工具参数
            
        Returns:
            str: 执行结果
        """
        if not self.connected:
            return "错误: MCP client 未连接"

        if tool_name not in self.tools:
            return f"错误: 未知工具 '{tool_name}'"

        try:
            result = await self._send_request("tools/call", {
                "name": tool_name,
                "arguments": arguments
            })

            # 解析结果
            content = result.get("content", [])
            if content:
                # 返回第一个文本内容
                for item in content:
                    if item.get("type") == "text":
                        return item.get("text", "")
                return json.dumps(content, ensure_ascii=False, indent=2)
            else:
                return json.dumps(result, ensure_ascii=False, indent=2)

        except Exception as e:
            return f"工具调用错误: {str(e)}"

    async def read_resource(self, uri: str) -> str:
        """读取 MCP resource
        
        Args:
            uri: 资源 URI
            
        Returns:
            str: 资源内容
        """
        if not self.connected:
            return "错误: MCP client 未连接"

        try:
            result = await self._send_request("resources/read", {
                "uri": uri
            })

            contents = result.get("contents", [])
            if contents:
                return json.dumps(contents, ensure_ascii=False, indent=2)
            return "无内容"

        except Exception as e:
            return f"资源读取错误: {str(e)}"

    async def _list_tools(self):
        """获取可用工具列表"""
        try:
            result = await self._send_request("tools/list", {})
            tools_data = result.get("tools", [])

            self.tools = {}
            for tool_data in tools_data:
                tool = MCPTool(
                    name=tool_data["name"],
                    description=tool_data.get("description", ""),
                    input_schema=tool_data.get("inputSchema", {})
                )
                self.tools[tool.name] = tool

            print(f"  发现 {len(self.tools)} 个工具: {', '.join(self.tools.keys())}")

        except Exception as e:
            print(f"获取工具列表失败: {e}")

    async def _list_resources(self):
        """获取可用资源列表"""
        try:
            result = await self._send_request("resources/list", {})
            resources_data = result.get("resources", [])

            self.resources = {}
            for resource_data in resources_data:
                resource = MCPResource(
                    uri=resource_data["uri"],
                    name=resource_data["name"],
                    description=resource_data.get("description", ""),
                    mime_type=resource_data.get("mimeType", "")
                )
                self.resources[resource.uri] = resource

            if self.resources:
                print(f"  发现 {len(self.resources)} 个资源")

        except Exception as e:
            # Resources 是可选功能,很多 servers 不支持,静默忽略
            pass

    async def _send_request(self, method: str, params: Dict[str, Any], timeout: int = 30) -> Dict:
        """发送 JSON-RPC 请求
        
        Args:
            method: 方法名
            params: 参数
            timeout: 超时时间(秒)
            
        Returns:
            Dict: 响应结果
        """
        self._message_id += 1
        request = {
            "jsonrpc": "2.0",
            "id": self._message_id,
            "method": method,
            "params": params
        }

        # 发送请求
        request_str = json.dumps(request) + "\n"
        self.process.stdin.write(request_str.encode('utf-8'))
        await self.process.stdin.drain()

        # 读取响应
        try:
            response_line = await asyncio.wait_for(
                self.process.stdout.readline(),
                timeout=timeout
            )

            if not response_line:
                raise Exception("服务器未返回响应")

            response = json.loads(response_line.decode('utf-8'))

            if "error" in response:
                raise Exception(f"RPC 错误: {response['error']}")

            return response.get("result", {})

        except asyncio.TimeoutError:
            raise Exception(f"请求超时 ({timeout}s)")

    async def _send_notification(self, method: str, params: Dict[str, Any]):
        """发送 JSON-RPC 通知 (不需要响应)"""
        notification = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params
        }

        notification_str = json.dumps(notification) + "\n"
        self.process.stdin.write(notification_str.encode('utf-8'))
        await self.process.stdin.drain()

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        """获取所有工具的 schema (用于 Function Calling)"""
        return [tool.to_function_schema() for tool in self.tools.values()]

    def get_tools_info(self) -> List[Dict[str, str]]:
        """获取工具信息列表"""
        return [
            {
                "name": tool.name,
                "description": tool.description
            }
            for tool in self.tools.values()
        ]
