"""天气查询工具"""

from src.tools.base import Tool


class WeatherTool(Tool):
    """天气查询工具 - 查询天气(模拟)"""
    
    def __init__(self):
        super().__init__(
            name="weather",
            description="查询天气。用法: weather(city), 例如 weather('北京')"
        )
    
    def execute(self, city: str) -> str:
        """查询天气信息
        
        Args:
            city: 城市名称
            
        Returns:
            str: 天气信息
        """
        # 这里可以集成真实的天气 API
        return f"[天气信息] {city} 的天气: 晴, 温度 20°C (这是一个模拟数据)"
