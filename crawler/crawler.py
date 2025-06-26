import asyncio
import random
from time import sleep
from urllib.parse import urlencode
import datetime

from config import config
from data import db


def log_failed_request(request_type, info):
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_line = f"[{timestamp}] [{request_type}] {info}，错误原因: 重试次数过多\n"
    with open('failed_requests.log', 'a', encoding='utf-8') as f:
        f.write(log_line)


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
            info = f"省份代码: {province_code}, 当前页: {curPage}, 断点: {self.breakpoint}"
            log_failed_request('fetch_school_info', info)
            return
        self.form_data['ssdm'] = province_code
        self.form_data['curPage'] = curPage
        self.form_data['start'] = str((curPage - 1) * 10)

        async with self.session.post(self.url, data=self.form_data) as response:
            if response.status == 200:
                data = await response.json()
                if not data.get('flag'):
                    if 'flag' not in data:
                        print("警告：返回数据没有flag字段，内容如下：", data)
                        log_failed_request('fetch_school_info_no_flag', str(data))
                    msg = data.get('msg')
                    if msg == '请登录':
                        await self.handle_login_prompt()
                    elif msg == '访问太频繁':
                        wait_time = retry * 2
                        print(f"访问太频繁，等待{wait_time}秒后重试……")
                        await asyncio.sleep(wait_time)
                        print("正在重试……")
                        await do_sleep()
                        await self.fetch_school_info(province_code, curPage, False, retry + 1)
                        return
                    print(msg)
                    print("警告：msg字段不是dict或缺少list，内容如下：", data)
                    log_failed_request('fetch_school_info_msg_type', str(data))
                    return
                else:
                    msg = data.get('msg')
                    if msg == '请登录':
                        await self.handle_login_prompt()
                        return
                    elif msg == '访问太频繁':
                        wait_time = retry * 2
                        print(f"访问太频繁，等待{wait_time}秒后重试……")
                        await asyncio.sleep(wait_time)
                        print("正在重试……")
                        await do_sleep()
                        await self.fetch_school_info(province_code, curPage, False, retry + 1)
                        return
                    if isinstance(msg, dict) and 'list' in msg:
                        list_ = msg['list']
                        for item in list_:
                            school_name = item.get('dwmc')
                            # 断点跳过逻辑
                            if not self.reached_school:
                                if school_name == self.breakpoint.get('school_name'):
                                    self.reached_school = True
                                else:
                                    continue
                            await self.fetch_school_major(item)
                    else:
                        print("警告：msg字段不是dict或缺少list，内容如下：", data)
                        log_failed_request('fetch_school_info_msg_type', str(data))
                        return

                if data.get('msg') and isinstance(data.get('msg'), dict) and data.get('msg').get('nextPageAvailable') and go_on:
                    await do_sleep()
                    await self.fetch_school_info(province_code, curPage + 1)
            else:
                print(f"请求失败，状态码: {response.status}")
                await self.fetch_school_info(province_code, curPage, False, retry + 1)
                return None

    async def fetch_school_major(self, obj, curPage=1, go_on=True, retry=0):
        if retry > 5:
            print("重试次数过多，放弃当前学校专业抓取")
            info = f"学校: {obj.get('dwmc')}, 当前页: {curPage}, 断点: {self.breakpoint}"
            log_failed_request('fetch_school_major', info)
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
                if not data.get('flag'):
                    if 'flag' not in data:
                        print("警告：返回数据没有flag字段，内容如下：", data)
                        log_failed_request('fetch_school_major_no_flag', str(data))
                    msg = data.get('msg')
                    if msg == '请登录':
                        await self.handle_login_prompt()
                    elif msg == '访问太频繁':
                        wait_time = retry * 2
                        print(f"访问太频繁，等待{wait_time}秒后重试……")
                        await asyncio.sleep(wait_time)
                        print("正在重试……")
                        await do_sleep()
                        await self.fetch_school_major(obj, curPage, False, retry + 1)
                        return
                    print(msg)
                    print("警告：msg字段不是dict或缺少list，内容如下：", data)
                    log_failed_request('fetch_school_major_msg_type', str(data))
                    return
                else:
                    msg = data.get('msg')
                    if msg == '请登录':
                        await self.handle_login_prompt()
                        return
                    elif msg == '访问太频繁':
                        wait_time = retry * 2
                        print(f"访问太频繁，等待{wait_time}秒后重试……")
                        await asyncio.sleep(wait_time)
                        print("正在重试……")
                        await do_sleep()
                        await self.fetch_school_major(obj, curPage, False, retry + 1)
                        return
                    if isinstance(msg, dict) and 'list' in msg:
                        list_ = msg['list']
                        for item in list_:
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
                    else:
                        print("警告：msg字段不是dict或缺少list，内容如下：", data)
                        log_failed_request('fetch_school_major_msg_type', str(data))
                        return

                if data.get('msg') and isinstance(data.get('msg'), dict) and data.get('msg').get('nextPageAvailable') and go_on:
                    await do_sleep()
                    await self.fetch_school_major(obj, curPage + 1)
            else:
                print(f"请求失败，状态码: {response.status}")
                await self.fetch_school_major(obj, curPage, False, retry + 1)

    async def _fetch_major_detail(self, item, detail_form_data, go_on=True, retry=0):
        if retry > 5:
            print("重试次数过多，放弃当前专业详情抓取")
            info = f"专业: {item.get('zymc')}, 学校: {item.get('dwmc')}"
            log_failed_request('fetch_major_detail', info)
            return
        async with self.session.post('https://yz.chsi.com.cn/zsml/rs/yjfxs.do',
                                     data=detail_form_data) as detail_response:
            if detail_response.status == 200:
                detail_data = await detail_response.json()

                if not detail_data.get('flag'):
                    if 'flag' not in detail_data:
                        print("警告：返回数据没有flag字段，内容如下：", detail_data)
                        log_failed_request('fetch_major_detail_no_flag', str(detail_data))
                    msg = detail_data.get('msg')
                    if msg == '请登录':
                        await self.handle_login_prompt()
                    elif msg == '访问太频繁':
                        wait_time = retry * 2
                        print(f"访问太频繁，等待{wait_time}秒后重试……")
                        await asyncio.sleep(wait_time)
                        print("正在重试……")
                        await do_sleep()
                        await self._fetch_major_detail(item, detail_form_data, False, retry + 1)
                        return
                    if isinstance(msg, dict) and 'list' in msg:
                        detail_list = msg['list']
                        for detail_item in detail_list:
                            detail_item['xwlxmc'] = item.get('xwlxmc')
                            db.insert(detail_item)
                    else:
                        print("警告：msg字段不是dict或缺少list，内容如下：", detail_data)
                        log_failed_request('fetch_major_detail_msg_type', str(detail_data))
                        return
                else:
                    msg = detail_data.get('msg')
                    if msg == '请登录':
                        await self.handle_login_prompt()
                    elif msg == '访问太频繁':
                        wait_time = retry * 2
                        print(f"访问太频繁，等待{wait_time}秒后重试……")
                        await asyncio.sleep(wait_time)
                        print("正在重试……")
                        await do_sleep()
                        await self._fetch_major_detail(item, detail_form_data, False, retry + 1)
                        return
                    if isinstance(msg, dict) and 'list' in msg:
                        detail_list = msg['list']
                        for detail_item in detail_list:
                            detail_item['xwlxmc'] = item.get('xwlxmc')
                            db.insert(detail_item)
                    else:
                        print("警告：msg字段不是dict或缺少list，内容如下：", detail_data)
                        log_failed_request('fetch_major_detail_msg_type', str(detail_data))
                        return
            else:
                print(f"详情请求失败，状态码: {detail_response.status}")
                await self._fetch_major_detail(item, detail_form_data, False, retry + 1)
