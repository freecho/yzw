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
    def __init__(self):
        self.post_url = 'https://account.chsi.com.cn/passport/login?entrytype=yzgr&service=https%3A%2F%2Fyz.chsi.com.cn%2Fj_spring_cas_security_check'
        self.headers = {
            'User-Agent': UserAgent().random,
            'Referer': 'https://account.chsi.com.cn/passport/login?entrytype=yzgr&service=https%3A%2F%2Fyz.chsi.com.cn%2Fj_spring_cas_security_check',
            'Origin': 'https://account.chsi.com.cn'
        }

    async def get_session(self, username, password) -> aiohttp.ClientSession:
        # 返回已登录的session
        form_data = {
            'username': username,
            'password': password,
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
        session = aiohttp.ClientSession(headers=self.headers)
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
            print("登录完毕（本系统不会强行验证是否正确，自行确认账号密码正确性，错误会导致后续数据遗漏等问题）")
        else:
            print("登录失败")
            print(await response.text())

        return session

    async def do_login(self):
        username = ''
        password = ''
        session = None

        print("请选择登录方式：（输出对于数字即可）")
        print("1. 输入账号密码登录")
        print("2. 输入cookie登录")
        choice = input("选择：")

        if choice == '1':
            print("请输入下面信息！")
            username = input("账号：")
            password = input("密码：")
            # 创建登录实例
            session = await self.get_session(username, password)

        else:
            cookie_str = input("请输入cookie字符串: ")

            cookies = {}
            for pair in cookie_str.split(';'):
                if '=' in pair:
                    key, value = pair.strip().split('=', 1)
                    cookies[key] = value

            session = aiohttp.ClientSession(cookies=cookies, headers=self.headers)

        return session
