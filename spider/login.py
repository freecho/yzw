import aiohttp
from bs4 import BeautifulSoup
from fake_useragent import UserAgent


class Login:
    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password
        self.session = None
        self.post_url = 'https://account.chsi.com.cn/passport/login?entrytype=yzgr&service=https%3A%2F%2Fyz.chsi.com.cn%2Fj_spring_cas_security_check'
        self.ua = UserAgent().random

    async def get_session(self) -> aiohttp.ClientSession:
        headers = {
            'User-Agent': self.ua
        }
        # 返回已登录的session
        form_data = {
            'username': self.username,
            'password': self.password,
            'lt': '',
            'execution': '',
            '_eventId': 'submit'
        }
        # 获取lt和execution
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(self.post_url) as response:
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')

                lt_input = soup.find('input', {'name': 'lt'})
                execution_input = soup.find('input', {'name': 'execution'})

                lt = lt_input['value'] if lt_input else None
                execution = execution_input['value'] if execution_input else None

                form_data['lt'] = lt
                form_data['execution'] = execution

        # 登录
        session = aiohttp.ClientSession(headers=headers)
        async with session.post(self.post_url, data=form_data) as response:
            if response.status == 200:
                self.session = session
                print("Login successful")
            else:
                print("Login failed")

        return self.session
