import aiohttp
import asyncio
import random
from typing import Optional, List, Dict
import logging
import datetime

class ProxyManager:
    def __init__(self, proxy_pool_url: str = "http://127.0.0.1:5010"):
        self.proxy_pool_url = proxy_pool_url
        self.proxies: List[str] = []
        self.current_proxy: Optional[str] = None
        self.failed_proxies: set = set()
        self.max_retries = 3
        
    async def get_proxy_from_pool(self) -> Optional[str]:
        """从代理池获取代理"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.proxy_pool_url}/get/") as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get("proxy"):
                            return data["proxy"]
        except Exception as e:
            logging.warning(f"从代理池获取代理失败: {e}")
        return None
    
    async def delete_proxy_from_pool(self, proxy: str):
        """从代理池删除失效代理"""
        try:
            async with aiohttp.ClientSession() as session:
                await session.get(f"{self.proxy_pool_url}/delete/?proxy={proxy}")
        except Exception as e:
            logging.warning(f"删除代理失败: {e}")
    
    async def switch_proxy(self) -> Optional[str]:
        """切换代理"""
        if self.current_proxy:
            self.failed_proxies.add(self.current_proxy)
            # 从代理池删除失效代理
            await self.delete_proxy_from_pool(self.current_proxy)
        
        # 尝试从代理池获取新代理
        new_proxy = await self.get_proxy_from_pool()
        if new_proxy and new_proxy not in self.failed_proxies:
            self.current_proxy = new_proxy
            logging.info(f"切换到新代理: {new_proxy}")
            return new_proxy
        
        # 如果代理池没有可用代理，尝试使用备用代理
        backup_proxies = [
            "127.0.0.1:7890",  # 常见的代理端口
            "127.0.0.1:1080",
            "127.0.0.1:8080",
        ]
        
        for proxy in backup_proxies:
            if proxy not in self.failed_proxies:
                self.current_proxy = proxy
                logging.info(f"使用备用代理: {proxy}")
                return proxy
        
        # 所有代理都失败了，返回None表示使用自身IP
        logging.warning("所有代理都失败，将使用自身IP")
        self.current_proxy = None
        return None
    
    def record_direct_ip_failure(self, error_info: str):
        """记录自身IP失败"""
        logging.error(f"自身IP也失败，程序将退出: {error_info}")
        # 可以在这里记录到文件或数据库
        with open('ip_failure.log', 'a', encoding='utf-8') as f:
            timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            f.write(f"[{timestamp}] 自身IP失败: {error_info}\n")
    
    def should_use_proxy(self) -> bool:
        """判断是否应该使用代理"""
        return self.current_proxy is not None and self.current_proxy not in self.failed_proxies
    
    def get_current_proxy(self) -> Optional[str]:
        """获取当前代理"""
        return self.current_proxy
    
    def get_proxy_dict(self) -> Optional[Dict[str, str]]:
        """获取代理字典格式，用于aiohttp"""
        if not self.should_use_proxy():
            return None
        
        return {
            "http": f"http://{self.current_proxy}",
            "https": f"http://{self.current_proxy}"
        }
    
    async def test_proxy(self, proxy: str, test_url: str = "https://www.baidu.com") -> bool:
        """测试代理是否可用"""
        try:
            proxy_dict = {
                "http": f"http://{proxy}",
                "https": f"http://{proxy}"
            }
            
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(test_url, proxy=proxy_dict["http"]) as response:
                    return response.status == 200
        except Exception:
            return False
    
    async def initialize_proxy(self):
        """初始化代理"""
        logging.info("正在初始化代理...")
        proxy = await self.switch_proxy()
        if proxy:
            # 测试代理可用性
            if await self.test_proxy(proxy):
                logging.info(f"代理初始化成功: {proxy}")
                return True
            else:
                logging.warning(f"代理测试失败: {proxy}")
                self.failed_proxies.add(proxy)
                return await self.initialize_proxy()
        return False 