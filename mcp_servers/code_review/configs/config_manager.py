from pathlib import Path
import yaml
from typing import Dict, Any

class ConfigManager:
    _instance = None
    _config = None
    _current_group = 'web'  # 默認值

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if self._config is None:
            self._load_config()

    def _load_config(self) -> None:
        """載入配置文件"""
        config_path = Path(__file__).parent / "config.yml"
        with open(config_path, 'r', encoding='utf-8') as f:
            self._config = yaml.safe_load(f)

    @property
    def variable_config(self) -> Dict[str, Any]:
        """獲取配置"""
        return self._config

    def get_global_variable_config(self) -> Dict[str, Any]:
        """獲取全局配置"""
        return self._config.get('global', {})

    def get_group_variable_config(self, group_name: str = None) -> Dict[str, Any]:
        """獲取特定群組的配置"""
        if group_name is None:
            group_name = self._current_group
        return self._config.get('group', {}).get(group_name, {})

    def get_current_group_variable_config(self) -> Dict[str, Any]:
        """獲取當前群組的配置"""
        return self.get_group_variable_config(self._current_group)

    def set_current_group(self, group_name: str) -> None:
        """設置當前群組"""
        self._current_group = group_name

    def get_current_group(self) -> str:
        """獲取當前群組名稱"""
        return self._current_group

    def get_template_dir(self, group_name: str = None) -> Path:
        """獲取模板目錄路徑"""
        if group_name is None:
            group_name = self._current_group
            
        # 優先從 group 配置中獲取 template_path
        group_config = self.get_group_variable_config(group_name)
        if group_config and 'template_path' in group_config:
            return Path(__file__).parent.parent / group_config['template_path']

        # 如果沒有找到，使用全局配置
        global_config = self.get_global_variable_config()
        if global_config and 'template_path' in global_config:
            return Path(__file__).parent.parent / global_config['template_path']

        # 如果都沒有找到，返回默認路徑
        return Path(__file__).parent.parent / 'templates'

# 創建一個全局實例
config_manager = ConfigManager()

def get_variable_config() -> Dict[str, Any]:
    """獲取完整配置的便捷函數"""
    return config_manager.variable_config

def get_global_variable_config() -> Dict[str, Any]:
    """獲取全局配置的便捷函數"""
    return config_manager.get_global_variable_config()

def get_group_variable_config(group_name: str = None) -> Dict[str, Any]:
    """獲取特定群組配置的便捷函數"""
    return config_manager.get_group_variable_config(group_name)

def get_current_group_variable_config() -> Dict[str, Any]:
    """獲取當前群組配置的便捷函數"""
    return config_manager.get_current_group_variable_config()

def set_current_group(group_name: str) -> None:
    """設置當前群組的便捷函數"""
    config_manager.set_current_group(group_name)

def get_current_group() -> str:
    """獲取當前群組名稱的便捷函數"""
    return config_manager.get_current_group()

def get_template_dir(group_name: str = None) -> Path:
    """獲取模板目錄路徑的便捷函數"""
    return config_manager.get_template_dir(group_name) 