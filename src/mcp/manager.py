"""
MCP 管理器

负责管理多个 MCP servers 的生命周期和动态加载
"""

import os
import json
import asyncio
from typing import Dict, List

from .client import MCPClient


class MCPServerConfig:
    """MCP Server 配置"""
    
    def __init__(self, name: str, command: str, args: List[str] = None, 
                 env: Dict[str, str] = None, enabled: bool = True):
        self.name = name
        self.command = command
        self.args = args or []
        self.env = env or {}
        self.enabled = enabled


class MCPManager:
    """MCP 管理器
    
    功能:
    - 从配置文件加载 MCP servers
    - 动态连接/断开 servers
    - 管理所有已连接的 clients
    - 提供统一的工具调用接口
    
    配置加载顺序 (与 config.json 一致):
    1. 全局配置: ~/.rush/mcp_servers.json
    2. 本地配置: .rush/mcp_servers.json (覆盖同名的全局配置)
    """
    
    def __init__(self, global_config_path: str = None, local_config_path: str = None):
        """初始化 MCP 管理器
        
        Args:
            global_config_path: 全局配置文件路径,默认为 ~/.rush/mcp_servers.json
            local_config_path: 本地配置文件路径,默认为 .rush/mcp_servers.json
        """
        if global_config_path is None:
            global_config_path = os.path.expanduser("~/.rush/mcp_servers.json")
        
        if local_config_path is None:
            local_config_path = os.path.join(os.getcwd(), '.rush', 'mcp_servers.json')
        
        self.global_config_path = global_config_path
        self.local_config_path = local_config_path
        self.servers: Dict[str, MCPServerConfig] = {}
        self.clients: Dict[str, MCPClient] = {}
        
        # 确保目录存在
        os.makedirs(os.path.dirname(global_config_path), exist_ok=True)
        os.makedirs(os.path.dirname(local_config_path), exist_ok=True)
        
        # 加载配置
        self.load_config()
    
    def load_config(self) -> bool:
        """从全局和本地配置文件加载 MCP servers
        
        加载顺序:
        1. 先加载全局配置 (~/.rush/mcp_servers.json)
        2. 再加载本地配置 (.rush/mcp_servers.json),同名会覆盖全局配置
        
        Returns:
            bool: 是否成功
        """
        try:
            self.servers = {}
            
            # 1. 加载全局配置
            global_count = self._load_from_file(self.global_config_path, "全局")
            
            # 2. 加载本地配置 (覆盖同名)
            local_count = self._load_from_file(self.local_config_path, "本地")
            
            total = len(self.servers)
            enabled_count = sum(1 for s in self.servers.values() if s.enabled)
            print(f"✓ 已加载 {total} 个 MCP servers (全局: {global_count}, 本地: {local_count}, 启用: {enabled_count})")
            return True
            
        except Exception as e:
            print(f"✗ 加载 MCP 配置失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _load_from_file(self, config_path: str, source: str) -> int:
        """从指定文件加载 MCP servers
        
        Args:
            config_path: 配置文件路径
            source: 来源标识 (用于日志)
            
        Returns:
            int: 加载的 server 数量
        """
        if not os.path.exists(config_path):
            return 0
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            servers_data = config.get("mcpServers", {})
            count = 0
            
            for name, server_data in servers_data.items():
                server = MCPServerConfig(
                    name=name,
                    command=server_data["command"],
                    args=server_data.get("args", []),
                    env=server_data.get("env", {}),
                    enabled=server_data.get("enabled", True)
                )
                self.servers[name] = server  # 本地配置会覆盖全局配置
                count += 1
            
            if count > 0:
                print(f"  从{source}配置加载 {count} 个 servers: {config_path}")
            
            return count
            
        except Exception as e:
            print(f"✗ 加载{source}MCP 配置失败 ({config_path}): {e}")
            return 0
    
    def save_config(self) -> bool:
        """保存当前配置到本地配置文件
        
        Returns:
            bool: 是否成功
        """
        try:
            config = {
                "mcpServers": {
                    name: {
                        "command": server.command,
                        "args": server.args,
                        "env": server.env,
                        "enabled": server.enabled
                    }
                    for name, server in self.servers.items()
                }
            }
            
            # 保存到本地配置文件
            with open(self.local_config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            
            print(f"✓ MCP 配置已保存: {self.local_config_path}")
            return True
            
        except Exception as e:
            print(f"✗ 保存 MCP 配置失败: {e}")
            return False
    
    async def connect_all(self) -> int:
        """连接所有启用的 MCP servers
        
        Returns:
            int: 成功连接的数量
        """
        success_count = 0
        
        for name, server in self.servers.items():
            if not server.enabled:
                continue
            
            try:
                client = MCPClient(
                    command=server.command,
                    args=server.args,
                    env=server.env
                )
                
                connected = await client.connect()
                if connected:
                    self.clients[name] = client
                    success_count += 1
                    
            except Exception as e:
                print(f"✗ 连接 MCP server '{name}' 失败: {e}")
        
        print(f"\n总计连接 {success_count}/{len([s for s in self.servers.values() if s.enabled])} 个 MCP servers")
        return success_count
    
    async def disconnect_all(self):
        """断开所有 MCP servers"""
        for name, client in self.clients.items():
            await client.disconnect()
        
        self.clients.clear()
        print("已断开所有 MCP servers")
    
    async def connect_server(self, name: str) -> bool:
        """连接指定的 MCP server
        
        Args:
            name: server 名称
            
        Returns:
            bool: 是否成功
        """
        if name not in self.servers:
            print(f"✗ 未知的 MCP server: {name}")
            return False
        
        if name in self.clients:
            print(f"⚠ MCP server '{name}' 已连接")
            return True
        
        server = self.servers[name]
        try:
            client = MCPClient(
                command=server.command,
                args=server.args,
                env=server.env
            )
            
            connected = await client.connect()
            if connected:
                self.clients[name] = client
                return True
            return False
            
        except Exception as e:
            print(f"✗ 连接 MCP server '{name}' 失败: {e}")
            return False
    
    async def disconnect_server(self, name: str) -> bool:
        """断开指定的 MCP server
        
        Args:
            name: server 名称
            
        Returns:
            bool: 是否成功
        """
        if name not in self.clients:
            print(f"⚠ MCP server '{name}' 未连接")
            return False
        
        try:
            await self.clients[name].disconnect()
            del self.clients[name]
            return True
        except Exception as e:
            print(f"✗ 断开 MCP server '{name}' 失败: {e}")
            return False
    
    def enable_server(self, name: str) -> bool:
        """启用 MCP server
        
        Args:
            name: server 名称
            
        Returns:
            bool: 是否成功
        """
        if name not in self.servers:
            print(f"✗ 未知的 MCP server: {name}")
            return False
        
        self.servers[name].enabled = True
        self.save_config()
        print(f"✓ 已启用 MCP server: {name}")
        return True
    
    def disable_server(self, name: str) -> bool:
        """禁用 MCP server
        
        Args:
            name: server 名称
            
        Returns:
            bool: 是否成功
        """
        if name not in self.servers:
            print(f"✗ 未知的 MCP server: {name}")
            return False
        
        self.servers[name].enabled = False
        
        # 如果已连接,先断开
        if name in self.clients:
            asyncio.create_task(self.disconnect_server(name))
        
        self.save_config()
        print(f"✓ 已禁用 MCP server: {name}")
        return True
    
    def add_server(self, name: str, command: str, args: List[str] = None, 
                   env: Dict[str, str] = None) -> bool:
        """添加新的 MCP server
        
        Args:
            name: server 名称
            command: 启动命令
            args: 参数列表
            env: 环境变量
            
        Returns:
            bool: 是否成功
        """
        if name in self.servers:
            print(f"⚠ MCP server '{name}' 已存在")
            return False
        
        server = MCPServerConfig(
            name=name,
            command=command,
            args=args or [],
            env=env or {},
            enabled=True
        )
        
        self.servers[name] = server
        self.save_config()
        print(f"✓ 已添加 MCP server: {name}")
        return True
    
    def remove_server(self, name: str) -> bool:
        """移除 MCP server
        
        Args:
            name: server 名称
            
        Returns:
            bool: 是否成功
        """
        if name not in self.servers:
            print(f"✗ 未知的 MCP server: {name}")
            return False
        
        # 如果已连接,先断开
        if name in self.clients:
            asyncio.create_task(self.disconnect_server(name))
        
        del self.servers[name]
        self.save_config()
        print(f"✓ 已移除 MCP server: {name}")
        return True
    
    def get_all_tools(self) -> Dict[str, Dict]:
        """获取所有已连接 servers 的工具
        
        Returns:
            Dict[str, Dict]: {server_name: {tool_name: tool_info}}
        """
        all_tools = {}
        
        for name, client in self.clients.items():
            tools = client.get_tools_info()
            if tools:
                all_tools[name] = {tool["name"]: tool for tool in tools}
        
        return all_tools
    
    def get_tool_schemas_for_agent(self) -> List[Dict]:
        """获取所有工具的 schema (用于 Agent Function Calling)
        
        工具名格式: mcp_{server}_{tool}
        
        Returns:
            List[Dict]: 工具 schema 列表
        """
        schemas = []
        
        for server_name, client in self.clients.items():
            for tool in client.tools.values():
                schema = tool.to_function_schema()
                # 添加前缀避免命名冲突
                prefixed_name = f"mcp_{server_name}_{tool.name}"
                schema["function"]["name"] = prefixed_name
                schema["function"]["description"] = f"[{server_name}] {tool.description}"
                schemas.append(schema)
        
        return schemas
    
    async def call_tool(self, server_name: str, tool_name: str, arguments: Dict) -> str:
        """调用指定 server 的工具
        
        Args:
            server_name: server 名称
            tool_name: 工具名称
            arguments: 工具参数
            
        Returns:
            str: 执行结果
        """
        if server_name not in self.clients:
            return f"错误: MCP server '{server_name}' 未连接"
        
        client = self.clients[server_name]
        return await client.call_tool(tool_name, arguments)
    
    def list_servers(self) -> List[Dict]:
        """列出所有配置的 MCP servers
        
        Returns:
            List[Dict]: server 信息列表
        """
        result = []
        
        for name, server in self.servers.items():
            connected = name in self.clients
            tool_count = len(self.clients[name].tools) if connected else 0
            
            result.append({
                "name": name,
                "command": server.command,
                "args": server.args,
                "enabled": server.enabled,
                "connected": connected,
                "tools": tool_count
            })
        
        return result
