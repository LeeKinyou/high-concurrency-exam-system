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
| Excel 处理 | openpyxl |
| 二维码 | qrcode + Pillow |
| 语言 | Python 3.12 |
| 包管理 | uv |

## 功能概览

### 学生端
- 考试列表（支持公开/班级限定考试）
- 在线答题（选择题/填空题，自动保存草稿）
- 考试码/扫码进入考试
- 成绩查看（答题详情与判分结果）

### 教师端
- 仪表盘（考试/题目/班级统计）
- 考试管理（创建/编辑/删除，时间窗口控制）
- 题目管理（手动创建/Excel 批量导入）
- 班级管理（学生分配）
- 成绩管理（统计分析/Excel 导出）
- 二维码生成（考试入口二维码）
- 审计日志（切屏/复制粘贴检测）

### 系统功能
- 自动判分（选择题精确匹配，填空题多答案匹配）
- Celery 自动交卷（考试结束后自动提交）
- 防作弊系统（切屏检测、复制粘贴检测）
- 消息通知（考试创建通知）
- IP 限流（登录安全）

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
python manage.py makemigrations
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

## URL 路由

### 学生端

| 路径 | 功能 |
|------|------|
| `/accounts/login/` | 学生登录 |
| `/accounts/teacher/login/` | 教师登录 |
| `/accounts/logout/` | 登出 |
| `/accounts/change-password/` | 修改密码 |
| `/exams/` | 考试列表 |
| `/exams/<id>/` | 考试详情 |
| `/exams/<id>/take/` | 答题页面 |
| `/exams/<id>/submit/` | 提交答卷 |
| `/exams/<id>/result/` | 查看成绩 |
| `/exams/<id>/enter/` | 考试码验证 |

### 教师端

| 路径 | 功能 |
|------|------|
| `/teacher/` | 仪表盘 |
| `/teacher/exams/` | 考试管理 |
| `/teacher/exams/create/` | 创建考试 |
| `/teacher/exams/<id>/edit/` | 编辑考试 |
| `/teacher/exams/<id>/qrcode/` | 考试二维码 |
| `/teacher/exams/<id>/audit/` | 审计日志 |
| `/teacher/questions/` | 题目管理 |
| `/teacher/scores/` | 成绩管理 |
| `/teacher/classes/` | 班级管理 |

## 运行测试

```bash
# 运行全部测试
pytest

# 运行指定模块测试
pytest tests/test_core/ -v
pytest tests/test_auth/ -v
pytest tests/test_examination/ -v

# 查看覆盖率
pytest --cov=core --cov=accounts --cov=examination
```

## 项目结构

```
dExam/
├── config/                  # Django 项目配置
│   ├── settings/            # 分环境配置（base/development/production/testing）
│   ├── urls.py              # 主路由
│   ├── celery.py            # Celery 配置
│   └── wsgi.py / asgi.py
├── core/                    # 核心公共模块
│   ├── exceptions.py        # 自定义业务异常
│   ├── constants.py         # 全局常量/枚举
│   ├── middleware.py         # 异常处理中间件
│   ├── responses.py         # 统一响应格式
│   ├── utils.py             # 通用工具函数
│   └── validators.py        # 数据验证器
├── accounts/                # 用户认证模块
│   ├── models.py            # User、LoginAttempt 模型
│   ├── services.py          # AuthService 认证服务
│   ├── views.py             # 登录/登出/改密视图
│   └── decorators.py        # 权限装饰器
├── examination/             # 考试核心模块
│   ├── models.py            # Exam、Question、ExamRecord 等模型
│   ├── services.py          # ExamService、ScoreService 等服务
│   ├── grader.py            # 自动判分引擎
│   ├── tasks.py             # Celery 自动交卷任务
│   ├── utils.py             # 二维码生成工具
│   ├── views.py             # 学生端视图
│   ├── teacher_views.py     # 教师端视图
│   └── templatetags/        # 模板过滤器
├── templates/               # HTML 模板
│   ├── base.html            # 基础模板
│   ├── accounts/            # 登录/改密模板
│   ├── exams/               # 学生端考试模板
│   └── teacher/             # 教师端模板
├── tests/                   # 测试代码（190 个测试用例）
│   ├── test_core/           # core 模块测试
│   ├── test_auth/           # 认证模块测试
│   ├── test_accounts/       # 账户模块测试
│   └── test_examination/    # 考试模块测试
├── manage.py
├── pyproject.toml
└── .env                     # 环境变量配置
```

## 数据库切换

默认使用 SQLite，适合开发和 100-200 人规模的考试。如需切换 MySQL：

1. 安装 MySQL 驱动：`uv pip install -e ".[mysql]"`
2. 修改 `.env`：`DB_ENGINE=mysql`
3. 配置数据库连接信息
4. 执行迁移：`python manage.py migrate`

## 架构设计

项目采用分层架构：

```
表现层 (Views) → 业务逻辑层 (Services) → 数据访问层 (Models) → 基础设施层 (DB/Redis/Celery)
```

- **Service Layer 模式**：所有业务逻辑在 Service 层实现，View 层仅处理 HTTP 请求/响应
- **统一响应格式**：使用 `core/responses.py` 的 `success_response()` 和 `error_response()`
- **自定义异常体系**：`core/exceptions.py` 定义业务异常，由中间件统一捕获
