import pymysql
from db_config import DB_CONFIG

def get_connection():
    return pymysql.connect(
        host=DB_CONFIG['host'],
        user=DB_CONFIG['user'],
        password=DB_CONFIG['password'],
        database=DB_CONFIG['database'],
        charset=DB_CONFIG['charset'],
        ssl=None           # 明确禁用 SSL
    )