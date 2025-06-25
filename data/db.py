import logging


from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy.orm import sessionmaker
from config import config
from data import entity
from data.entity import Major

database = config.get('database', {})

DATABASE_URL = (
    f"mysql+pymysql://{database.get('username')}:{database.get('password')}"
    f"@{database.get('host')}:{database.get('port')}/{database.get('name')}?charset=utf8mb4"
)

engine = create_engine(DATABASE_URL, echo=False)

Session = sessionmaker(bind=engine)
logging.getLogger('sqlalchemy').setLevel(logging.ERROR)


def insert(item):
    """
    插入 Major 实体数据
    """
    session = Session()
    try:
        # 提取考试科目名称（最多4科）
        kskmz = item.get("kskmz")
        exam_subjects = ["", "", "", ""]
        if kskmz and isinstance(kskmz, list):
            km = kskmz[0]
            exam_subjects[0] = km.get("km1Vo", {}).get("kskmmc", "")
            exam_subjects[1] = km.get("km2Vo", {}).get("kskmmc", "")
            exam_subjects[2] = km.get("km3Vo", {}).get("kskmmc", "")
            exam_subjects[3] = km.get("km4Vo", {}).get("kskmmc", "")

        # 构造 Major 实例
        major = Major(
            school_name=item.get("dwmc"),
            major_name=item.get("zymc"),
            province=item.get("szss"),
            major_code=item.get("zydm"),
            degree_type=item.get('xwlxmc'),
            exam_type=item.get("ksfsmc"),
            department=item.get("yxsmc"),
            study_mode="全日制" if item.get("xxfs") == "1" else "非全日制",
            research_direction=item.get("yjfxmc"),
            veteran_program="是" if item.get("tydxs") == "1" else "否",
            shaogu_program="是" if item.get("jsggjh") == "1" else "否",
            advisor=item.get("zdjs"),
            planned_enrollment=item.get("nzsrsstr"),
            exam_subject1=exam_subjects[0],
            exam_subject2=exam_subjects[1],
            exam_subject3=exam_subjects[2],
            exam_subject4=exam_subjects[3],
        )

        session.add(major)
        session.commit()
        print(f"成功插入：{item.get('zymc')}-{item.get("yjfxmc")}")
    except IntegrityError:
        session.rollback()
        print("记录已存在，插入被忽略")
    except SQLAlchemyError as e:
        session.rollback()
        print(f"插入失败：{e}")
    finally:
        session.close()

def get_last_major():
    """
    获取 major 表最后一条记录的省份、学校、专业代码
    """
    session = Session()
    try:
        last_major = session.query(Major).order_by(Major.id.desc()).first()
        if last_major:
            return {
                'province': last_major.province,
                'school_name': last_major.school_name,
                'major_code': last_major.major_code
            }
        else:
            return None
    except SQLAlchemyError as e:
        print(f"查询最后一条 major 记录失败：{e}")
        return None
    finally:
        session.close()
