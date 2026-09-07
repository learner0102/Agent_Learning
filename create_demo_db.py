# create_demo_db.py - 生成示例 SQLite 数据库 demo.db（供 query_database 工具使用）
import os
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "demo.db"

SCHEMA = [
    """CREATE TABLE employees (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        department TEXT NOT NULL,
        city TEXT NOT NULL,
        salary INTEGER NOT NULL
    )""",
    """CREATE TABLE products (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        category TEXT NOT NULL,
        price REAL NOT NULL,
        stock INTEGER NOT NULL
    )""",
    """CREATE TABLE sales (
        id INTEGER PRIMARY KEY,
        product_id INTEGER NOT NULL,
        quantity INTEGER NOT NULL,
        amount REAL NOT NULL,
        sale_date TEXT NOT NULL
    )""",
]

EMPLOYEES = [
    (1, "张伟", "研发", "北京", 25000),
    (2, "李娜", "研发", "上海", 23000),
    (3, "王强", "市场", "北京", 18000),
    (4, "刘洋", "销售", "广州", 15000),
    (5, "陈静", "人事", "深圳", 14000),
    (6, "杨帆", "研发", "杭州", 26000),
    (7, "赵磊", "财务", "上海", 17000),
    (8, "周敏", "销售", "成都", 12000),
    (9, "孙杰", "市场", "深圳", 19000),
    (10, "吴芳", "财务", "北京", 16000),
]

PRODUCTS = [
    (1, "笔记本电脑", "电子", 6999, 120),
    (2, "智能手机", "电子", 3999, 300),
    (3, "显示器", "电子", 1299, 200),
    (4, "机械键盘", "外设", 499, 500),
    (5, "无线鼠标", "外设", 199, 800),
    (6, "会议摄像头", "外设", 899, 150),
    (7, "智能音箱", "智能家居", 399, 400),
    (8, "路由器", "网络", 299, 350),
]

SALES = [
    (1, 1, 2, 13998, "2026-01-05"),
    (2, 2, 5, 19995, "2026-01-12"),
    (3, 4, 10, 4990, "2026-02-01"),
    (4, 5, 20, 3980, "2026-02-10"),
    (5, 2, 8, 31992, "2026-03-03"),
    (6, 3, 6, 7794, "2026-03-15"),
    (7, 1, 3, 20997, "2026-04-02"),
    (8, 7, 15, 5985, "2026-04-20"),
    (9, 6, 4, 3596, "2026-05-11"),
    (10, 8, 12, 3588, "2026-05-25"),
    (11, 2, 10, 39990, "2026-06-08"),
    (12, 5, 30, 5970, "2026-06-19"),
]


def main():
    if DB_PATH.exists():
        os.remove(DB_PATH)

    conn = sqlite3.connect(str(DB_PATH))
    try:
        cur = conn.cursor()
        for ddl in SCHEMA:
            cur.execute(ddl)
        cur.executemany("INSERT INTO employees VALUES (?,?,?,?,?)", EMPLOYEES)
        cur.executemany("INSERT INTO products VALUES (?,?,?,?,?)", PRODUCTS)
        cur.executemany("INSERT INTO sales VALUES (?,?,?,?,?)", SALES)
        conn.commit()
    finally:
        conn.close()

    print(f"✅ 已生成示例数据库: {DB_PATH}")
    print("   包含表: employees / products / sales")


if __name__ == "__main__":
    main()
