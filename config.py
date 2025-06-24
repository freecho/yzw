import os
import yaml


# 自动读取config.yaml的配置
class Config:
    def __init__(self, config_file="config.yaml"):
        config_path = os.path.join(os.path.dirname(__file__), config_file)
        with open(config_path, "r", encoding="utf-8") as f:
            self._config = yaml.safe_load(f)

    # 获取配置项，支持嵌套访问(智能返回字符串或字典)
    def get(self, key_path, default=None, sep="."):
        keys = key_path.split(sep)
        data = self._config
        for key in keys:
            if isinstance(data, dict):
                data = data.get(key, default)
            else:
                return default
        return data


# 实例化配置对象
config = Config()
