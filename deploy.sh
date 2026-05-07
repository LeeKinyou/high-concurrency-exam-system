#!/bin/bash

# 考试系统部署脚本

echo "开始部署考试系统..."

# 1. 创建虚拟环境
echo "创建虚拟环境..."
python3 -m venv venv
source venv/bin/activate

# 2. 安装依赖
echo "安装依赖包..."
pip install --upgrade pip
pip install -r requirements.txt

# 3. 数据库迁移
echo "执行数据库迁移..."
python manage.py makemigrations
python manage.py migrate

# 4. 收集静态文件
echo "收集静态文件..."
python manage.py collectstatic --noinput

# 5. 创建超级用户（可选）
echo "是否创建超级用户？(y/n)"
read -p "> " create_superuser
if [ "$create_superuser" = "y" ]; then
    python manage.py createsuperuser
fi

echo "部署完成！"
echo "启动服务: python manage.py runserver 0.0.0.0:8000"
