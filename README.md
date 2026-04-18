# ReAct Agent CLI

基于 ReAct(Reasoning + Acting)框架的命令行 AI Agent,使用 DeepSeek API。

## 功能特性

- ✅ ReAct 框架实现(Thought/Action/Observation 循环)
- ✅ 工具调用能力(计算器、搜索、天气查询)
- ✅ REPL 交互式命令行界面
- ✅ 历史命令导航
- ✅ 自动配置管理

## 安装

1. 安装依赖:
```bash
pip install -r requirements.txt
```

2. 配置 API Key:
   - 首次运行时会自动创建配置文件 `~/.rush/config.json`
   - 编辑配置文件,填入你的 DeepSeek API Key:
```json
{
    "api_key": "your_deepseek_api_key_here",
    "base_url": "https://api.deepseek.com/v1",
    "model": "deepseek-chat"
}
```

## 使用方法

运行程序:
```bash
python react_agent.py
```

### 内置命令

- `/exit` - 退出程序
- `/clear` - 清除对话历史
- `/help` - 显示帮助信息

### 可用工具

1. **calculator** - 执行数学计算
   ```
   calculator('2 + 2')
   calculator('10 * 5')
   ```

2. **search** - 搜索信息(模拟)
   ```
   search('Python ReAct 框架')
   ```

3. **weather** - 查询天气(模拟)
   ```
   weather('北京')
   ```

## 示例对话

```
[Rush] > 计算 123 乘以 456 的结果

============================================================
问题: 计算 123 乘以 456 的结果
============================================================

[迭代 1/5]
LLM 响应:
Thought: 我需要计算 123 乘以 456 的结果,可以使用计算器工具
Action: calculator('123 * 456')

执行工具: calculator(123 * 456)
观察结果: 计算结果: 56088

[迭代 2/5]
LLM 响应:
Thought: 我已经找到了答案
Final Answer: 123 乘以 456 的结果是 56088

============================================================
最终答案: 123 乘以 456 的结果是 56088
============================================================
```

## ReAct 框架说明

ReAct(Reasoning + Acting)框架通过以下循环工作:

1. **Thought** - 思考当前情况,决定下一步行动
2. **Action** - 执行一个工具调用
3. **Observation** - 观察工具返回的结果
4. 重复上述步骤直到找到答案
5. **Final Answer** - 给出最终答案

这种设计让 AI Agent 能够:
- 进行逻辑推理
- 调用外部工具获取信息
- 根据观察结果调整策略
- 解决复杂的多步问题

## 配置文件位置

配置文件存储在: `~/.rush/config.json`

## 技术栈

- Python 3.x
- openai >= 1.0.0
- prompt_toolkit >= 3.0.0
- DeepSeek API

## 许可证

MIT License
