"""ReAct Agent CLI - 基于 ReAct 框架的命令行 AI Agent"""

import json
import os
import re
import sys
from pathlib import Path
from typing import Optional

from openai import OpenAI
from prompt_toolkit import prompt
from prompt_toolkit.history import FileHistory


class Tool:
    """工具基类"""

    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description

    def execute(self, *args, **kwargs) -> str:
        raise NotImplementedError


class CalculatorTool(Tool):
    """计算器工具"""

    def __init__(self):
        super().__init__(
            name="calculator",
            description="执行数学计算。用法: calculator(expression), 例如 calculator('2 + 2')"
        )

    def execute(self, expression: str) -> str:
        try:
            # 安全的表达式求值
            result = eval(expression, {"__builtins__": {}}, {})
            return f"计算结果: {result}"
        except Exception as e:
            return f"计算错误: {str(e)}"


class SearchTool(Tool):
    """搜索工具(模拟)"""

    def __init__(self):
        super().__init__(
            name="search",
            description="搜索信息。用法: search(query), 例如 search('Python ReAct 框架')"
        )

    def execute(self, query: str) -> str:
        # 这里可以集成真实的搜索引擎 API
        return f"[搜索结果] 关于 '{query}' 的信息: (这是一个模拟搜索结果)"


class WeatherTool(Tool):
    """天气查询工具(模拟)"""

    def __init__(self):
        super().__init__(
            name="weather",
            description="查询天气。用法: weather(city), 例如 weather('北京')"
        )

    def execute(self, city: str) -> str:
        # 这里可以集成真实的天气 API
        return f"[天气信息] {city} 的天气: 晴, 温度 20°C (这是一个模拟数据)"


class ReActAgent:
    """ReAct 框架 AI Agent"""

    def __init__(self, config_path: str = None):
        # 加载配置
        if config_path is None:
            config_path = os.path.expanduser("~/.rush/config.json")

        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)

        # 验证 API Key
        api_key = config.get("api_key", "")
        if not api_key or api_key == "your_deepseek_api_key_here":
            raise ValueError("API Key 未配置或无效。请编辑配置文件 ~/.rush/config.json")

        # 初始化 OpenAI 客户端
        self.client = OpenAI(
            api_key=api_key,
            base_url=config.get("base_url", "https://api.deepseek.com/v1")
        )
        self.model = config.get("model", "deepseek-chat")

        # 注册工具
        self.tools = {
            "calculator": CalculatorTool(),
            "search": SearchTool(),
            "weather": WeatherTool()
        }

        # 最大迭代次数
        self.max_iterations = 5

        # 构建系统提示
        self.system_prompt = self._build_system_prompt()

        # 对话历史
        self.conversation_history = []

    def _build_system_prompt(self) -> str:
        """构建系统提示"""
        tool_descriptions = "\n".join([
            f"- {tool.name}: {tool.description}"
            for tool in self.tools.values()
        ])

        return f"""你是一个智能助手,使用 ReAct(Reasoning + Acting)框架来解决问题。

可用工具:
{tool_descriptions}

回答格式要求:
你必须按照以下格式思考和行动:

Thought: <你的思考过程,分析问题和下一步行动>
Action: <工具名称>(<参数>)
Observation: <工具返回的结果>

你可以重复 Thought/Action/Observation 循环多次,直到找到答案。

当你确定知道最终答案时,使用以下格式:
Thought: 我已经找到了答案
Final Answer: <你的最终答案>

重要规则:
1. 每次只能执行一个 Action
2. 必须等待 Observation 结果后再进行下一步 Thought
3. 如果不需要工具,直接给出 Final Answer
4. 最多进行 {self.max_iterations} 次迭代

现在开始!"""

    def _parse_react_response(self, response: str) -> dict:
        """解析 ReAct 响应"""
        result = {
            "thought": None,
            "action": None,
            "action_input": None,
            "final_answer": None
        }

        # 提取 Thought
        thought_match = re.search(r'Thought:\s*(.+?)(?=Action:|Final Answer:|$)',
                                  response, re.DOTALL)
        if thought_match:
            result["thought"] = thought_match.group(1).strip()

        # 提取 Final Answer
        final_answer_match = re.search(r'Final Answer:\s*(.+)', response, re.DOTALL)
        if final_answer_match:
            result["final_answer"] = final_answer_match.group(1).strip()
            return result

        # 提取 Action
        action_match = re.search(r'Action:\s*(\w+)\(([^)]*)\)', response)
        if action_match:
            result["action"] = action_match.group(1)
            result["action_input"] = action_match.group(2).strip().strip("'\"")

        return result

    def _execute_action(self, action_name: str, action_input: str) -> str:
        """执行工具动作"""
        if action_name not in self.tools:
            return f"错误: 未知工具 '{action_name}'"

        tool = self.tools[action_name]
        try:
            return tool.execute(action_input)
        except Exception as e:
            return f"工具执行错误: {str(e)}"

    def run(self, query: str) -> str:
        """运行 ReAct 循环"""
        print(f"\n{'=' * 60}")
        print(f"问题: {query}")
        print(f"{'=' * 60}\n")

        # 添加用户问题到历史
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": query}
        ]

        iteration = 0
        while iteration < self.max_iterations:
            iteration += 1
            print(f"[迭代 {iteration}/{self.max_iterations}]")

            # 调用 LLM
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=0.7,
                    max_tokens=1000
                )

                llm_response = response.choices[0].message.content
                print(f"LLM 响应:\n{llm_response}\n")

            except Exception as e:
                return f"API 调用错误: {str(e)}"

            # 解析响应
            parsed = self._parse_react_response(llm_response)

            # 如果有 Final Answer,返回结果
            if parsed["final_answer"]:
                print(f"\n{'=' * 60}")
                print(f"最终答案: {parsed['final_answer']}")
                print(f"{'=' * 60}\n")
                return parsed["final_answer"]

            # 如果有 Action,执行工具
            if parsed["action"] and parsed["action_input"]:
                print(f"执行工具: {parsed['action']}({parsed['action_input']})")
                observation = self._execute_action(parsed["action"], parsed["action_input"])
                print(f"观察结果: {observation}\n")

                # 将 LLM 响应和观察结果添加到历史
                messages.append({"role": "assistant", "content": llm_response})
                messages.append({"role": "user", "content": f"Observation: {observation}"})
            else:
                # 没有 Action 也没有 Final Answer,可能是格式错误
                print("警告: 无法解析 LLM 响应,尝试继续...")
                messages.append({"role": "assistant", "content": llm_response})
                messages.append({"role": "user", "content": "请按照正确的 ReAct 格式回答"})

        return "达到最大迭代次数,未能找到答案"

    def clear_history(self):
        """清除对话历史"""
        self.conversation_history = []
        print("对话历史已清除")


def load_config():
    """加载配置文件"""
    config_path = os.path.expanduser("~/.rush/config.json")

    # 如果配置文件不存在,创建默认配置
    if not os.path.exists(config_path):
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        default_config = {
            "api_key": "your_deepseek_api_key_here",
            "base_url": "https://api.deepseek.com/v1",
            "model": "deepseek-chat"
        }
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(default_config, f, indent=4, ensure_ascii=False)
        print(f"已创建默认配置文件: {config_path}")
        print("请编辑配置文件,填入你的 DeepSeek API Key")
        sys.exit(1)

    return config_path


def main():
    """主函数 - REPL 交互界面"""
    print("=" * 60)
    print("ReAct Agent CLI - 基于 ReAct 框架的 AI Agent")
    print("=" * 60)
    print("\n输入问题开始对话,或使用以下命令:")
    print("  /exit  - 退出程序")
    print("  /clear - 清除对话历史")
    print("  /help  - 显示帮助信息")
    print("=" * 60 + "\n")

    # 加载配置
    config_path = load_config()

    # 初始化 Agent
    try:
        agent = ReActAgent(config_path)
        print("\n✓ Agent 初始化成功\n")
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
            if user_input.lower() == '/exit':
                print("再见!")
                break
            elif user_input.lower() == '/clear':
                agent.clear_history()
                continue
            elif user_input.lower() == '/help':
                print("\n可用命令:")
                print("  /exit  - 退出程序")
                print("  /clear - 清除对话历史")
                print("  /help  - 显示帮助信息")
                print("\n可用工具:")
                for tool in agent.tools.values():
                    print(f"  {tool.description}")
                print()
                continue

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
