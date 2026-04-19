"""文件读取工具"""

import os
from typing import Dict, Any

from src.tools.base import Tool


class FileReadTool(Tool):
    """文件读取工具 - 读取指定文件的内容"""
    
    def __init__(self):
        super().__init__(
            name="file_read",
            description="读取文件内容。用法: file_read(path), 例如 file_read('/path/to/file.txt')"
        )
    
    def execute(self, path: str) -> str:
        """读取文件内容
        
        Args:
            path: 文件路径
            
        Returns:
            str: 文件内容或错误信息
        """
        try:
            # 安全检查:防止读取敏感文件
            if not self._is_safe_path(path):
                return f"错误: 不允许访问该路径 '{path}'"
            
            # 检查文件是否存在
            if not os.path.exists(path):
                return f"错误: 文件不存在 '{path}'"
            
            # 检查是否是文件(不是目录)
            if not os.path.isfile(path):
                return f"错误: 路径不是文件 '{path}'"
            
            # 检查文件大小(限制读取大文件)
            file_size = os.path.getsize(path)
            max_size = 1024 * 1024  # 1MB
            if file_size > max_size:
                return f"错误: 文件太大 ({file_size / 1024:.2f} KB),最大支持 {max_size / 1024} KB"
            
            # 读取文件内容
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 如果内容太长,截断
            max_length = 10000  # 最大字符数
            if len(content) > max_length:
                content = content[:max_length] + f"\n\n... (内容已截断,总长度: {len(content)} 字符)"
            
            return f"文件内容:\n{content}"
            
        except UnicodeDecodeError:
            return f"错误: 文件编码不是 UTF-8,无法读取 '{path}'"
        except PermissionError:
            return f"错误: 没有权限读取文件 '{path}'"
        except Exception as e:
            return f"错误: 读取文件失败 - {str(e)}"
    
    def _is_safe_path(self, path: str) -> bool:
        """检查路径是否安全
        
        Args:
            path: 文件路径
            
        Returns:
            bool: 是否安全
        """
        # 转换为绝对路径
        abs_path = os.path.abspath(path)
        
        # 禁止访问的系统目录
        forbidden_paths = [
            '/etc/',
            '/usr/',
            '/var/',
            '/root/',
            '/sys/',
            '/proc/',
        ]
        
        # 检查是否在禁止列表中
        for forbidden in forbidden_paths:
            if abs_path.startswith(forbidden):
                return False
        
        # 禁止访问隐藏文件(以 . 开头)
        basename = os.path.basename(abs_path)
        if basename.startswith('.') and basename not in ['.gitignore', '.env']:
            return False
        
        return True
    
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
                        "path": {
                            "type": "string",
                            "description": "文件的绝对路径或相对路径,如 'README.md' 或 '/home/user/file.txt'"
                        }
                    },
                    "required": ["path"]
                }
            }
        }
