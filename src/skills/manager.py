"""
Agent Skill 管理器
参考 Claude Code 的 Skill 设计
"""

import os
import json
from typing import Dict, List, Optional
from pathlib import Path


class AgentSkill:
    """Agent Skill 定义
    
    每个 skill 是一个目录,包含:
    - SKILL.md: skill 的内容和行为准则 (包含 name 和 description)
    
    参考 Claude Code 的 Skill 设计
    """
    
    def __init__(self, name: str, description: str, content: str, enabled: bool = True):
        self.name = name
        self.description = description
        self.content = content  # SKILL.md 的内容
        self.enabled = enabled
    
    def to_system_prompt(self) -> str:
        """转换为系统提示词片段"""
        if not self.enabled:
            return ""
        return f"\n\n# {self.name}\n{self.description}\n\n{self.content}"


class SkillManager:
    """Agent Skill 管理器
    
    负责:
    - 从全局和项目级别加载 skills
    - 动态启用/禁用 skills
    - 生成包含 skills 的系统提示词
    - 支持运行时刷新
    
    Skills 搜索顺序:
    1. 全局 Skills: ~/.rush/skills/
    2. 项目 Skills: .rush/skills/ (覆盖同名的全局 skill)
    """
    
    def __init__(self, global_skills_dir: str = None, local_skills_dir: str = None):
        """初始化
        
        Args:
            global_skills_dir: 全局 Skills 目录,默认为 ~/.rush/skills
            local_skills_dir: 项目 Skills 目录,默认为 .rush/skills
        """
        if global_skills_dir is None:
            global_skills_dir = os.path.expanduser("~/.rush/skills")
        
        if local_skills_dir is None:
            local_skills_dir = os.path.join(os.getcwd(), '.rush', 'skills')
        
        self.global_skills_dir = global_skills_dir
        self.local_skills_dir = local_skills_dir
        self.skills: Dict[str, AgentSkill] = {}
        
        # 确保目录存在
        os.makedirs(global_skills_dir, exist_ok=True)
        os.makedirs(local_skills_dir, exist_ok=True)
        
        # 加载 skills
        self.load_skills()
    
    def load_skills(self) -> bool:
        """从全局和项目级别加载所有 skills
        
        Skills 目录结构 (参考 Claude Code):
        skills/
          ├── skill-name-1/
          │   └── SKILL.md       # 文件内包含 name 和 description
          └── skill-name-2/
              └── SKILL.md
        
        SKILL.md 格式:
        ---
        name: Skill Name
        description: Skill description
        ---
        
        # Skill content here...
        
        加载顺序:
        1. 先加载全局 skills (~/.rush/skills/)
        2. 再加载项目 skills (.rush/skills/),同名会覆盖全局 skill
        
        Returns:
            bool: 是否成功
        """
        try:
            self.skills = {}
            
            # 1. 加载全局 skills
            global_count = self._load_skills_from_dir(self.global_skills_dir, "全局")
            
            # 2. 加载项目 skills (覆盖同名)
            local_count = self._load_skills_from_dir(self.local_skills_dir, "项目")
            
            total = len(self.skills)
            print(f"✓ 已加载 {total} 个 Agent Skills (全局: {global_count}, 项目: {local_count})")
            return True
            
        except Exception as e:
            print(f"✗ 加载 skills 失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _load_skills_from_dir(self, skills_dir: str, source: str) -> int:
        """从指定目录加载 skills
        
        Args:
            skills_dir: skills 目录路径
            source: 来源标识 (用于日志)
            
        Returns:
            int: 加载的 skill 数量
        """
        count = 0
        skills_path = Path(skills_dir)
        
        if not skills_path.exists():
            return 0
        
        # 遍历所有子目录
        for skill_dir in skills_path.iterdir():
            if not skill_dir.is_dir():
                continue
            
            skill_file = skill_dir / "SKILL.md"
            if not skill_file.exists():
                continue
            
            # 读取 skill 文件内容
            with open(skill_file, 'r', encoding='utf-8') as f:
                raw_content = f.read()
            
            # 解析 frontmatter
            name, description, content = self._parse_skill_file(raw_content, skill_dir.name)
            
            skill = AgentSkill(
                name=name,
                description=description,
                content=content,
                enabled=True
            )
            
            self.skills[name] = skill
            count += 1
        
        return count
    
    def _parse_skill_file(self, content: str, default_name: str) -> tuple:
        """解析 skill 文件,提取 name, description 和内容
        
        支持两种格式:
        1. YAML frontmatter:
           ---
           name: Skill Name
           description: Description
           ---
           Content...
        
        2. Markdown 标题:
           # Skill Name
           Description paragraph...
           
           Content...
        
        Args:
            content: 文件原始内容
            default_name: 默认名称(目录名)
            
        Returns:
            tuple: (name, description, content)
        """
        # 尝试解析 YAML frontmatter
        if content.startswith('---'):
            parts = content.split('---', 2)
            if len(parts) >= 3:
                frontmatter = parts[1].strip()
                body = parts[2].strip()
                
                # 解析 YAML
                name = default_name
                description = ""
                
                for line in frontmatter.split('\n'):
                    line = line.strip()
                    if line.startswith('name:'):
                        name = line[5:].strip().strip('"').strip("'")
                    elif line.startswith('description:'):
                        description = line[12:].strip().strip('"').strip("'")
                
                return name, description, body
        
        # 尝试从 Markdown 标题提取
        lines = content.split('\n', 2)
        if lines and lines[0].startswith('# '):
            name = lines[0][2:].strip()
            
            # 第二行可能是描述
            description = ""
            body_start = 1
            
            if len(lines) > 1 and lines[1].strip() and not lines[1].startswith('#'):
                description = lines[1].strip()
                body_start = 2
            
            body = '\n'.join(lines[body_start:]) if len(lines) > body_start else ""
            return name, description, body
        
        #  fallback: 使用目录名
        return default_name, "", content
    
    def refresh_skills(self) -> bool:
        """刷新 skills (重新扫描文件系统)
        
        Returns:
            bool: 是否成功
        """
        print("正在刷新 Agent Skills...")
        return self.load_skills()
    
    def enable_skill(self, skill_name: str) -> bool:
        """启用 skill
        
        Args:
            skill_name: skill 名称
            
        Returns:
            bool: 是否成功
        """
        if skill_name not in self.skills:
            print(f"✗ Skill '{skill_name}' 不存在")
            return False
        
        self.skills[skill_name].enabled = True
        self._save_metadata()
        print(f"✓ 已启用 skill: {skill_name}")
        return True
    
    def disable_skill(self, skill_name: str) -> bool:
        """禁用 skill
        
        Args:
            skill_name: skill 名称
            
        Returns:
            bool: 是否成功
        """
        if skill_name not in self.skills:
            print(f"✗ Skill '{skill_name}' 不存在")
            return False
        
        self.skills[skill_name].enabled = False
        self._save_metadata()
        print(f"✓ 已禁用 skill: {skill_name}")
        return True
    
    def get_enabled_skills_text(self) -> str:
        """获取所有已启用 skills 的系统提示词
        
        Returns:
            str: 格式化的系统提示词
        """
        enabled_skills = [s for s in self.skills.values() if s.enabled]
        
        if not enabled_skills:
            return ""
        
        sections = []
        for skill in enabled_skills:
            sections.append(skill.to_system_prompt())
        
        return "\n".join(sections)
    
    def list_skills(self) -> List[Dict[str, any]]:
        """列出所有 skills
        
        Returns:
            List[Dict]: skill 信息列表
        """
        result = []
        for skill in self.skills.values():
            # 判断来源: 检查 skill 目录是否存在于项目级别
            local_skill_dir = os.path.join(self.local_skills_dir, skill.name.replace(' ', '-').lower())
            global_skill_dir = os.path.join(self.global_skills_dir, skill.name.replace(' ', '-').lower())
            
            if os.path.exists(local_skill_dir):
                source = "项目"
            elif os.path.exists(global_skill_dir):
                source = "全局"
            else:
                # fallback: 尝试原始名称
                if os.path.exists(os.path.join(self.local_skills_dir, skill.name)):
                    source = "项目"
                else:
                    source = "全局"
            
            result.append({
                "name": skill.name,
                "description": skill.description or "无描述",
                "enabled": skill.enabled,
                "source": source,
                "directory": skill.name
            })
        
        return result
    
    def _save_metadata(self):
        """保存元数据 (当前未使用,保留接口)"""
        pass
    
    def _load_metadata(self) -> Dict:
        """加载元数据 (当前未使用,保留接口)"""
        return {}
