"""
MCP 工具适配器

将 MCP tools 包装为 Agent 可用的 Tool 对象
"""

import asyncio
from typing import TYPE_CHECKING, Dict, Any
from src.tools.base import Tool

if TYPE_CHECKING:
    from src.mcp.manager import MCPManager


class MCPToolAdapter(Tool):
    """MCP 工具适配器
    
    将 MCP server 的工具包装为标准 Tool 接口
    """
    
    def __init__(self, mcp_manager: 'MCPManager', server_name: str, tool_name: str, 
                 description: str, input_schema: Dict[str, Any]):
        """初始化
        
        Args:
            mcp_manager: MCP 管理器实例
            server_name: MCP server 名称
            tool_name: MCP tool 名称
            description: 工具描述
            input_schema: 输入参数 schema
        """
        # 工具名格式: mcp_{server}_{tool}
        full_name = f"mcp_{server_name}_{tool_name}"
        super().__init__(
            name=full_name,
            description=f"[{server_name}] {description}"
        )
        
        self.mcp_manager = mcp_manager
        self.server_name = server_name
        self.tool_name = tool_name
        self.input_schema = input_schema
    
    def execute(self, **kwargs) -> str:
        """执行 MCP 工具
        
        Args:
            **kwargs: 工具参数
            
        Returns:
            str: 执行结果
        """
        try:
            import asyncio
            from src.mcp.client import MCPClient
            
            # 获取 server 配置
            server_config = self.mcp_manager.servers.get(self.server_name)
            if not server_config:
                return f"错误: 找不到 server '{self.server_name}' 的配置"
            
            # 创建临时 client (避免事件循环问题)
            temp_client = MCPClient(
                command=server_config.command,
                args=server_config.args,
                env=server_config.env
            )
            
            # 创建新的事件循环
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                # 连接并调用
                connected = loop.run_until_complete(temp_client.connect())
                if not connected:
                    return "错误: 无法连接到 MCP server"
                
                result = loop.run_until_complete(
                    temp_client.call_tool(self.tool_name, kwargs)
                )
                
                return result
                
            finally:
                # 断开连接
                loop.run_until_complete(temp_client.disconnect())
                loop.close()
                
        except Exception as e:
            return f"MCP 工具执行错误: {str(e)}"
    
    def get_schema(self) -> Dict[str, Any]:
        """获取工具的 Function Calling schema"""
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


class MCPManagerTool(Tool):
    """MCP 管理工具
    
    让 Agent 可以查看和管理 MCP servers
    """
    
    def __init__(self, mcp_manager: 'MCPManager'):
        super().__init__(
            name="manage_mcp",
            description="管理 MCP servers。用法: manage_mcp(action, server_name=None, command=None, args=None)"
        )
        self.mcp_manager = mcp_manager
    
    def execute(self, action: str, server_name: str = None, 
                command: str = None, args: str = None) -> str:
        """执行 MCP 管理操作
        
        Args:
            action: 操作类型 (list, connect, disconnect, enable, disable, add, remove)
            server_name: server 名称
            command: 启动命令 (add 时需要)
            args: 参数字符串,用空格分隔 (add 时需要)
            
        Returns:
            str: 操作结果
        """
        action = action.lower().strip()
        
        if action == "list":
            servers = self.mcp_manager.list_servers()
            if not servers:
                return "暂无配置的 MCP servers\n\n提示: 使用 manage_mcp('add', ...) 添加新的 server"
            
            lines = ["当前配置的 MCP Servers:\n"]
            for server in servers:
                status_icon = "✓" if server['connected'] else "○"
                enabled_icon = "启用" if server['enabled'] else "禁用"
                lines.append(f"• {server['name']}")
                lines.append(f"  状态: {status_icon} {enabled_icon}")
                lines.append(f"  命令: {server['command']} {' '.join(server['args'])}")
                lines.append(f"  可用工具: {server['tools']} 个\n")
            
            return "\n".join(lines)
        
        elif action == "connect":
            if not server_name:
                return "✗ 错误: 请指定要连接的 server 名称"
            
            # 运行异步连接
            loop = asyncio.new_event_loop()
            try:
                success = loop.run_until_complete(
                    self.mcp_manager.connect_server(server_name)
                )
                if success:
                    return f"✓ 已连接 MCP server '{server_name}'"
                return f"✗ 连接失败"
            finally:
                loop.close()
        
        elif action == "disconnect":
            if not server_name:
                return "✗ 错误: 请指定要断开的 server 名称"
            
            loop = asyncio.new_event_loop()
            try:
                success = loop.run_until_complete(
                    self.mcp_manager.disconnect_server(server_name)
                )
                if success:
                    return f"✓ 已断开 MCP server '{server_name}'"
                return f"✗ 断开失败"
            finally:
                loop.close()
        
        elif action == "enable":
            if not server_name:
                return "✗ 错误: 请指定要启用的 server 名称"
            success = self.mcp_manager.enable_server(server_name)
            if success:
                return f"✓ 已启用 MCP server '{server_name}',下次连接时生效"
            return f"✗ 启用失败"
        
        elif action == "disable":
            if not server_name:
                return "✗ 错误: 请指定要禁用的 server 名称"
            success = self.mcp_manager.disable_server(server_name)
            if success:
                return f"✓ 已禁用 MCP server '{server_name}'"
            return f"✗ 禁用失败"
        
        elif action == "add":
            if not server_name or not command:
                return "✗ 错误: 请提供 server_name 和 command\n示例: manage_mcp('add', 'myserver', 'npx', '-y @modelcontextprotocol/server-example')"
            
            args_list = args.split() if args else []
            success = self.mcp_manager.add_server(server_name, command, args_list)
            if success:
                return f"✓ 已添加 MCP server '{server_name}',使用 connect 操作进行连接"
            return f"✗ 添加失败"
        
        elif action == "remove":
            if not server_name:
                return "✗ 错误: 请指定要移除的 server 名称"
            success = self.mcp_manager.remove_server(server_name)
            if success:
                return f"✓ 已移除 MCP server '{server_name}'"
            return f"✗ 移除失败"
        
        else:
            return f"✗ 未知操作: {action}\n支持的操作: list, connect, disconnect, enable, disable, add, remove"
    
    def get_schema(self) -> Dict[str, Any]:
        """获取工具的 Function Calling schema"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "description": "操作类型",
                            "enum": ["list", "connect", "disconnect", "enable", "disable", "add", "remove"]
                        },
                        "server_name": {
                            "type": "string",
                            "description": "server 名称"
                        },
                        "command": {
                            "type": "string",
                            "description": "启动命令 (add 时需要)"
                        },
                        "args": {
                            "type": "string",
                            "description": "参数字符串,用空格分隔 (add 时需要)"
                        }
                    },
                    "required": ["action"]
                }
            }
        }
