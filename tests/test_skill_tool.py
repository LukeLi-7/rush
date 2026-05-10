#!/usr/bin/env python3
"""
测试 Skill 工具的新机制
验证 Claude Code 风格的 Skill 管理
"""

import sys
import os

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from src.agent import ReActAgent

def test_skill_tool_mechanism():
    """测试新的 Skill 工具机制"""
    
    print("=" * 60)
    print("Skill 工具机制测试")
    print("=" * 60)
    
    # 1. 初始化 Agent
    print("\n[1] 初始化 Agent...")
    agent = ReActAgent()
    
    print(f"✓ Agent 已初始化")
    print(f"  Provider: {agent.provider.get_provider_name()}")
    print(f"  可用工具: {list(agent.tools.keys())}")
    
    # 2. 检查 Skill 管理工具
    print("\n[2] 检查 Skill 管理工具...")
    if "manage_skills" in agent.tools:
        print("✓ Skill 管理工具已注册")
        skill_tool = agent.tools["manage_skills"]
        
        # 3. 测试获取工具 schema
        print("\n[3] 测试工具 schema...")
        schema = skill_tool.get_schema()
        print("✓ 成功获取工具 schema")
        print(f"  工具名称: {schema['function']['name']}")
        print(f"  参数: {list(schema['function']['parameters']['properties'].keys())}")
        
        # 检查描述中是否包含 skills 列表
        description = schema['function']['description']
        if "<available_skills>" in description:
            print("✓ 工具描述中包含 skills 列表")
        else:
            print("⚠ 工具描述中未找到 skills 列表")
        
        if "<skills_instructions>" in description:
            print("✓ 工具描述中包含使用说明")
        else:
            print("⚠ 工具描述中未找到使用说明")
        
        # 4. 测试列出 skills
        print("\n[4] 测试列出 skills...")
        result = skill_tool.execute(action="list")
        print(result)
        
        # 5. 测试执行 skill（如果有可用的 skill）
        print("\n[5] 测试执行 skill...")
        skills = agent.skill_manager.list_skills()
        enabled_skills = [s for s in skills if s['enabled']]
        
        if enabled_skills:
            test_skill_name = enabled_skills[0]['name']
            print(f"  测试执行 skill: {test_skill_name}")
            result = skill_tool.execute(command=test_skill_name)
            if "<command-message>" in result:
                print("✓ Skill 执行返回正确的格式")
                print(f"  包含 command-message 标签")
            else:
                print("⚠ Skill 执行格式不符合预期")
        else:
            print("  没有可用的 skills 进行测试")
        
        # 6. 检查系统提示词
        print("\n[6] 检查系统提示词...")
        system_prompt = agent.base_system_prompt
        if "=== Agent Skills ===" not in system_prompt:
            print("✓ 系统提示词中不再包含 Skills 注入")
        else:
            print("⚠ 系统提示词中仍然包含 Skills 注入")
        
    else:
        print("✗ Skill 管理工具未注册")
    
    print("\n" + "=" * 60)
    print("测试完成!")
    print("=" * 60)

if __name__ == "__main__":
    try:
        test_skill_tool_mechanism()
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
