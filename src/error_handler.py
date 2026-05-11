#!/usr/bin/env python3
"""
错误处理和恢复机制
提供重试、熔断、缓存等功能
"""

import time
import json
import hashlib
import logging
from typing import Optional, Callable, Any
from datetime import datetime, timedelta

# 配置日志
logger = logging.getLogger(__name__)


class RetryConfig:
    """重试配置"""
    
    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True
    ):
        """
        Args:
            max_retries: 最大重试次数
            base_delay: 基础延迟时间（秒）
            max_delay: 最大延迟时间（秒）
            exponential_base: 指数退避基数
            jitter: 是否添加随机抖动
        """
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
    
    def get_delay(self, attempt: int) -> float:
        """计算重试延迟时间
        
        Args:
            attempt: 当前尝试次数（从0开始）
            
        Returns:
            float: 延迟时间（秒）
        """
        # 指数退避
        delay = self.base_delay * (self.exponential_base ** attempt)
        
        # 限制最大延迟
        delay = min(delay, self.max_delay)
        
        # 添加随机抖动（避免多个请求同时重试）
        if self.jitter:
            import random
            delay *= (0.5 + random.random() * 0.5)
        
        return delay


class CircuitBreaker:
    """熔断器
    
    状态机：
    - CLOSED: 正常状态，允许请求通过
    - OPEN: 熔断状态，拒绝所有请求
    - HALF_OPEN: 半开状态，允许一个测试请求
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        expected_exception: type = Exception
    ):
        """
        Args:
            failure_threshold: 失败阈值，连续失败多少次后熔断
            recovery_timeout: 恢复超时时间（秒）
            expected_exception: 需要计数的异常类型
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        
        self.failure_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
    
    def can_execute(self) -> bool:
        """检查是否可以执行请求
        
        Returns:
            bool: 是否允许执行
        """
        if self.state == "CLOSED":
            return True
        
        if self.state == "OPEN":
            # 检查是否过了恢复时间
            if self.last_failure_time and \
               (datetime.now() - self.last_failure_time).total_seconds() > self.recovery_timeout:
                self.state = "HALF_OPEN"
                logger.info("熔断器进入半开状态")
                return True
            return False
        
        # HALF_OPEN 状态允许一个请求
        return True
    
    def record_success(self):
        """记录成功"""
        if self.state == "HALF_OPEN":
            logger.info("熔断器恢复正常")
            self.state = "CLOSED"
        
        self.failure_count = 0
        self.last_failure_time = None
    
    def record_failure(self):
        """记录失败"""
        self.failure_count += 1
        self.last_failure_time = datetime.now()
        
        if self.failure_count >= self.failure_threshold:
            if self.state != "OPEN":
                self.state = "OPEN"
                logger.warning(f"熔断器打开：连续失败 {self.failure_count} 次")


class ResponseCache:
    """响应缓存
    
    用于离线模式或减少API调用
    """
    
    def __init__(self, cache_dir: str = ".rush/cache", ttl: int = 3600):
        """
        Args:
            cache_dir: 缓存目录
            ttl: 缓存有效期（秒），默认1小时
        """
        import os
        self.cache_dir = cache_dir
        self.ttl = ttl
        
        # 确保缓存目录存在
        os.makedirs(cache_dir, exist_ok=True)
    
    def _get_cache_key(self, messages: list, tools: list = None) -> str:
        """生成缓存键
        
        Args:
            messages: 消息列表
            tools: 工具列表
            
        Returns:
            str: 缓存键（MD5哈希）
        """
        # 序列化请求内容
        cache_data = {
            "messages": messages,
            "tools": tools or []
        }
        
        content = json.dumps(cache_data, sort_keys=True, ensure_ascii=False)
        return hashlib.md5(content.encode('utf-8')).hexdigest()
    
    def _get_cache_path(self, key: str) -> str:
        """获取缓存文件路径"""
        import os
        return os.path.join(self.cache_dir, f"{key}.json")
    
    def get(self, messages: list, tools: list = None) -> Optional[Any]:
        """获取缓存的响应
        
        Args:
            messages: 消息列表
            tools: 工具列表
            
        Returns:
            Optional[Any]: 缓存的响应，如果不存在或过期则返回None
        """
        try:
            key = self._get_cache_key(messages, tools)
            cache_path = self._get_cache_path(key)
            
            import os
            if not os.path.exists(cache_path):
                return None
            
            # 读取缓存
            with open(cache_path, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            # 检查是否过期
            cached_time = datetime.fromisoformat(cache_data['timestamp'])
            if (datetime.now() - cached_time).total_seconds() > self.ttl:
                logger.debug("缓存已过期")
                return None
            
            logger.debug("命中缓存")
            return cache_data['response']
            
        except Exception as e:
            logger.warning(f"读取缓存失败: {e}")
            return None
    
    def set(self, messages: list, response: Any, tools: list = None):
        """缓存响应
        
        Args:
            messages: 消息列表
            response: 响应内容
            tools: 工具列表
        """
        try:
            key = self._get_cache_key(messages, tools)
            cache_path = self._get_cache_path(key)
            
            cache_data = {
                'timestamp': datetime.now().isoformat(),
                'messages': messages,
                'response': response
            }
            
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
            
            logger.debug(f"响应已缓存: {key[:8]}...")
            
        except Exception as e:
            logger.warning(f"写入缓存失败: {e}")
    
    def clear(self):
        """清空缓存"""
        try:
            import os
            import glob
            
            cache_files = glob.glob(os.path.join(self.cache_dir, "*.json"))
            for file in cache_files:
                os.remove(file)
            
            logger.info(f"已清空缓存，删除 {len(cache_files)} 个文件")
            
        except Exception as e:
            logger.warning(f"清空缓存失败: {e}")


def retry_with_backoff(
    func: Callable,
    config: RetryConfig = None,
    fallback: Callable = None,
    circuit_breaker: CircuitBreaker = None
) -> Callable:
    """带指数退避的重试装饰器
    
    Args:
        func: 要执行的函数
        config: 重试配置
        fallback: 降级函数（所有重试失败后调用）
        circuit_breaker: 熔断器
        
    Returns:
        Callable: 包装后的函数
    """
    if config is None:
        config = RetryConfig()
    
    def wrapper(*args, **kwargs):
        # 检查熔断器
        if circuit_breaker and not circuit_breaker.can_execute():
            logger.warning("熔断器开启，拒绝请求")
            if fallback:
                return fallback(*args, **kwargs)
            raise Exception("服务不可用（熔断器保护）")
        
        last_exception = None
        
        for attempt in range(config.max_retries + 1):
            try:
                result = func(*args, **kwargs)
                
                # 记录成功
                if circuit_breaker:
                    circuit_breaker.record_success()
                
                if attempt > 0:
                    logger.info(f"重试成功（第{attempt + 1}次尝试）")
                
                return result
                
            except Exception as e:
                last_exception = e
                
                # 记录失败
                if circuit_breaker:
                    circuit_breaker.record_failure()
                
                # 如果是最后一次尝试，不再重试
                if attempt >= config.max_retries:
                    logger.error(f"所有重试失败: {e}")
                    break
                
                # 计算延迟时间
                delay = config.get_delay(attempt)
                logger.warning(f"请求失败（尝试 {attempt + 1}/{config.max_retries + 1}）: {e}")
                logger.info(f"{delay:.2f}秒后重试...")
                
                # 等待后重试
                time.sleep(delay)
        
        # 所有重试都失败，尝试降级
        if fallback:
            logger.info("使用降级方案")
            try:
                return fallback(*args, **kwargs)
            except Exception as fallback_error:
                logger.error(f"降级方案也失败: {fallback_error}")
        
        # 抛出最后的异常
        raise last_exception
    
    return wrapper


class ErrorHandler:
    """错误处理器
    
    统一管理错误日志和报告
    """
    
    def __init__(self, log_file: str = ".rush/error.log"):
        """
        Args:
            log_file: 日志文件路径
        """
        import os
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        
        # 配置文件日志
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.WARNING)
        
        # 配置控制台日志
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.ERROR)
        
        # 设置格式
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        # 添加处理器
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        logger.setLevel(logging.WARNING)
    
    def log_error(self, error: Exception, context: dict = None):
        """记录错误
        
        Args:
            error: 异常对象
            context: 上下文信息
        """
        error_info = {
            'type': type(error).__name__,
            'message': str(error),
            'timestamp': datetime.now().isoformat(),
            'context': context or {}
        }
        
        logger.error(f"错误: {json.dumps(error_info, ensure_ascii=False)}")
    
    def log_warning(self, message: str, context: dict = None):
        """记录警告
        
        Args:
            message: 警告信息
            context: 上下文信息
        """
        warning_info = {
            'message': message,
            'timestamp': datetime.now().isoformat(),
            'context': context or {}
        }
        
        logger.warning(f"警告: {json.dumps(warning_info, ensure_ascii=False)}")
