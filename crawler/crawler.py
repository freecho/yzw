import asyncio
import random
from time import sleep
from urllib.parse import urlencode

from config import config
from data import db


async def do_sleep():
    interval = config.get('interval.seconds')  # 抓取时间间隔，单位为秒
    await asyncio.sleep(interval * random.uniform(0.8, 1.2))  # 随机延时，防止被封禁


class School:
    def __init__(self, session, breakpoint=None):
        self.session = session
        self.url = 'https://yz.chsi.com.cn/zsml/rs/dws.do'
        self.form_data = {
            'dwmc': '',
            'dwdm': '',
            'xxfs': '',
            'tydxs': '',
            'jsggjh': '',
            'dwlxs[0]': 'all',
            'start': '0',
            'pageSize': '10',
            'totalPage': '',
            'totalCount': ''
        }
        self.breakpoint = breakpoint or {}
        self.reached_school = False if self.breakpoint.get('school_name') else True
        self.reached_major = False if self.breakpoint.get('major_code') else True
        self.login_prompt_count = 0  # 统计"请登录"出现次数

    async def handle_login_prompt(self):
        self.login_prompt_count += 1
        if self.login_prompt_count >= 10:
            print("检测到'请登录'超过10次，程序自动终止！")
            raise SystemExit
        await do_sleep()
        await self.session.get('https://yz.chsi.com.cn/zsml/a/dw.do')
        await do_sleep()

    # 爬取指定省份地区的学校信息
    async def fetch_school_info(self, province_code, curPage=1, go_on=True, retry=0):
        if retry > 5:
            print("重试次数过多，放弃当前省份学校抓取")
            return
        self.form_data['ssdm'] = province_code
        self.form_data['curPage'] = curPage
        self.form_data['start'] = str((curPage - 1) * 10)

        async with self.session.post(self.url, data=self.form_data) as response:
            if response.status == 200:
                data = await response.json()
                if not data['flag']:
                    print(data['msg'])
                    if data['msg'] == '请登录':
                        await self.handle_login_prompt()
                    print("正在重试……")
                    await do_sleep()
                    await self.fetch_school_info(province_code, curPage, False, retry + 1)
                    return
                else:
                    # 学校列表
                    list = data['msg']['list']
                    for item in list:
                        school_name = item.get('dwmc')
                        # 断点跳过逻辑
                        if not self.reached_school:
                            if school_name == self.breakpoint.get('school_name'):
                                self.reached_school = True
                            else:
                                continue
                        await self.fetch_school_major(item)
                    print(data)

                if data['msg']['nextPageAvailable'] and go_on:
                    await do_sleep()
                    await self.fetch_school_info(province_code, curPage + 1)
            else:
                print(f"请求失败，状态码: {response.status}")
                await self.fetch_school_info(province_code, curPage, False, retry + 1)
                return None

    async def fetch_school_major(self, obj, curPage=1, go_on=True, retry=0):
        if retry > 5:
            print("重试次数过多，放弃当前学校专业抓取")
            return
        form_data = {
            'dwdm': obj.get('dwdm'),
            'dwmc': obj.get('dwmc'),
            'zydm': '',
            'zymc': '',
            'xwlx': '',
            'mldm': '',
            'yjxkdm': '',
            'xxfs': '',
            'tydxs': '',
            'jsggjh': '',
            'start': str((curPage - 1) * 10),
            'curPage': str(curPage),
            'pageSize': '10',
            'totalPage': '0',
            'totalCount': '0'
        }
        async with self.session.post('https://yz.chsi.com.cn/zsml/rs/dwzys.do', data=form_data) as response:
            if response.status == 200:
                data = await response.json()
                if not data['flag']:
                    print(data['msg'])
                    if data['msg'] == '请登录':
                        await self.handle_login_prompt()
                    print("正在重试……")
                    await do_sleep()
                    await self.fetch_school_major(obj, curPage, False, retry + 1)
                    return
                else:
                    # 专业列表
                    list = data['msg']['list']
                    for item in list:
                        major_code = item.get('zydm')
                        # 断点跳过逻辑
                        if not self.reached_major:
                            if major_code == self.breakpoint.get('major_code'):
                                self.reached_major = True
                            else:
                                continue
                        await do_sleep()
                        detail_form_data = {
                            'zydm': item.get('zydm'),
                            'zymc': item.get('zymc'),
                            'dwdm': item.get('dwdm'),
                            'xxfs': '',
                            'dwlxs': '',
                            'tydxs': '',
                            'jsggjh': '',
                            'start': '0',
                            'pageSize': '3',
                            'totalCount': '0'
                        }
                        await self._fetch_major_detail(item, detail_form_data)

                if data['msg']['nextPageAvailable'] and go_on:
                    await do_sleep()
                    await self.fetch_school_major(obj, curPage + 1)
            else:
                print(f"请求失败，状态码: {response.status}")
                await self.fetch_school_major(obj, curPage, False, retry + 1)

    async def _fetch_major_detail(self, item, detail_form_data, go_on=True, retry=0):
        if retry > 5:
            print("重试次数过多，放弃当前专业详情抓取")
            return
        async with self.session.post('https://yz.chsi.com.cn/zsml/rs/yjfxs.do',
                                     data=detail_form_data) as detail_response:
            if detail_response.status == 200:
                detail_data = await detail_response.json()

                if not detail_data['flag']:
                    print(detail_data['msg'])
                    if detail_data['msg'] == '请登录':
                        await self.handle_login_prompt()

                    print("正在重试……")
                    await do_sleep()
                    await self._fetch_major_detail(item, detail_form_data, False, retry + 1)
                    return
                else:
                    detail_list = detail_data['msg']['list']
                    for detail_item in detail_list:
                        detail_item['xwlxmc'] = item.get('xwlxmc')
                        db.insert(detail_item)
            else:
                print(f"详情请求失败，状态码: {detail_response.status}")
                await self._fetch_major_detail(item, detail_form_data, False, retry + 1)
