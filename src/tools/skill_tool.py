"""
Skill 管理工具
让 Agent 可以查看和管理已加载的 Skills
"""

from typing import TYPE_CHECKING, Dict, Any
from src.tools.base import Tool

if TYPE_CHECKING:
    from src.agent import ReActAgent


class SkillManagerTool(Tool):
    """管理 Agent Skills 的工具"""
    
    def __init__(self, agent: 'ReActAgent'):
        super().__init__(
            name="manage_skills",
            description="管理 Agent Skills。用法: manage_skills(action, skill_name=None)"
        )
        self.agent = agent
    
    def execute(self, action: str, skill_name: str = None) -> str:
        """执行 skill 管理操作
        
        Args:
            action: 操作类型 (list, refresh, enable, disable)
            skill_name: skill 名称(enable/disable 时需要)
            
        Returns:
            str: 操作结果
        """
        skill_manager = getattr(self.agent, 'skill_manager', None)
        if not skill_manager:
            return "✗ 错误: Skill 管理器未初始化"
        
        action = action.lower().strip()
        
        if action == "list":
            skills = skill_manager.list_skills()
            if not skills:
                return "暂无可用的 Agent Skills\n\n提示: 在 .rush/skills/ 或 ~/.rush/skills/ 目录下创建 skill 目录"
            
            lines = ["当前配置的 Agent Skills:\n"]
            for skill in skills:
                status = "✓ 启用" if skill['enabled'] else "✗ 禁用"
                source_tag = f"[{skill['source']}]"
                lines.append(f"• {skill['name']} {source_tag}")
                lines.append(f"  状态: {status}")
                lines.append(f"  描述: {skill['description']}")
                lines.append(f"  目录: {skill['directory']}\n")
            
            return "\n".join(lines)
        
        elif action == "refresh":
            success = skill_manager.refresh_skills()
            if success:
                # 重建 Agent 的系统提示词
                agent = self.agent
                agent.base_system_prompt = agent._build_system_prompt()
                
                count = len(skill_manager.skills)
                return f"✓ Agent Skills 已刷新\n总计: {count} 个\n新的 skills 将在下次对话时生效"
            else:
                return "✗ 刷新 skills 失败"
        
        elif action == "enable":
            if not skill_name:
                return "✗ 错误: 请指定要启用的 skill 名称"
            success = skill_manager.enable_skill(skill_name)
            if success:
                return f"✓ 已启用 skill '{skill_name}',下次对话时生效"
            return f"✗ 启用失败"
        
        elif action == "disable":
            if not skill_name:
                return "✗ 错误: 请指定要禁用的 skill 名称"
            success = skill_manager.disable_skill(skill_name)
            if success:
                return f"✓ 已禁用 skill '{skill_name}',下次对话时生效"
            return f"✗ 禁用失败"
        
        else:
            return f"✗ 未知操作: {action}\n支持的操作: list, refresh, enable, disable"
    
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
                            "enum": ["list", "refresh", "enable", "disable"]
                        },
                        "skill_name": {
                            "type": "string",
                            "description": "skill 名称(enable/disable 时需要)"
                        }
                    },
                    "required": ["action"]
                }
            }
        }
