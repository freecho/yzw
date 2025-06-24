import asyncio

import aiohttp

from crawler.login import Login
from crawler.crawler import School


async def work():
    print("请输入下面信息！")
    username = input("账号：")
    password = input("密码：")

    # 创建登录实例
    login = Login(username, password)
    session = await login.get_session()
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
                    {'code': '15', 'name': '内蒙古'},
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

    # 需要get访问同步登录状态
    await session.get('https://yz.chsi.com.cn/zsml/a/dw.do')

    # 获取学校信息 todo
    school = School(session)
    for ss in ssList:
        for child in ss['children']:
            print(f"正在爬取{child['name']}的学校信息...")
            await school.fetch_school_info(child['code'])
            print(f"{child['name']}的学校信息爬取完成！")


    await session.close()


asyncio.run(work())
