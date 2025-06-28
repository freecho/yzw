import asyncio
import random
from time import sleep
from urllib.parse import urlencode
import datetime
import re
import ast

from config import config
from data import db


def log_failed_request(request_type, info, item=None):
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    # 如果有item，补全xwlxmc等字段
    if item is not None:
        # 只补全常用字段，避免None
        xwlxmc = item.get('xwlxmc', '')
        info += f", xwlxmc: {xwlxmc}"
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
            log_failed_request('fetch_school_major', info, obj)
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
                    log_failed_request('fetch_school_major_msg_type', str(data), obj)
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
                        log_failed_request('fetch_school_major_msg_type', str(data), obj)
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
            log_failed_request('fetch_major_detail', info, item)
            return
        async with self.session.post('https://yz.chsi.com.cn/zsml/rs/yjfxs.do',
                                     data=detail_form_data) as detail_response:
            if detail_response.status == 200:
                detail_data = await detail_response.json()

                if not detail_data.get('flag'):
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
                        log_failed_request('fetch_major_detail_msg_type', str(detail_data), item)
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
                        log_failed_request('fetch_major_detail_msg_type', str(detail_data), item)
                        return
            else:
                print(f"详情请求失败，状态码: {detail_response.status}")
                await self._fetch_major_detail(item, detail_form_data, False, retry + 1)


async def retry_failed_requests(school_instance, log_path='failed_requests.log'):
    print('开始日志重试...')
    try:
        with open(log_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except FileNotFoundError:
        print('日志文件未找到')
        return
    
    print(f'日志文件共有 {len(lines)} 行内容')
    
    if not lines:
        print('日志文件为空，无需重试')
        return
        
    retried = set()
    lines_to_keep = []
    retry_count = 0
    
    for line in lines:
        if "错误原因: 重试次数过多" not in line:
            lines_to_keep.append(line)
            continue
        handled = False
        await asyncio.sleep(1)
        # fetch_school_major
        if '[fetch_school_major_no_flag]' in line or '[fetch_school_major_msg_type]' in line:
            m = re.search(r'\] \[fetch_school_major.*?\] (\{.*\})，错误原因', line)
            if m:
                try:
                    info = ast.literal_eval(m.group(1))
                except Exception:
                    lines_to_keep.append(line)
                    continue
                dwdm = info.get('zsmlcxModel', {}).get('dwdm')
                dwmc = info.get('zsmlcxModel', {}).get('dwmc')
                curPage = int(info.get('params', {}).get('curPage', ['1'])[0])
                key = (dwdm, dwmc, curPage)
                if key in retried:
                    continue
                print(f'重试日志失败请求：学校={dwmc}, dwdm={dwdm}, 当前页={curPage}')
                obj = {'dwdm': dwdm, 'dwmc': dwmc}
                retry_school = type(school_instance)(school_instance.session, breakpoint={})
                retry_school.login_prompt_count = 0  # 重置登录提示计数
                try:
                    await retry_school.fetch_school_major(obj, curPage)
                    handled = True
                    retry_count += 1
                except Exception as e:
                    print(f'重试失败：{e}')
                    lines_to_keep.append(line)
                    continue
                retried.add(key)
        # fetch_major_detail
        elif '[fetch_major_detail_no_flag]' in line or '[fetch_major_detail_msg_type]' in line:
            m = re.search(r'\] \[fetch_major_detail.*?\] (\{.*\})(?:, xwlxmc: (.*?))?，错误原因', line)
            if m:
                try:
                    info = ast.literal_eval(m.group(1))
                except Exception:
                    lines_to_keep.append(line)
                    continue
                xwlxmc = m.group(2) if m.group(2) else ''
                params = info.get('params', {})
                item = {
                    'zydm': params.get('zydm', [''])[0],
                    'zymc': params.get('zymc', [''])[0],
                    'dwdm': params.get('dwdm', [''])[0],
                    'xwlxmc': xwlxmc,
                }
                detail_form_data = {
                    'zydm': params.get('zydm', [''])[0],
                    'zymc': params.get('zymc', [''])[0],
                    'dwdm': params.get('dwdm', [''])[0],
                    'xxfs': params.get('xxfs', [''])[0],
                    'dwlxs': params.get('dwlxs', [''])[0] if 'dwlxs' in params else '',
                    'tydxs': params.get('tydxs', [''])[0],
                    'jsggjh': params.get('jsggjh', [''])[0],
                    'start': params.get('start', ['0'])[0],
                    'pageSize': params.get('pageSize', ['3'])[0],
                    'totalCount': params.get('totalCount', ['0'])[0]
                }
                key = (item['dwdm'], item['zydm'], item['zymc'])
                if key in retried:
                    continue
                print(f'重试日志失败请求：专业={item["zymc"]}, 学校代码={item["dwdm"]}, 专业代码={item["zydm"]}, 学位类型={item["xwlxmc"]}')
                retry_school = type(school_instance)(school_instance.session, breakpoint={})
                retry_school.login_prompt_count = 0  # 重置登录提示计数
                try:
                    await retry_school._fetch_major_detail(item, detail_form_data)
                    handled = True
                    retry_count += 1
                except Exception as e:
                    print(f'重试失败：{e}')
                    lines_to_keep.append(line)
                    continue
                retried.add(key)
        if not handled:
            lines_to_keep.append(line)
    
    print(f'日志重试完成！共重试了 {retry_count} 个请求')
    
    # 写回未处理的日志
    with open(log_path, 'w', encoding='utf-8') as f:
        f.writelines(lines_to_keep)
