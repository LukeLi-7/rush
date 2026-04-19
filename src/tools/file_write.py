"""文件写入工具"""

import os
from typing import Dict, Any

from src.tools.base import Tool


class FileWriteTool(Tool):
    """文件写入工具 - 将内容写入指定文件"""
    
    def __init__(self):
        super().__init__(
            name="file_write",
            description="写入文件内容。用法: file_write(path, content), 例如 file_write('/path/to/file.txt', 'Hello World')"
        )
    
    def execute(self, path: str, content: str) -> str:
        """写入文件内容
        
        Args:
            path: 文件路径
            content: 要写入的内容
            
        Returns:
            str: 操作结果或错误信息
        """
        try:
            # 安全检查:防止写入敏感位置
            if not self._is_safe_path(path):
                return f"错误: 不允许写入该路径 '{path}'"
            
            # 检查内容长度
            max_length = 50000  # 最大 50KB
            if len(content) > max_length:
                return f"错误: 内容太长 ({len(content)} 字符),最大支持 {max_length} 字符"
            
            # 确保目录存在
            directory = os.path.dirname(path)
            if directory and not os.path.exists(directory):
                os.makedirs(directory, exist_ok=True)
            
            # 如果文件已存在,给出警告
            if os.path.exists(path):
                file_size = os.path.getsize(path)
                warning = f"警告: 文件已存在 (大小: {file_size} 字节),将被覆盖\n"
            else:
                warning = ""
            
            # 写入文件
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            # 获取写入后的文件大小
            final_size = os.path.getsize(path)
            
            return f"{warning}成功写入文件: {path}\n文件大小: {final_size} 字节"
            
        except PermissionError:
            return f"错误: 没有权限写入文件 '{path}'"
        except IsADirectoryError:
            return f"错误: 路径是目录,不是文件 '{path}'"
        except Exception as e:
            return f"错误: 写入文件失败 - {str(e)}"
    
    def _is_safe_path(self, path: str) -> bool:
        """检查路径是否安全
        
        Args:
            path: 文件路径
            
        Returns:
            bool: 是否安全
        """
        # 转换为绝对路径
        abs_path = os.path.abspath(path)
        
        # 禁止写入的系统目录
        forbidden_paths = [
            '/etc/',
            '/usr/',
            '/var/',
            '/root/',
            '/sys/',
            '/proc/',
            '/bin/',
            '/sbin/',
        ]
        
        # 检查是否在禁止列表中
        for forbidden in forbidden_paths:
            if abs_path.startswith(forbidden):
                return False
        
        # 禁止写入隐藏文件(以 . 开头)
        basename = os.path.basename(abs_path)
        if basename.startswith('.'):
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
                            "description": "文件的绝对路径或相对路径,如 'output.txt' 或 '/home/user/file.txt'"
                        },
                        "content": {
                            "type": "string",
                            "description": "要写入文件的内容"
                        }
                    },
                    "required": ["path", "content"]
                }
            }
        }
