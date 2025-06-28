import asyncio

import aiohttp

from crawler.login import Login
from crawler.crawler import Crawler
from data import db  # 新增导入
from crawler.crawler import retry_failed_requests
from proxy_manager import ProxyManager
from config import config

ssList = [
        {
            'code': '1',
            'name': '一区',
            'children':
                [
                    {'code': '11', 'name': '北京'},
                    {'code': '12', 'name': '天津'},
                    {'code': '13', 'name': '河北'},
                    {'code': '14', 'name': '山西'},
                    {'code': '21', 'name': '辽宁'},
                    {'code': '22', 'name': '吉林'},
                    {'code': '23', 'name': '黑龙江'},
                    {'code': '31', 'name': '上海'},
                    {'code': '32', 'name': '江苏'},
                    {'code': '33', 'name': '浙江'},
                    {'code': '34', 'name': '安徽'},
                    {'code': '35', 'name': '福建'},
                    {'code': '36', 'name': '江西'},
                    {'code': '37', 'name': '山东'},
                    {'code': '41', 'name': '河南'},
                    {'code': '42', 'name': '湖北'},
                    {'code': '43', 'name': '湖南'},
                    {'code': '44', 'name': '广东'},
                    {'code': '50', 'name': '重庆'},
                    {'code': '51', 'name': '四川'},
                    {'code': '61', 'name': '陕西'}
                ]
        },
        {
            'code': '2',
            'name': '二区',
            'children':
                [
                    {'code': '15', 'name': '内蒙'},
                    {'code': '45', 'name': '广西'},
                    {'code': '46', 'name': '海南'},
                    {'code': '52', 'name': '贵州'},
                    {'code': '53', 'name': '云南'},
                    {'code': '54', 'name': '西藏'},
                    {'code': '62', 'name': '甘肃'},
                    {'code': '63', 'name': '青海'},
                    {'code': '64', 'name': '宁夏'},
                    {'code': '65', 'name': '新疆'}
                ]
        }
    ]

async def work():
    session = await Login().do_login()

    # 需要get访问同步登录状态
    await session.get('https://yz.chsi.com.cn/zsml/a/dw.do')

    # 代理功能选择
    print("\n请选择网络连接方式：")
    print("1. 使用代理池（推荐，可有效避免IP被封）")
    print("2. 使用自身IP（如果代理池不可用或不想使用代理）")
    
    while True:
        try:
            proxy_choice = input("请选择网络连接方式（输入1或2）：").strip()
            if proxy_choice in ['1', '2']:
                break
            else:
                print("请输入1或2")
        except KeyboardInterrupt:
            print("\n程序被用户中断")
            return

    # 初始化代理管理器
    proxy_manager = None
    
    if proxy_choice == '1':
        print("正在初始化代理管理器...")
        # 检查是否启用代理功能
        if config.get('proxy.enabled', False):
            proxy_pool_url = config.get('proxy.pool_url', 'http://127.0.0.1:5010')
            proxy_manager = ProxyManager(proxy_pool_url)
            try:
                # 尝试初始化代理（可选，如果代理池不可用会降级到自身IP）
                await proxy_manager.initialize_proxy()
                print("代理管理器初始化成功")
            except Exception as e:
                print(f"代理初始化失败，将使用自身IP: {e}")
                proxy_manager = None
        else:
            print("代理功能未启用，将使用自身IP")
    else:
        print("已选择使用自身IP")

    # 断点选择
    print("\n请选择断点模式：（数据抓取的起始点）")
    print("1. 从数据库获取最后一条记录作为断点")
    print("2. 手动输入断点参数")
    
    while True:
        try:
            choice = input("请选择模式（输入1或2）：").strip()
            if choice in ['1', '2']:
                break
            else:
                print("请输入1或2")
        except KeyboardInterrupt:
            print("\n程序被用户中断")
            return
    
    # 获取断点信息
    if choice == '1':
        # 模式1：从数据库获取最后一条记录
        last_major = db.get_last_major()
        last_province = last_major['province'] if last_major else None
        reached_province = False if last_province else True
        print(f"断点信息：last_province={last_province}, reached_province={reached_province}")
        if last_major:
            print(f"完整断点数据：{last_major}")
        else:
            print("没有找到断点数据，将从第一个省份开始爬取")
    else:
        # 模式2：手动输入断点参数
        print("\n请输入断点参数：")
        try:
            province_name = input("省份名称（如：上海、内蒙等）：").strip()
            school_name = input("学校名称（可选，直接回车跳过）：").strip() or None
            major_code = input("专业代码（可选，直接回车跳过）：").strip() or None
            
            # 验证省份名称是否在列表中
            valid_provinces = []
            for ss in ssList:
                for child in ss['children']:
                    valid_provinces.append(child['name'])
            
            if province_name not in valid_provinces:
                print(f"错误：省份名称 '{province_name}' 不在有效列表中")
                print(f"有效省份：{', '.join(valid_provinces)}")
                return
            
            last_major = {
                'province': province_name,
                'school_name': school_name,
                'major_code': major_code
            }
            last_province = province_name
            reached_province = False
            print(f"断点信息：last_province={last_province}, reached_province={reached_province}")
            print(f"完整断点数据：{last_major}")
            
        except KeyboardInterrupt:
            print("\n程序被用户中断")
            return
        except Exception as e:
            print(f"输入断点参数时出错：{e}")
            return

    # 获取爬虫实例
    crawler = Crawler(session, breakpoint=last_major, proxy_manager=proxy_manager)

    # 1. 先用断点crawler补抓日志失败项
    print("开始执行日志重试...")
    await retry_failed_requests(crawler)
    print("日志重试执行完毕，开始正常爬取流程...")

    # 2. 再顺序爬取
    print("开始遍历省份列表...")
    for ss in ssList:
        print(f"处理区域：{ss['name']}")
        for child in ss['children']:
            province_name = child['name']
            # 断点判断：未到断点省份则跳过
            if not reached_province:
                if province_name == last_province:
                    reached_province = True
                    print(f"到达断点省份：{province_name}")
                else:
                    print(f"跳过省份：{province_name}（未到断点）")
                    continue
            print(f"正在爬取{province_name}的学校信息...")
            await crawler.fetch_school_info(child['code'])
            print(f"{province_name}的学校信息爬取完成！")

    print("所有省份爬取完成！")
    await session.close()


asyncio.run(work())
