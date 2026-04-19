"""命令执行工具"""

import subprocess
import shlex
from typing import Dict, Any, List

from src.tools.base import Tool


class CommandExecTool(Tool):
    """命令执行工具 - 安全地执行系统命令
    
    ⚠️ 注意: 此工具具有潜在安全风险,已添加严格的安全检查
    """
    
    def __init__(self):
        super().__init__(
            name="command_exec",
            description="执行系统命令。用法: command_exec(command), 例如 command_exec('ls -la')"
        )
        
        # 允许的命令白名单
        self.allowed_commands = {
            # 文件操作
            'ls', 'dir', 'pwd', 'cd',
            'cat', 'head', 'tail', 'wc',
            'find', 'grep', 'sort', 'uniq',
            
            # 系统信息
            'uname', 'hostname', 'whoami',
            'date', 'cal', 'uptime',
            
            # 网络
            'ping', 'curl', 'wget',
            
            # 开发工具
            'python', 'python3', 'pip', 'pip3',
            'git', 'npm', 'node',
            
            # 文本处理
            'echo', 'printf',
            'awk', 'sed',
        }
        
        # 禁止的命令/关键字黑名单
        self.forbidden_patterns = [
            'rm -rf', 'rm -f',  # 删除文件
            'dd if=',  # 磁盘操作
            'mkfs', 'fdisk',  # 格式化
            'chmod 777',  # 危险权限
            'sudo', 'su ',  # 提权
            '> /dev/',  # 设备文件
            '| bash', '| sh',  # 管道执行
            '; rm', '& rm',  # 命令注入
            '`', '$(',  # 命令替换
        ]
    
    def execute(self, command: str) -> str:
        """执行系统命令
        
        Args:
            command: 要执行的命令
            
        Returns:
            str: 命令输出或错误信息
        """
        try:
            # 安全检查
            if not self._is_safe_command(command):
                return f"错误: 不允许执行该命令 (安全限制)"
            
            # 解析命令
            cmd_parts = shlex.split(command)
            if not cmd_parts:
                return "错误: 命令为空"
            
            base_command = cmd_parts[0]
            
            # 检查是否在白名单中
            if base_command not in self.allowed_commands:
                return f"错误: 命令 '{base_command}' 不在允许列表中\n允许的命令: {', '.join(sorted(self.allowed_commands))}"
            
            # 执行命令 (设置超时和限制)
            result = subprocess.run(
                cmd_parts,
                capture_output=True,
                text=True,
                timeout=10,  # 10秒超时
                cwd=None,  # 在当前目录执行
                env=None,  # 使用当前环境变量
            )
            
            # 组合输出
            output = []
            if result.stdout:
                output.append(f"标准输出:\n{result.stdout}")
            if result.stderr:
                output.append(f"错误输出:\n{result.stderr}")
            
            if not output:
                return f"命令执行成功 (无输出)\n退出码: {result.returncode}"
            
            output_text = "\n".join(output)
            
            # 限制输出长度
            max_length = 5000
            if len(output_text) > max_length:
                output_text = output_text[:max_length] + f"\n\n... (输出已截断)"
            
            return f"退出码: {result.returncode}\n{output_text}"
            
        except subprocess.TimeoutExpired:
            return "错误: 命令执行超时 (超过 10 秒)"
        except FileNotFoundError:
            return f"错误: 命令不存在 '{command}'"
        except PermissionError:
            return f"错误: 没有权限执行命令 '{command}'"
        except Exception as e:
            return f"错误: 执行命令失败 - {str(e)}"
    
    def _is_safe_command(self, command: str) -> bool:
        """检查命令是否安全
        
        Args:
            command: 要检查的命令
            
        Returns:
            bool: 是否安全
        """
        # 检查是否为空
        if not command or not command.strip():
            return False
        
        # 检查黑名单
        command_lower = command.lower()
        for pattern in self.forbidden_patterns:
            if pattern in command_lower:
                return False
        
        # 检查是否包含危险字符
        dangerous_chars = [';', '|', '&', '`', '$', '>', '<']
        for char in dangerous_chars:
            if char in command and char not in ['|']:  # 允许 grep | sort 这样的管道
                # 更细致的检查
                if self._has_dangerous_usage(command, char):
                    return False
        
        # 检查命令长度
        if len(command) > 500:
            return False
        
        return True
    
    def _has_dangerous_usage(self, command: str, char: str) -> bool:
        """检查字符是否有危险用法
        
        Args:
            command: 命令字符串
            char: 要检查的字符
            
        Returns:
            bool: 是否有危险
        """
        if char == '|':
            # 允许简单的管道,但不允许多重管道
            if command.count('|') > 2:
                return True
        elif char in [';', '&']:
            # 不允许命令分隔符
            return True
        elif char in ['`', '$']:
            # 不允许命令替换
            return True
        elif char in ['>', '<']:
            # 不允许重定向到特殊位置
            if any(path in command for path in ['/dev/', '/etc/', '/root/']):
                return True
        
        return False
    
    def get_schema(self) -> Dict[str, Any]:
        """获取工具的 Function Calling schema"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description + "\n⚠️ 注意: 只能执行安全的只读命令,如 ls, cat, grep 等",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "string",
                            "description": "要执行的命令,如 'ls -la' 或 'grep pattern file.txt'"
                        }
                    },
                    "required": ["command"]
                }
            }
        }
