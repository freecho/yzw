from sqlalchemy import Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class Major(Base):
    __tablename__ = 'major'

    id = Column(Integer, primary_key=True, autoincrement=True, comment='主键')
    school_name = Column(String(255), nullable=True, comment='学校名称')
    major_name = Column(String(255), nullable=True, comment='专业名称')
    province = Column(String(255), nullable=True, comment='所在省份')
    major_code = Column(String(255), nullable=True, comment='专业代码')
    degree_type = Column(String(255), nullable=True, comment='学位类型')
    exam_type = Column(String(255), nullable=True, comment='考试方式')
    department = Column(String(255), nullable=True, comment='院系所')
    study_mode = Column(String(255), nullable=True, comment='学习方式')
    research_direction = Column(String(255), nullable=True, comment='研究方向')
    veteran_program = Column(String(255), nullable=True, comment='退役计划')
    shaogu_program = Column(String(255), nullable=True, comment='少骨计划')
    advisor = Column(String(255), nullable=True, comment='指导教师')
    planned_enrollment = Column(String(255), nullable=True, comment='拟招生人数')
    exam_subject1 = Column(String(255), nullable=True, comment='考试科目1')
    exam_subject2 = Column(String(255), nullable=True, comment='考试科目2')
    exam_subject3 = Column(String(255), nullable=True, comment='考试科目3')
    exam_subject4 = Column(String(255), nullable=True, comment='考试科目4')
