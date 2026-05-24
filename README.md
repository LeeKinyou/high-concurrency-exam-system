# dExam - 在线考试系统

基于 Django 框架开发的教育场景考试管理平台，支持教师出题组卷、发布考试，学生在线答题、自动评分与人工阅卷。

## 技术栈

| 类别 | 技术 |
|------|------|
| 后端框架 | Django 6.0 |
| 数据库 | SQLite（可切换 MySQL） |
| 缓存 | Redis |
| 异步任务 | Celery |
| 文件存储 | MinIO / 本地 |
| 语言 | Python 3.12 |
| 包管理 | uv |

## 快速开始

### 1. 安装依赖

```bash
# 安装 uv（如未安装）
pip install uv

# 安装项目依赖
uv pip install -e .
# 开发依赖
uv pip install -e ".[dev]"
# MySQL 支持（可选）
uv pip install -e ".[mysql]"
```

### 2. 配置环境变量

复制并编辑 `.env` 文件：

```bash
cp .env.example .env
```

`.env` 主要配置项：

```env
# 必须修改
SECRET_KEY=your-secret-key-here

# 数据库（默认 SQLite，切换 MySQL 改为 DB_ENGINE=mysql）
DB_ENGINE=sqlite

# Redis 缓存（留空则使用内存缓存）
REDIS_URL=redis://:password@host:6379/0

# Celery 异步任务
CELERY_BROKER_URL=redis://:password@host:6379/1

# MinIO 文件存储（默认关闭，使用本地 media/ 目录）
USE_MINIO=False
```

### 3. 初始化数据库

```bash
python manage.py makemigrations accounts
python manage.py migrate
```

### 4. 创建管理员账号

```bash
python manage.py create_admin --username admin --password Admin@1234 --name 管理员
```

### 5. 启动服务

```bash
python manage.py runserver
```

访问 http://localhost:8000 即可。

## 登录说明

系统提供两种角色的登录入口：

### 学生登录

- 地址：`/accounts/login/`
- 支持**用户名**或**学号**登录
- 首次登录需修改密码（由管理员批量导入时设置默认密码）

### 教师登录

- 地址：`/accounts/teacher/login/`
- 使用管理员分配的用户名和密码登录

### 默认管理员账号

使用 `create_admin` 命令创建的账号可登录教师端，同时拥有 Django Admin 后台权限（`/admin/`）。

### 批量导入学生

管理员可通过 Django Admin 或 API 上传 Excel 文件批量创建学生账号。Excel 格式：

| 学号 | 姓名 | 邮箱 |
|------|------|------|
| 2024001 | 张三 | zhang@example.com |
| 2024002 | 李四 | li@example.com |

- 默认密码为学号后 6 位
- 首次登录强制修改密码

## 运行测试

```bash
# 运行全部测试
pytest

# 运行指定模块测试
pytest tests/test_core/ -v
pytest tests/test_auth/ -v

# 查看覆盖率
pytest --cov=core --cov=accounts
```

## 项目结构

```
dExam/
├── config/              # Django 项目配置
│   ├── settings/        # 分环境配置（base/development/production/testing）
│   ├── urls.py          # 主路由
│   ├── celery.py        # Celery 配置
│   └── wsgi.py / asgi.py
├── core/                # 核心公共模块（异常、常量、响应、中间件、工具）
├── accounts/            # 用户认证模块（登录、改密、权限、批量导入）
├── examination/         # 考试核心模块（待开发）
├── templates/           # HTML 模板
├── tests/               # 测试代码
├── manage.py
├── pyproject.toml
└── .env                 # 环境变量配置
```

## 数据库切换

默认使用 SQLite，适合开发和 100-200 人规模的考试。如需切换 MySQL：

1. 安装 MySQL 驱动：`uv pip install -e ".[mysql]"`
2. 修改 `.env`：`DB_ENGINE=mysql`
3. 配置数据库连接信息
4. 执行迁移：`python manage.py migrate`
