from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from data.entity import Base

# 请根据实际情况修改数据库连接信息
DATABASE_URL = "mysql+pymysql://root:123456@localhost:3306/yzw?charset=utf8mb4"

# 创建数据库引擎
engine = create_engine(DATABASE_URL, echo=True)

# 创建Session工厂
Session = sessionmaker(bind=engine) 