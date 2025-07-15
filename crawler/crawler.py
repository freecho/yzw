import asyncio
import random
from time import sleep
from urllib.parse import urlencode
import datetime
import re
import ast
import aiohttp
import logging
import sys

from config import config
from data import db
from proxy_manager import ProxyManager


def log_failed_request(request_type, info, item=None, province_code=None):
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    # 如果有item，补全xwlxmc等字段
    if item is not None:
        # 只补全常用字段，避免None
        xwlxmc = item.get('xwlxmc', '')
        info += f", xwlxmc: {xwlxmc}"
    # 如果有province_code，补充到info
    if province_code is not None:
        info += f", province_code: {province_code}"
    log_line = f"[{timestamp}] [{request_type}] {info}，错误原因: 重试次数过多\n"
    with open('failed_requests.log', 'a', encoding='utf-8') as f:
        f.write(log_line)


async def do_sleep():
    interval = config.get('interval.seconds')  # 抓取时间间隔，单位为秒
    await asyncio.sleep(interval * random.uniform(0.8, 1.2))  # 随机延时，防止被封禁


class Crawler:
    def __init__(self, session, breakpoint=None, proxy_manager=None):
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
        self.proxy_manager = proxy_manager  # 代理管理器

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
            log_failed_request('fetch_school_info', info, province_code=province_code)
            return
        self.form_data['ssdm'] = province_code
        self.form_data['curPage'] = curPage
        self.form_data['start'] = str((curPage - 1) * 10)

        try:
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
                        log_failed_request('fetch_school_info_msg_type', str(data), province_code=province_code)
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
                            log_failed_request('fetch_school_info_msg_type', str(data), province_code=province_code)
                            return

                    if data.get('msg') and isinstance(data.get('msg'), dict) and data.get('msg').get('nextPageAvailable') and go_on:
                        await do_sleep()
                        await self.fetch_school_info(province_code, curPage + 1)
                else:
                    print(f"请求失败，状态码: {response.status}")
                    await self.fetch_school_info(province_code, curPage, False, retry + 1)
                    return None
        except aiohttp.ClientConnectorError as e:
            print(f"网络连接错误：{e}")
            if self.proxy_manager and self.proxy_manager.should_use_proxy():
                print("尝试切换代理...")
                new_proxy = await self.proxy_manager.switch_proxy()
                if new_proxy:
                    print(f"已切换到新代理: {new_proxy}")
                    if retry < 3:
                        print(f"等待5秒后重试...")
                        await asyncio.sleep(5)
                        await self.fetch_school_info(province_code, curPage, False, retry + 1)
                    else:
                        print("网络连接失败，跳过当前省份")
                        log_failed_request('fetch_school_info_network_error', f"省份代码: {province_code}, 当前页: {curPage}", province_code=province_code)
                else:
                    # 所有代理都失败，使用自身IP
                    print("所有代理都失败，尝试使用自身IP...")
                    if retry < 2:  # 给自身IP一次重试机会
                        await asyncio.sleep(3)
                        await self.fetch_school_info(province_code, curPage, False, retry + 1)
                    else:
                        # 自身IP也失败，记录错误并结束程序
                        error_info = f"省份代码: {province_code}, 当前页: {curPage}, 错误: {e}"
                        self.proxy_manager.record_direct_ip_failure(error_info)
                        print("自身IP也失败，程序退出")
                        sys.exit(1)
            else:
                # 没有代理或已经是自身IP
                if retry < 2:
                    print(f"等待5秒后重试...")
                    await asyncio.sleep(5)
                    await self.fetch_school_info(province_code, curPage, False, retry + 1)
                else:
                    # 自身IP失败，记录错误并结束程序
                    error_info = f"省份代码: {province_code}, 当前页: {curPage}, 错误: {e}"
                    if self.proxy_manager:
                        self.proxy_manager.record_direct_ip_failure(error_info)
                    else:
                        # 如果没有代理管理器，直接记录到文件
                        with open('ip_failure.log', 'a', encoding='utf-8') as f:
                            timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                            f.write(f"[{timestamp}] 自身IP失败: {error_info}\n")
                    print("自身IP也失败，程序退出")
                    sys.exit(1)
        except Exception as e:
            print(f"请求异常：{e}")
            if retry < 3:
                print(f"等待3秒后重试...")
                await asyncio.sleep(3)
                await self.fetch_school_info(province_code, curPage, False, retry + 1)
            else:
                print("请求失败，跳过当前省份")
                log_failed_request('fetch_school_info_exception', f"省份代码: {province_code}, 当前页: {curPage}, 错误: {e}", province_code=province_code)

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
        try:
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
        except aiohttp.ClientConnectorError as e:
            print(f"网络连接错误：{e}")
            if self.proxy_manager and self.proxy_manager.should_use_proxy():
                print("尝试切换代理...")
                new_proxy = await self.proxy_manager.switch_proxy()
                if new_proxy:
                    print(f"已切换到新代理: {new_proxy}")
                    if retry < 3:
                        print(f"等待5秒后重试...")
                        await asyncio.sleep(5)
                        await self.fetch_school_major(obj, curPage, False, retry + 1)
                    else:
                        print("网络连接失败，跳过当前学校")
                        log_failed_request('fetch_school_major_network_error', f"学校: {obj.get('dwmc')}, 当前页: {curPage}", obj)
                else:
                    # 所有代理都失败，使用自身IP
                    print("所有代理都失败，尝试使用自身IP...")
                    if retry < 2:  # 给自身IP一次重试机会
                        await asyncio.sleep(3)
                        await self.fetch_school_major(obj, curPage, False, retry + 1)
                    else:
                        # 自身IP也失败，记录错误并结束程序
                        error_info = f"学校: {obj.get('dwmc')}, 当前页: {curPage}, 错误: {e}"
                        self.proxy_manager.record_direct_ip_failure(error_info)
                        print("自身IP也失败，程序退出")
                        sys.exit(1)
            else:
                # 没有代理或已经是自身IP
                if retry < 2:
                    print(f"等待5秒后重试...")
                    await asyncio.sleep(5)
                    await self.fetch_school_major(obj, curPage, False, retry + 1)
                else:
                    # 自身IP失败，记录错误并结束程序
                    error_info = f"学校: {obj.get('dwmc')}, 当前页: {curPage}, 错误: {e}"
                    if self.proxy_manager:
                        self.proxy_manager.record_direct_ip_failure(error_info)
                    else:
                        # 如果没有代理管理器，直接记录到文件
                        with open('ip_failure.log', 'a', encoding='utf-8') as f:
                            timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                            f.write(f"[{timestamp}] 自身IP失败: {error_info}\n")
                    print("自身IP也失败，程序退出")
                    sys.exit(1)
        except Exception as e:
            print(f"请求异常：{e}")
            if retry < 3:
                print(f"等待3秒后重试...")
                await asyncio.sleep(3)
                await self.fetch_school_major(obj, curPage, False, retry + 1)
            else:
                print("请求失败，跳过当前学校")
                log_failed_request('fetch_school_major_exception', f"学校: {obj.get('dwmc')}, 当前页: {curPage}, 错误: {e}", obj)

    async def _fetch_major_detail(self, item, detail_form_data, go_on=True, retry=0):
        if retry > 5:
            print("重试次数过多，放弃当前专业详情抓取")
            info = f"专业: {item.get('zymc')}, 学校: {item.get('dwmc')}"
            log_failed_request('fetch_major_detail', info, item)
            return
        try:
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
        except aiohttp.ClientConnectorError as e:
            print(f"网络连接错误：{e}")
            if self.proxy_manager and self.proxy_manager.should_use_proxy():
                print("尝试切换代理...")
                new_proxy = await self.proxy_manager.switch_proxy()
                if new_proxy:
                    print(f"已切换到新代理: {new_proxy}")
                    if retry < 3:
                        print(f"等待5秒后重试...")
                        await asyncio.sleep(5)
                        await self._fetch_major_detail(item, detail_form_data, False, retry + 1)
                    else:
                        print("网络连接失败，跳过当前请求")
                        log_failed_request('fetch_major_detail_network_error', f"专业: {item.get('zymc')}, 学校: {item.get('dwmc')}", item)
                else:
                    # 所有代理都失败，使用自身IP
                    print("所有代理都失败，尝试使用自身IP...")
                    if retry < 2:  # 给自身IP一次重试机会
                        await asyncio.sleep(3)
                        await self._fetch_major_detail(item, detail_form_data, False, retry + 1)
                    else:
                        # 自身IP也失败，记录错误并结束程序
                        error_info = f"专业: {item.get('zymc')}, 学校: {item.get('dwmc')}, 错误: {e}"
                        self.proxy_manager.record_direct_ip_failure(error_info)
                        print("自身IP也失败，程序退出")
                        sys.exit(1)
            else:
                # 没有代理或已经是自身IP
                if retry < 2:
                    print(f"等待5秒后重试...")
                    await asyncio.sleep(5)
                    await self._fetch_major_detail(item, detail_form_data, False, retry + 1)
                else:
                    # 自身IP失败，记录错误并结束程序
                    error_info = f"专业: {item.get('zymc')}, 学校: {item.get('dwmc')}, 错误: {e}"
                    if self.proxy_manager:
                        self.proxy_manager.record_direct_ip_failure(error_info)
                    else:
                        # 如果没有代理管理器，直接记录到文件
                        with open('ip_failure.log', 'a', encoding='utf-8') as f:
                            timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                            f.write(f"[{timestamp}] 自身IP失败: {error_info}\n")
                    print("自身IP也失败，程序退出")
                    sys.exit(1)
        except Exception as e:
            print(f"请求异常：{e}")
            if retry < 3:
                print(f"等待3秒后重试...")
                await asyncio.sleep(3)
                await self._fetch_major_detail(item, detail_form_data, False, retry + 1)
            else:
                print("请求失败，跳过当前请求")
                log_failed_request('fetch_major_detail_exception', f"专业: {item.get('zymc')}, 学校: {item.get('dwmc')}, 错误: {e}", item)


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
        # fetch_school_major/fetch_school_info
        if '[fetch_school_major_no_flag]' in line or '[fetch_school_major_msg_type]' in line:
            # print('日志原文:', line.strip())
            m = re.search(r'\] \[fetch_school_major.*?\] (\{.*\})[\s\S]*错误原因', line)
            if not m:
                # print('正则未匹配到大括号内容')
                lines_to_keep.append(line)
                continue
            # print('正则提取内容:', m.group(1))
            try:
                info = ast.literal_eval(m.group(1))
            except Exception as e:
                # print('ast.literal_eval 失败:', e)
                lines_to_keep.append(line)
                continue
            dwdm = info.get('zsmlcxModel', {}).get('dwdm')
            dwmc = info.get('zsmlcxModel', {}).get('dwmc')
            curPage = int(info.get('params', {}).get('curPage', ['1'])[0])
            zydm = info.get('zsmlcxModel', {}).get('zydm', '')
            zymc = info.get('zsmlcxModel', {}).get('zymc', '')
            key = (dwdm, dwmc, curPage)
            if key in retried:
                continue
            # 判断是school级别还是major级别
            if (not zydm and not zymc) or (zydm == '' and zymc == ''):
                # school级别，重试fetch_school_info
                # 优先从 info 结构和日志字符串中获取 province_code 或 ssdm
                # print('日志原文:', line.strip())
                # print('正则提取内容:', m.group(1))
                province_code = None
                # 1. 尝试从 zsmlcxModel.ssdm 获取
                province_code = info.get('zsmlcxModel', {}).get('ssdm')
                # print('zsmlcxModel.ssdm:', province_code)
                # 2. 如果没有，再尝试从日志字符串中正则提取 province_code: xx
                if not province_code:
                    m2 = re.search(r'province_code: (\d+)', line)
                    if m2:
                        province_code = m2.group(1)
                # print('最终用于重试的 province_code:', province_code)
                # 3. 如果还没有，提示并跳过
                if not province_code:
                    print(f'无法获取省份代码，跳过该school级别日志：{line.strip()}')
                    lines_to_keep.append(line)
                    continue
                # print(f'重试日志失败请求（school级别）：学校={dwmc}, dwdm={dwdm}, 当前页={curPage}, 省份代码={province_code}')
                try:
                    await school_instance.fetch_school_info(province_code, curPage)
                    handled = True
                    retry_count += 1
                except Exception as e:
                    print(f'重试失败：{e}')
                    lines_to_keep.append(line)
                    continue
            else:
                # major级别，重试fetch_school_major
                # print(f'重试日志失败请求（major级别）：学校={dwmc}, dwdm={dwdm}, 当前页={curPage}')
                obj = {'dwdm': dwdm, 'dwmc': dwmc}
                retry_crawler = type(school_instance)(school_instance.session, breakpoint={}, proxy_manager=school_instance.proxy_manager)
                retry_crawler.login_prompt_count = 0  # 重置登录提示计数
                try:
                    await retry_crawler.fetch_school_major(obj, curPage)
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
                # print(f'重试日志失败请求：专业={item["zymc"]}, 学校代码={item["dwdm"]}, 专业代码={item["zydm"]}, 学位类型={item["xwlxmc"]}')
                retry_crawler = type(school_instance)(school_instance.session, breakpoint={}, proxy_manager=school_instance.proxy_manager)
                retry_crawler.login_prompt_count = 0  # 重置登录提示计数
                try:
                    await retry_crawler._fetch_major_detail(item, detail_form_data)
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
