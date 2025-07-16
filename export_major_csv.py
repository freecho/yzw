import csv
from sqlalchemy.orm import sessionmaker
from data.db import engine
from data.entity import Major

# ====== 你可以在这里自定义导出文件名 ======
EXPORT_FILENAME = 'majors.csv'  # 改成你想要的文件名
# =========================================

BATCH_SIZE = 1000

def export_major_to_csv():
    """
    导出major表所有字段为csv，支持自定义文件名，分批写入避免内存爆炸。
    """
    Session = sessionmaker(bind=engine)
    session = Session()
    offset = 0
    fields = [c.name for c in Major.__table__.columns]

    with open(EXPORT_FILENAME, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(fields)  # 写表头
        while True:
            rows = (
                session.query(Major)
                .order_by(Major.province, Major.school_name)
                .offset(offset)
                .limit(BATCH_SIZE)
                .all()
            )
            if not rows:
                break
            for row in rows:
                writer.writerow([getattr(row, field) for field in fields])
            offset += BATCH_SIZE
    session.close()
    print(f"导出完成，文件名：{EXPORT_FILENAME}")

if __name__ == '__main__':
    export_major_to_csv() 