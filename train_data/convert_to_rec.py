import os

# 路径配置
image_dir = "./images"  # 图片文件夹
label_dir = "./labels"  # YOLO 标签文件夹
classes_file = "./classes.txt"  # 类别列表文件
output_file = "./rec_gt_train.txt"  # 输出文件

# 读取类别映射 (id -> char_code)
with open(classes_file, 'r', encoding='gbk') as f:
    classes = [line.strip() for line in f.readlines()]

# 打开输出文件
with open(output_file, 'w', encoding='utf-8') as out:
    # 遍历 labels 文件夹中的所有 txt 文件
    for label_file in os.listdir(label_dir):
        if not label_file.endswith('.txt'):
            continue
        # 获取对应的图片文件名（假设图片和标签文件名相同，扩展名为 .jpg/.png）
        base = os.path.splitext(label_file)[0]
        # 尝试找到匹配的图片（支持 jpg, png）
        img_ext = None
        for ext in ['.jpg', '.jpeg', '.png']:
            if os.path.exists(os.path.join(image_dir, base + ext)):
                img_ext = ext
                break
        if img_ext is None:
            print(f"警告: 找不到图片 {base}.*，跳过")
            continue
        img_path = os.path.join(image_dir, base + img_ext)

        # 读取标签文件
        with open(os.path.join(label_dir, label_file), 'r') as lf:
            lines = lf.readlines()
        for line in lines:
            parts = line.strip().split()
            if len(parts) < 5:
                continue
            class_id = int(parts[0])
            char_code = classes[class_id]  # 获取减字符号
            # 每行格式: 图片绝对路径\t标签
            out.write(f"{os.path.abspath(img_path)}\t{char_code}\n")

print(f"转换完成，输出文件: {output_file}")