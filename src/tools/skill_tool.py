"""
Skill 管理工具
让 Agent 可以查看和管理已加载的 Skills
采用 Claude Code 的设计模式，将 skills 列表嵌入到工具描述中
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
    
    def execute(self, action: str = None, skill_name: str = None, command: str = None) -> str:
        """执行 skill 管理操作
        
        Args:
            action: 操作类型 (list, refresh, enable, disable)
            skill_name: skill 名称(enable/disable 时需要)
            command: skill 命令名称(用于执行 skill)
            
        Returns:
            str: 操作结果
        """
        skill_manager = getattr(self.agent, 'skill_manager', None)
        if not skill_manager:
            return "✗ 错误: Skill 管理器未初始化"
        
        # 如果提供了 command，则执行 skill
        if command is not None:
            return self._execute_skill(skill_manager, command)
        
        if action is None:
            return "✗ 错误: 请指定操作类型或 command"
        
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
    
    def _execute_skill(self, skill_manager, command: str) -> str:
        """执行指定的 skill
        
        Args:
            skill_manager: Skill 管理器实例
            command: skill 名称
            
        Returns:
            str: skill 内容
        """
        skill = skill_manager.skills.get(command)
        
        if not skill:
            return f"✗ Skill '{command}' 不存在或未启用"
        
        if not skill.enabled:
            return f"✗ Skill '{command}' 已被禁用"
        
        # 返回 Claude Code 风格的响应格式
        result = f"<command-message>The \"{command}\" skill is running</command-message>\n"
        result += f"<command-name>{command}</command-name>\n\n"
        result += skill.to_system_prompt()
        
        return result
    
    def get_schema(self) -> Dict[str, Any]:
        """获取工具的 Function Calling schema
        
        采用 Claude Code 的设计模式，将 skills 列表嵌入到工具描述中
        """
        # 获取所有启用的 skills
        skill_manager = getattr(self.agent, 'skill_manager', None)
        enabled_skills = []
        
        if skill_manager:
            all_skills = skill_manager.list_skills()
            enabled_skills = [s for s in all_skills if s['enabled']]
        
        # 构建 available_skills 文本
        if enabled_skills:
            skills_text = "\n".join([
                f"<skill>\n<name>{s['name']}</name>\n<description>{s['description']}</description>\n<location>{s['source']}</location>\n</skill>"
                for s in enabled_skills
            ])
        else:
            skills_text = "No skills available"
        
        # 构建 Claude Code 风格的工具描述
        description = f"""Execute a skill within the main conversation

<skills_instructions>
When users ask you to perform tasks, check if any of the available skills below can help complete the task more effectively. Skills provide specialized capabilities and domain knowledge.

How to use skills:
- Invoke skills using this tool with the skill name only (no arguments)
- When you invoke a skill, you will see <command-message>The skill is loading</command-message>
- The skill's prompt will expand and provide detailed instructions on how to complete the task
- Examples:
  - command: "pdf" - invoke the pdf skill
  - command: "csv" - invoke the csv skill

Important:
- Only use skills listed in <available_skills> below
- Do not invoke a skill that is already running
- Do not use this tool for built-in CLI commands
</skills_instructions>

<available_skills>
{skills_text}
</available_skills>
"""
        
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "description": "操作类型 (list, refresh, enable, disable)",
                            "enum": ["list", "refresh", "enable", "disable"]
                        },
                        "skill_name": {
                            "type": "string",
                            "description": "skill 名称(enable/disable 时需要)"
                        },
                        "command": {
                            "type": "string",
                            "description": "要执行的 skill 命令名称 (例如: 'pdf', 'csv')"
                        }
                    },
                    "required": []
                }
            }
        }
