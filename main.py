"""ReAct Agent CLI - 主启动程序"""

import os
import sys
import signal

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


def clear_screen():
    """清除控制台屏幕"""
    import platform
    system = platform.system()
    if system == 'Windows':
        os.system('cls')
    else:
        # macOS, Linux
        os.system('clear')


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
        clear_screen()
        print_welcome()
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
    
    # 中断标志 (用于在 agent 执行时检测 Ctrl+C)
    import threading
    interrupt_event = threading.Event()
    
    def signal_handler(sig, frame):
        """处理 Ctrl+C 信号 - 直接抛出异常中断执行"""
        raise KeyboardInterrupt("\n\n⚠️  操作已中断,可以输入新问题")
    
    # 注册信号处理器
    signal.signal(signal.SIGINT, signal_handler)
    
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
            if user_input.startswith('/'):
                if not handle_command(user_input, agent):
                    break
                continue  # 命令处理后跳过 Agent 执行
            
            # 重置中断标志
            interrupt_event.clear()
            
            # 运行 ReAct Agent
            result = agent.run(user_input)
            
        except KeyboardInterrupt:
            # prompt_toolkit 的 KeyboardInterrupt (输入阶段)
            print("\n\n⚠️  操作已中断,可以输入新问题")
            agent.clear_history()
            continue
        except EOFError:
            print("\n检测到输入结束,继续等待输入...")
            continue
        except Exception as e:
            print(f"\n错误: {str(e)}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    main()
