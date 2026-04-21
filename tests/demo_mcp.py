"""
MCP 功能演示

展示如何在 Agent 中使用 MCP 功能
"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def demo_mcp_usage():
    """演示 MCP 使用流程"""
    print("="*60)
    print("MCP 功能演示")
    print("="*60)
    
    from src.agent import ReActAgent
    
    # 1. 创建 Agent
    print("\n步骤 1: 创建 Agent")
    print("-" * 60)
    agent = ReActAgent()
    
    # 2. 查看已配置的 MCP servers
    print("\n\n步骤 2: 查看已配置的 MCP servers")
    print("-" * 60)
    result = agent.run("使用 manage_mcp 工具列出所有配置的 MCP servers")
    print(f"\n结果:\n{result}")
    
    # 3. 连接 MCP server
    print("\n\n步骤 3: 连接 filesystem MCP server")
    print("-" * 60)
    result = agent.run("使用 manage_mcp 连接 filesystem server")
    print(f"\n结果:\n{result}")
    
    # 4. 再次查看 servers 状态
    print("\n\n步骤 4: 确认 server 已连接")
    print("-" * 60)
    result = agent.run("使用 manage_mcp 列出 servers,确认 filesystem 已连接")
    print(f"\n结果:\n{result}")
    
    # 5. 使用 MCP 工具
    print("\n\n步骤 5: 使用 MCP filesystem 工具读取文件")
    print("-" * 60)
    result = agent.run("请使用 mcp_filesystem_read_text_file 工具读取 README.md 文件的前20行")
    print(f"\n结果:\n{result[:500]}...")
    
    print("\n\n" + "="*60)
    print("演示完成!")
    print("="*60)
    print("""
提示:
- MCP tools 命名格式: mcp_{server_name}_{tool_name}
- 例如: mcp_filesystem_read_text_file
- 可用的 filesystem 工具:
  * read_text_file - 读取文本文件
  * list_directory - 列出目录
  * write_file - 写入文件
  * edit_file - 编辑文件
  * create_directory - 创建目录
  * search_files - 搜索文件
  ... 等等
""")


if __name__ == "__main__":
    try:
        demo_mcp_usage()
    except Exception as e:
        print(f"\n✗ 演示失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
