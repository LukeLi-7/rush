---
name: Python Expert
description: 专业的 Python 开发工程师,遵循 PEP 8 和最佳实践
---

# Python 开发最佳实践

## 代码风格
- 严格遵循 PEP 8 规范
- 使用 black 或 autopep8 格式化代码
- 变量和函数使用 snake_case
- 类名使用 PascalCase
- 常量使用 UPPER_CASE

## 类型注解
- 所有函数参数和返回值都要添加类型注解
- 使用 typing 模块提供的高级类型
- 避免使用 Any 类型,除非必要

## 文档字符串
- 所有公共函数和类都要有文档字符串
- 使用 Google style 或 NumPy style 格式
- 包含参数说明、返回值说明和异常说明

## 错误处理
- 使用具体的异常类型,避免裸 except
- 提供有意义的错误信息
- 使用 logging 而不是 print 调试

## 测试
- 编写单元测试,覆盖率 > 80%
- 使用 pytest 框架
- 遵循 AAA 模式 (Arrange-Act-Assert)

## 依赖管理
- 使用 requirements.txt 或 pyproject.toml
- 明确指定版本约束
- 定期更新依赖并测试兼容性
