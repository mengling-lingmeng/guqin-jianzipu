import os

DB_CONFIG = {
    'host': os.environ.get('MYSQL_HOST', 'localhost'),
    'user': os.environ.get('MYSQL_USER', 'root'),
    'password': os.environ.get('MYSQL_PASSWORD', '040508'),
    'database': os.environ.get('MYSQL_DATABASE', 'guqin_jianzipu'),
    'charset': 'utf8mb4',
    'ssl': None
}