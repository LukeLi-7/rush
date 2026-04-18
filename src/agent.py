"""ReAct Agent 核心模块"""

import re
from typing import Dict, Optional, List

from openai import OpenAI

from src.config import read_config
from src.tools.base import Tool
from src.tools.calculator import CalculatorTool
from src.tools.search import SearchTool
from src.tools.weather import WeatherTool


class ReActAgent:
    """ReAct 框架 AI Agent
    
    实现 Reasoning + Acting 循环机制,支持工具调用
    """
    
    def __init__(self, config_path: str = None):
        """初始化 ReAct Agent
        
        Args:
            config_path: 配置文件路径
        """
        # 加载配置
        config = read_config(config_path)
        
        # 初始化 OpenAI 客户端
        self.client = OpenAI(
            api_key=config["api_key"],
            base_url=config.get("base_url", "https://api.deepseek.com/v1")
        )
        self.model = config.get("model", "deepseek-chat")
        
        # 注册工具
        self.tools = self._register_tools()
        
        # 最大迭代次数
        self.max_iterations = 5
        
        # 构建系统提示
        self.system_prompt = self._build_system_prompt()
        
        # 对话历史
        self.conversation_history = []
    
    def _register_tools(self) -> Dict[str, Tool]:
        """注册可用工具
        
        Returns:
            Dict[str, Tool]: 工具字典
        """
        return {
            "calculator": CalculatorTool(),
            "search": SearchTool(),
            "weather": WeatherTool()
        }
    
    def _build_system_prompt(self) -> str:
        """构建系统提示
        
        Returns:
            str: 系统提示文本
        """
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
    
    def _parse_react_response(self, response: str) -> Dict[str, Optional[str]]:
        """解析 ReAct 响应
        
        Args:
            response: LLM 响应文本
            
        Returns:
            Dict: 包含 thought, action, action_input, final_answer 的字典
        """
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
        """执行工具动作
        
        Args:
            action_name: 工具名称
            action_input: 工具参数
            
        Returns:
            str: 工具执行结果
        """
        if action_name not in self.tools:
            return f"错误: 未知工具 '{action_name}'"
        
        tool = self.tools[action_name]
        try:
            return tool.execute(action_input)
        except Exception as e:
            return f"工具执行错误: {str(e)}"
    
    def run(self, query: str) -> str:
        """运行 ReAct 循环
        
        Args:
            query: 用户问题
            
        Returns:
            str: 最终答案
        """
        print(f"\n{'='*60}")
        print(f"问题: {query}")
        print(f"{'='*60}\n")
        
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
                print(f"\n{'='*60}")
                print(f"最终答案: {parsed['final_answer']}")
                print(f"{'='*60}\n")
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
    
    def get_available_tools(self) -> List[Tool]:
        """获取可用工具列表
        
        Returns:
            List[Tool]: 工具列表
        """
        return list(self.tools.values())
