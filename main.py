"""ReAct Agent CLI - 主启动程序"""

import os
import sys

from prompt_toolkit import prompt
from prompt_toolkit.history import FileHistory

from src.config import load_config
from src.agent import ReActAgent


def print_welcome():
    """打印欢迎信息"""
    print("="*60)
    print("Rush - 基于 ReAct 框架的 AI Agent")
    print("="*60)
    print("\n输入问题开始对话,或使用以下命令:")
    print("  /exit  - 退出程序")
    print("  /clear - 清除对话历史")
    print("  /help  - 显示帮助信息")
    print("="*60 + "\n")


def print_help(agent: ReActAgent):
    """打印帮助信息
    
    Args:
        agent: ReAct Agent 实例
    """
    print("\n可用命令:")
    print("  /exit  - 退出程序")
    print("  /clear - 清除对话历史")
    print("  /help  - 显示帮助信息")
    print("\n可用工具:")
    for tool in agent.get_available_tools():
        print(f"  {tool.description}")
    print()


def handle_command(command: str, agent: ReActAgent) -> bool:
    """处理内置命令
    
    Args:
        command: 用户输入的命令
        agent: ReAct Agent 实例
        
    Returns:
        bool: 是否应该继续运行
    """
    if command.lower() == '/exit':
        print("再见!")
        return False
    elif command.lower() == '/clear':
        agent.clear_history()
        return True
    elif command.lower() == '/help':
        print_help(agent)
        return True
    else:
        return True


def main():
    """主函数 - REPL 交互界面"""
    print_welcome()
    
    # 加载配置
    config_path = load_config()
    
    # 初始化 Agent
    try:
        agent = ReActAgent(config_path)
        print("\n✓ Agent 初始化成功")
        print("="*60 + "\n")
    except Exception as e:
        print(f"\n✗ Agent 初始化失败: {str(e)}")
        print("\n请检查:")
        print("1. 配置文件 ~/.rush/config.json 中的 API Key 是否正确")
        print("2. 网络连接是否正常")
        print("3. DeepSeek API 服务是否可用")
        sys.exit(1)
    
    # 设置历史记录文件
    history_path = os.path.expanduser("~/.rush/history.txt")
    os.makedirs(os.path.dirname(history_path), exist_ok=True)
    
    # REPL 循环
    while True:
        try:
            user_input = prompt(
                "[Rush] > ",
                history=FileHistory(history_path)
            ).strip()
            
            if not user_input:
                continue
            
            # 处理内置命令
            if not handle_command(user_input, agent):
                break
            
            # 运行 ReAct Agent
            result = agent.run(user_input)
            
        except KeyboardInterrupt:
            print("\n\n再见!")
            break
        except EOFError:
            print("\n检测到输入结束,继续等待输入...")
            continue
        except Exception as e:
            print(f"\n错误: {str(e)}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    main()
