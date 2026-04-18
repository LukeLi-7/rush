"""计算器工具"""

from src.tools.base import Tool


class CalculatorTool(Tool):
    """计算器工具 - 执行数学计算"""
    
    def __init__(self):
        super().__init__(
            name="calculator",
            description="执行数学计算。用法: calculator(expression), 例如 calculator('2 + 2')"
        )
    
    def execute(self, expression: str) -> str:
        """执行数学表达式计算
        
        Args:
            expression: 数学表达式字符串
            
        Returns:
            str: 计算结果或错误信息
        """
        try:
            # 安全的表达式求值
            result = eval(expression, {"__builtins__": {}}, {})
            return f"计算结果: {result}"
        except Exception as e:
            return f"计算错误: {str(e)}"
