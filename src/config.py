"""配置管理模块"""

import json
import os
import sys
from typing import Dict, Any


def load_config(config_path: str = None) -> str:
    """加载配置文件
    
    支持全局和本地配置:
    - 全局配置: ~/.rush/config.json
    - 本地配置: .rush/config.json (覆盖同名的全局配置)
    
    Args:
        config_path: 配置文件路径,默认为自动检测
        
    Returns:
        str: 主配置文件路径
        
    Raises:
        FileNotFoundError: 配置文件不存在
        SystemExit: 配置无效时退出程序
    """
    if config_path is None:
        # 优先使用本地配置,否则使用全局配置
        local_config = os.path.join(os.getcwd(), '.rush', 'config.json')
        global_config = os.path.expanduser("~/.rush/config.json")
        
        if os.path.exists(local_config):
            config_path = local_config
        else:
            config_path = global_config
    
    # 如果配置文件不存在,创建默认配置
    if not os.path.exists(config_path):
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        default_config = {
            "api_key": "your_deepseek_api_key_here",
            "base_url": "https://api.deepseek.com/v1",
            "model": "deepseek-chat",
            "_note": "DeepSeek 兼容 OpenAI API,可以直接使用"
        }
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(default_config, f, indent=4, ensure_ascii=False)
        print(f"已创建默认配置文件: {config_path}")
        print("请编辑配置文件,填入你的 DeepSeek API Key")
        sys.exit(1)
    
    return config_path


def read_config(config_path: str) -> Dict[str, Any]:
    """读取配置文件内容
    
    Args:
        config_path: 配置文件路径
        
    Returns:
        Dict[str, Any]: 配置字典
        
    Raises:
        ValueError: API Key 无效
        json.JSONDecodeError: JSON 格式错误
    """
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    # 验证 API Key
    api_key = config.get("api_key", "")
    if not api_key or api_key == "your_deepseek_api_key_here":
        raise ValueError("API Key 未配置或无效。请编辑配置文件 ~/.rush/config.json")
    
    return config
