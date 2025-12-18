import os
from typing import Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

@dataclass
class Settings:
    """系统配置类"""
    AWS_ACCESS_KEY_ID: str
    AWS_SECRET_ACCESS_KEY: str 
    AWS_REGION: str
    GITLAB_TOKEN: str = None
    GITLAB_BASE_URL: str = None
    @classmethod
    def from_env(cls) -> Optional['Settings']:
        """从环境变量加载配置"""
        required_vars = {
            'AWS_ACCESS_KEY_ID': os.getenv('AWS_ACCESS_KEY_ID'),
            'AWS_SECRET_ACCESS_KEY': os.getenv('AWS_SECRET_ACCESS_KEY'),
            'AWS_REGION': os.getenv('AWS_ACCESS_REGION'),
            'GITLAB_TOKEN': os.getenv('GITLAB_TOKEN'),
            # 'GITLAB_BASE_URL': os.getenv('GITLAB_BASE_URL')
        }
        
        # 检查必需的环境变量
        missing_vars = [k for k, v in required_vars.items() if not v]
        if missing_vars:
            logger.error(f"缺少必需的环境变量: {', '.join(missing_vars)}")
            return None
         
        return cls(**required_vars)

# 创建全局配置实例
settings = Settings.from_env()
# print(settings)
if not settings:
    raise RuntimeError("无法加载配置，请检查环境变量是否正确设置")