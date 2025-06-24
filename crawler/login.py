import aiohttp
from bs4 import BeautifulSoup
from fake_useragent import UserAgent

# async def on_request_start(session, trace_config_ctx, params):
#     print(f"请求开始: {params.method} {params.url}")
#
# async def on_request_end(session, trace_config_ctx, params):
#     print(f"请求结束: {params.response.status} {params.response.url}")
#
# async def on_redirect(session, trace_config_ctx, params):
#     print(f"重定向: {params.response.status} -> {params.response.headers.get('Location')}")
#     for name, morsel in params.response.cookies.items():
#         print(f"  {name} = {morsel.value}")


class Login:
    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password
        self.session = None
        self.post_url = 'https://account.chsi.com.cn/passport/login?entrytype=yzgr&service=https%3A%2F%2Fyz.chsi.com.cn%2Fj_spring_cas_security_check'
        self.ua = UserAgent().random

    async def get_session(self) -> aiohttp.ClientSession:
        headers = {
            'User-Agent': self.ua,
            'Referer': 'https://account.chsi.com.cn/passport/login?entrytype=yzgr&service=https%3A%2F%2Fyz.chsi.com.cn%2Fj_spring_cas_security_check',
            'Origin':  'https://account.chsi.com.cn'
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

        # trace_config = aiohttp.TraceConfig()
        # trace_config.on_request_start.append(on_request_start)
        # trace_config.on_request_end.append(on_request_end)
        # trace_config.on_request_redirect.append(on_redirect)
        # session = aiohttp.ClientSession(headers=headers, trace_configs=[trace_config])
        session = aiohttp.ClientSession(headers=headers)
        response = await session.get(self.post_url)

        html = await response.text()
        soup = BeautifulSoup(html, 'html.parser')
        lt_input = soup.find('input', {'name': 'lt'})
        execution_input = soup.find('input', {'name': 'execution'})
        lt = lt_input['value'] if lt_input else None
        execution = execution_input['value'] if execution_input else None
        form_data['lt'] = lt
        form_data['execution'] = execution

        # 登录
        response = await session.post(self.post_url, data=form_data)
        if response.status == 200:
            self.session = session
            print("登录完毕（本系统不会强行验证是否正确，自行确认账号密码正确性，错误会导致后续数据遗漏等问题）")
        else:
            print("登录失败")
            print(await response.text())

        return self.session
