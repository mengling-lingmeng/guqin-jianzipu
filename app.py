import os
import time
import hashlib
from flask import Flask, request, jsonify, send_from_directory, session
from flask_cors import CORS
import pymysql
from db_util import get_connection
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'your-secret-key-please-change-this'   # 请修改为随机字符串
CORS(app, supports_credentials=True)

# 上传配置
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# ------------------ 模拟识别函数 ------------------
def fake_recognize(image_id, image_path):
    """从 classes.txt 读取所有减字符号，作为模拟识别结果插入数据库"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM RecognitionResult WHERE image_id = %s", (image_id,))

    classes_file = os.path.join(os.path.dirname(__file__), 'classes.txt')
    try:
        try:
            with open(classes_file, 'r', encoding='utf-8') as f:
                char_codes = [line.strip() for line in f.readlines() if line.strip()]
        except UnicodeDecodeError:
            with open(classes_file, 'r', encoding='gbk') as f:
                char_codes = [line.strip() for line in f.readlines() if line.strip()]
    except FileNotFoundError:
        char_codes = ['中十挑七', '名十二勾四', '大九勹五']
        print(f"警告: 未找到 {classes_file}，使用默认字符列表")

    if not char_codes:
        char_codes = ['中十挑七', '名十二勾四']

    # 查询数据库中已存在的 char_code
    cursor.execute("SELECT char_code FROM JianziChar")
    existing = {row[0] for row in cursor.fetchall()}

    # 只保留在数据库中存在的字符
    valid_codes = [code for code in char_codes if code in existing]
    if not valid_codes:
        print("警告: classes.txt 中的字符在数据库中不存在，使用默认字符")
        # 使用默认字符，但确保它们在数据库中
        default_codes = ['中十挑七', '名十二勾四']
        valid_codes = [code for code in default_codes if code in existing]
        if not valid_codes:
            print("错误: 数据库中没有任何减字符号，请先添加")
            conn.close()
            return

    import random
    random.seed(image_id)
    seq = 1
    for char_code in valid_codes[:50]:
        x = random.randint(50, 500)
        y = random.randint(50, 300)
        confidence = round(random.uniform(0.75, 0.98), 2)
        cursor.execute("""
            INSERT INTO RecognitionResult (image_id, char_code, position_x, position_y, confidence, sequence_order)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (image_id, char_code, x, y, confidence, seq))
        seq += 1

    cursor.execute("UPDATE JianzipuImage SET status = 'completed' WHERE image_id = %s", (image_id,))
    conn.commit()
    cursor.close()
    conn.close()
    print(f"模拟识别完成，共插入 {seq - 1} 个字符")

# ------------------ 页面服务 ------------------
@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

# ------------------ 数据库测试 ------------------
@app.route('/api/test-db')
def test_db():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.close()
        conn.close()
        return jsonify({'status': '数据库连接成功'})
    except Exception as e:
        return jsonify({'status': '数据库连接失败', 'error': str(e)})

# ------------------ 获取所有减字字符 ------------------
@app.route('/api/characters', methods=['GET'])
def get_characters():
    conn = get_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute("SELECT char_id, char_code, left_finger, right_finger, description FROM JianziChar")
    result = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(result)

# ------------------ 上传图片（需登录） ------------------
@app.route('/api/upload', methods=['POST'])
def upload_image():
    if 'user_id' not in session:
        return jsonify({'error': '请先登录'}), 401
    user_id = session['user_id']

    if 'file' not in request.files:
        return jsonify({'error': '未找到文件'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': '未选择文件'}), 400
    if not allowed_file(file.filename):
        return jsonify({'error': '不支持的图片格式'}), 400

    filename = secure_filename(file.filename)
    name, ext = os.path.splitext(filename)
    filename = f"{name}_{int(time.time())}{ext}"
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)

    title = request.form.get('title', '未命名')
    dynasty = request.form.get('dynasty', '')
    author = request.form.get('author', '')

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO JianzipuImage (user_id, title, dynasty, author, image_path, status) VALUES (%s, %s, %s, %s, %s, 'pending')",
        (user_id, title, dynasty, author, filepath)
    )
    image_id = cursor.lastrowid
    conn.commit()
    cursor.close()
    conn.close()

    # 调用模拟识别（真实识别可替换此函数）
    fake_recognize(image_id, filepath)

    return jsonify({'image_id': image_id, 'message': '上传成功，识别完成'})

# ------------------ 获取识别结果 ------------------
@app.route('/api/recognition/<int:image_id>', methods=['GET'])
def get_recognition(image_id):
    conn = get_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute("""
        SELECT r.result_id, r.char_code, r.position_x, r.position_y, r.confidence, r.sequence_order,
               c.left_finger, c.right_finger, c.description
        FROM RecognitionResult r
        JOIN JianziChar c ON r.char_code = c.char_code
        WHERE r.image_id = %s
        ORDER BY r.sequence_order
    """, (image_id,))
    result = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(result)

# ------------------ 检索接口（管理员可见所有，普通用户仅见自己） ------------------
@app.route('/api/search', methods=['GET'])
def search():
    if 'user_id' not in session:
        return jsonify({'error': '请先登录'}), 401
    user_id = session['user_id']
    role = session.get('role', 'user')

    keyword = request.args.get('keyword', '')
    search_type = request.args.get('type', 'title')

    conn = get_connection()
    cursor = conn.cursor()

    # 构造查询条件
    if role == 'admin':
        user_condition = ""
        params = []
    else:
        user_condition = " AND user_id = %s"
        params = [user_id]

    if search_type == 'title':
        sql = f"SELECT * FROM JianzipuImage WHERE title LIKE %s{user_condition}"
        params.insert(0, '%' + keyword + '%')
    elif search_type == 'finger':
        sql = f"""
            SELECT DISTINCT i.* FROM JianzipuImage i
            JOIN RecognitionResult r ON i.image_id = r.image_id
            JOIN JianziChar c ON r.char_code = c.char_code
            WHERE (c.left_finger LIKE %s OR c.right_finger LIKE %s){user_condition}
        """
        params = ['%' + keyword + '%', '%' + keyword + '%'] + params
    elif search_type == 'dynasty':
        sql = f"SELECT * FROM JianzipuImage WHERE dynasty LIKE %s{user_condition}"
        params.insert(0, '%' + keyword + '%')
    elif search_type == 'author':
        sql = f"SELECT * FROM JianzipuImage WHERE author LIKE %s{user_condition}"
        params.insert(0, '%' + keyword + '%')
    else:
        return jsonify([])

    cursor.execute(sql, params)
    rows = cursor.fetchall()
    col_names = [desc[0] for desc in cursor.description]
    results = [dict(zip(col_names, row)) for row in rows]
    cursor.close()
    conn.close()
    return jsonify(results)

# ------------------ 用户认证 ------------------
@app.route('/api/current_user', methods=['GET'])
def current_user():
    if 'user_id' in session:
        return jsonify({
            'user_id': session['user_id'],
            'username': session.get('username'),
            'role': session.get('role')
        })
    else:
        return jsonify({'error': '未登录'}), 401

@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    if not username or not password:
        return jsonify({'error': '用户名和密码不能为空'}), 400
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO User (username, password, role) VALUES (%s, %s, 'user')",
                       (username, hash_password(password)))
        conn.commit()
        return jsonify({'message': '注册成功'})
    except pymysql.IntegrityError:
        return jsonify({'error': '用户名已存在'}), 400
    finally:
        cursor.close()
        conn.close()

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    conn = get_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute("SELECT user_id, username, role FROM User WHERE username=%s AND password=%s",
                   (username, hash_password(password)))
    user = cursor.fetchone()
    cursor.close()
    conn.close()
    if user:
        session['user_id'] = user['user_id']
        session['username'] = user['username']
        session['role'] = user['role']
        return jsonify({'message': '登录成功', 'user': user})
    else:
        return jsonify({'error': '用户名或密码错误'}), 401

@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'message': '已退出登录'})

# ------------------ 获取用户自己的图片列表（可选） ------------------
@app.route('/api/myimages', methods=['GET'])
def my_images():
    if 'user_id' not in session:
        return jsonify({'error': '未登录'}), 401
    user_id = session['user_id']
    conn = get_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute("SELECT * FROM JianzipuImage WHERE user_id=%s", (user_id,))
    result = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(result)

# ------------------ 静态文件服务（上传的图片） ------------------
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/api/add_char', methods=['POST'])
def add_char():
    # 检查登录状态
    if 'user_id' not in session:
        return jsonify({'error': '请先登录'}), 401
    # 仅管理员可添加
    if session.get('role') != 'admin':
        return jsonify({'error': '权限不足，仅管理员可添加'}), 403

    data = request.get_json()
    char_code = data.get('char_code')
    left_finger = data.get('left_finger')
    left_position = data.get('left_position')
    right_finger = data.get('right_finger')
    string_num = data.get('string_num')
    description = data.get('description')

    if not char_code:
        return jsonify({'error': '字符代码不能为空'}), 400

    conn = get_connection()
    cursor = conn.cursor()
    try:
        # 检查是否已存在
        cursor.execute("SELECT char_code FROM JianziChar WHERE char_code = %s", (char_code,))
        if cursor.fetchone():
            return jsonify({'error': '该字符已存在'}), 400

        # 插入新字符
        cursor.execute(
            "INSERT INTO JianziChar (char_code, left_finger, left_position, right_finger, string_num, description) VALUES (%s, %s, %s, %s, %s, %s)",
            (char_code, left_finger, left_position, right_finger, string_num, description)
        )
        conn.commit()
        return jsonify({'message': '添加成功'})
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()



if __name__ == '__main__':
    app.run(debug=True, port=5000)