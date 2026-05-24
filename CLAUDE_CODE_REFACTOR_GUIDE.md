# 在线考试系统 - Claude Code 重构开发指南

> **版本**: 2.0  
> **创建日期**: 2026-05-24  
> **目标读者**: Claude Code（AI 编程代理）  
> **用途**: 从零开始重构项目的完整指南  
> **设计原则**: 模块化、可渐进交付、每阶段产出可独立验证

---

## 目录

1. [项目概览](#一项目概览)
2. [重构目标与优化分析](#二重构目标与优化分析)
3. [项目目录结构](#三项目目录结构)
4. [模块功能描述](#四模块功能描述)
5. [API 接口规范](#五api-接口规范)
6. [数据模型规范](#六数据模型规范)
7. [Claude Code 开发流程](#七claude-code-开发流程)
8. [代码规范要求](#八代码规范要求)
9. [测试规范](#九测试规范)
10. [部署指南](#十部署指南)
11. [常见问题解决方案](#十一常见问题解决方案)
12. [风险与对策表](#十二风险与对策表)
13. [重构路线图](#十三重构路线图)

---

## 一、项目概览

### 1.1 项目简介

在线考试系统是基于 Django 框架开发的教育场景考试管理平台，支持教师出题组卷、发布考试，学生在线答题、自动评分与人工阅卷。系统采用 MySQL 数据库和 Redis 缓存，实现完整的考试流程管理。

### 1.2 技术栈

| 类别 | 技术 | 版本 |
|------|------|------|
| 后端框架 | Django | 6.0.3 |
| 数据库 | MySQL | 8.0 |
| 缓存 | Redis | 7.x |
| Excel 处理 | openpyxl | - |
| 二维码生成 | qrcode + Pillow | 8.2 |
| 前端 | Django Templates + Vanilla JS | - |
| 语言 | Python | 3.12 |
| 包管理工具 | uv | - |

### 1.3 核心功能域

| 功能域 | 子功能 |
|--------|--------|
| A. 用户认证与权限 | 统一登录、密码策略、角色控制、IP 限流 |
| B. 班级与学生管理 | 班级 CRUD、学生分配、Excel 批量导入 |
| C. 题目管理 | 题库 CRUD、Excel 批量导入、标签分类 |
| D. 考试管理 | 考试 CRUD、可见性控制、二维码/考试码、时间窗口 |
| E. 答题与判分 | 在线答题、草稿自动保存、自动判分、人工判分 |
| F. 成绩与统计 | 成绩查看、Excel 导出、难度/区分度分析 |

### 1.4 目录命名说明

原项目中 `exam/`（Django 项目配置）和 `exams/`（考试业务模块）命名容易混淆。重构后：

| 原名称 | 新名称 | 说明 |
|--------|--------|------|
| `exam/` | `config/` | Django 项目配置（settings、urls、wsgi 等） |
| `exams/` | `examination/` | 考试业务模块（考试、题目、判题、成绩等） |

---

## 二、重构目标与优化分析

### 2.1 现有代码质量问题

#### 2.1.1 架构层问题

| 问题 | 严重程度 | 描述 |
|------|----------|------|
| Service Layer 不彻底 | 高 | 部分业务逻辑仍在视图层（如 `upload_students`），未完全走 Service |
| 视图层过重 | 高 | `exam_submit` 等视图直接处理答案解析和判题，应下沉至 Service |
| 模块耦合度高 | 中 | 教师端所有功能集中在一个文件，应按模块拆分 |
| 缺少统一响应格式 | 中 | API 返回格式不统一，部分使用 JsonResponse，部分使用 Django messages |

#### 2.1.2 安全性问题

| 问题 | 严重程度 | 描述 |
|------|----------|------|
| CSRF 豁免 | 高 | `upload_students` 使用 `@csrf_exempt`，应改用 API Token 认证 |
| 文件路径硬编码 | 高 | Excel 上传使用 `/tmp/` 路径，Windows 环境不兼容且存在路径遍历风险 |
| 默认密码可预测 | 中 | 默认密码为学号后 6 位，应使用随机强密码 |
| Session 安全配置 | 中 | 需确认 `SESSION_COOKIE_SECURE`、`SESSION_COOKIE_HTTPONLY` 等配置 |

#### 2.1.3 性能问题

| 问题 | 严重程度 | 描述 |
|------|----------|------|
| N+1 查询 | 高 | `exam_list` 未使用 `prefetch_related` 预加载关联数据 |
| 循环过滤可见性 | 高 | 考试列表使用 Python 循环过滤可见性，应改为数据库 JOIN 查询 |
| 未使用 select_related | 中 | 多处外键查询未使用 `select_related` 优化 |

#### 2.1.4 代码质量问题

| 问题 | 严重程度 | 描述 |
|------|----------|------|
| 重复代码 | 中 | `student_login` 和 `teacher_login` 的登录失败处理逻辑完全重复 |
| 错误处理不统一 | 中 | 部分函数返回 `(data, error)` 元组，部分直接抛异常 |
| 缺少类型注解 | 低 | Service 层函数缺少类型注解 |
| 魔法数字 | 低 | 如 60 秒超时、5 次尝试等硬编码值应提取为常量 |

### 2.2 优化建议优先级

#### P0 - 必须修复（阻塞性）

1. **统一 Service Layer 架构**：将所有业务逻辑从视图层下沉到 Service 层
2. **修复 CSRF 豁免问题**：移除 `upload_students` 的 `@csrf_exempt`
3. **修复文件上传路径**：使用 Django `MEDIA_ROOT` 或 `tempfile` 模块
4. **优化考试列表查询**：消除 N+1 查询，使用 JOIN 过滤可见性

#### P1 - 高优先级（影响质量）

5. **统一 API 响应格式**：使用 `core/responses.py` 的统一响应函数
6. **消除重复代码**：抽取 `student_login` 和 `teacher_login` 的公共逻辑
7. **添加 select_related/prefetch_related**：优化所有外键查询
8. **完善状态机实现**：`ExamRecord` 状态流转使用显式状态机

#### P2 - 中优先级（增强可维护性）

9. **拆分教师端视图**：按模块拆分为多个视图文件
10. **添加类型注解**：为所有 Service 层函数添加类型注解
11. **提取魔法数字为常量**：在 `core/constants.py` 中统一定义
12. **完善错误处理**：统一使用 `(data, error)` 元组返回模式

---

## 三、项目目录结构

### 3.1 完整目录树

```
project/
├── config/                          # Django 项目配置（原 exam/）
│   ├── __init__.py
│   ├── settings.py                  # 设置入口（导入子模块）
│   ├── settings/
│   │   ├── __init__.py
│   │   ├── base.py                  # 基础配置（所有环境共用）
│   │   ├── development.py           # 开发环境配置
│   │   ├── production.py            # 生产环境配置
│   │   └── testing.py               # 测试环境配置
│   ├── urls.py                      # 主路由
│   ├── asgi.py
│   └── wsgi.py
│
├── accounts/                        # M1: 用户认证与授权模块
│   ├── __init__.py
│   ├── models.py                    # User、LoginAttempt 模型
│   ├── views.py                     # 登录/登出/改密/上传视图
│   ├── urls.py                      # 认证路由
│   ├── services.py                  # AuthService: 认证业务逻辑
│   ├── forms.py                     # 登录表单、改密表单
│   ├── decorators.py                # teacher_required/student_required 装饰器
│   ├── validators.py                # 密码复杂度验证器
│   ├── utils.py                     # Session/登录审计工具函数
│   ├── signals.py                   # 用户信号处理
│   ├── admin.py                     # Admin 用户管理配置
│   ├── apps.py                      # 应用配置
│   └── management/commands/
│       └── create_admin.py          # 创建管理员命令
│
├── examination/                     # M2-M9: 考试核心模块（原 exams/）
│   ├── __init__.py
│   ├── models.py                    # Exam/Question/ExamRecord/ClassInfo 模型
│   ├── views.py                     # 学生端考试视图
│   ├── teacher_views.py             # 教师端视图（待拆分）
│   ├── class_views.py               # 班级管理视图
│   ├── services.py                  # 考试业务服务层（新增）
│   ├── grading_service.py           # 判题服务（新增）
│   ├── urls.py                      # 学生端路由
│   ├── teacher_urls.py              # 教师端路由
│   ├── grader.py                    # 自动判题算法
│   ├── auto_submit.py               # Celery 自动交卷任务
│   ├── excel_importer.py            # Excel 题目导入器
│   ├── decorators.py                # 考试权限装饰器
│   ├── utils.py                     # 二维码工具函数
│   ├── apps.py
│   └── admin.py
│
├── core/                            # M12: 核心公共模块
│   ├── __init__.py
│   ├── exceptions.py                # 自定义业务异常
│   ├── constants.py                 # 全局常量/枚举
│   ├── middleware.py                # 异常处理/请求日志中间件
│   ├── responses.py                 # 统一响应格式
│   ├── utils.py                     # 通用工具函数
│   └── validators.py                # 通用数据验证器
│
├── templates/                       # 模板文件
│   ├── base.html                    # 基础模板
│   ├── accounts/
│   │   ├── student_login.html
│   │   ├── teacher_login.html
│   │   └── change_password.html
│   ├── exams/
│   │   ├── exam_list.html
│   │   ├── exam_detail.html
│   │   ├── exam_take.html
│   │   ├── exam_submitted.html
│   │   ├── exam_result.html
│   │   ├── exam_not_started.html
│   │   └── exam_over.html
│   ├── teacher/
│   │   └── (待补充教师端模板)
│   └── partials/
│       ├── _header.html
│       └── _messages.html
│
├── tests/                           # 测试文件
│   ├── __init__.py
│   ├── conftest.py                  # pytest 全局 fixture
│   ├── factories.py                 # 测试数据工厂
│   ├── test_auth/                   # accounts 模块测试
│   │   ├── test_views.py
│   │   ├── test_services.py
│   │   ├── test_models.py
│   │   └── test_decorators.py
│   ├── test_core/                   # core 模块测试
│   │   ├── test_utils.py
│   │   ├── test_responses.py
│   │   ├── test_middleware.py
│   │   ├── test_exceptions.py
│   │   └── test_constants.py
│   ├── test_accounts/
│   │   └── test_models.py
│   ├── test_examination/            # examination 模块测试
│   │   ├── test_views.py
│   │   ├── test_grader.py
│   │   ├── test_services.py
│   │   └── test_models.py
│   └── integration/                 # 集成测试
│       ├── __init__.py
│       └── test_login_flow.py
│
├── manage.py
└── requirements.txt
```

### 3.2 架构分层

```
┌────────────────────────────────────────────────────────────┐
│                    表现层 (Presentation)                    │
│  学生端视图  │  教师端视图  │  API 端点  │  Django Admin    │
└───────────────────────┬────────────────────────────────────┘
                        │
┌───────────────────────▼────────────────────────────────────┐
│                    业务逻辑层 (Service)                      │
│  AuthService  │  ExamService  │  GradingService  │  ...    │
└───────────────────────┬────────────────────────────────────┘
                        │
┌───────────────────────▼────────────────────────────────────┐
│                    数据访问层 (Models)                       │
│  User  │  Exam  │  Question  │  ExamRecord  │  ClassInfo   │
└───────────────────────┬────────────────────────────────────┘
                        │
┌───────────────────────▼────────────────────────────────────┐
│                    基础设施层 (Infrastructure)                │
│  MySQL  │  Redis  │  Celery  │  Django Cache                │
└────────────────────────────────────────────────────────────┘
```

### 3.3 模块依赖层级

| 层级 | 模块 | 说明 |
|------|------|------|
| Level 0 | core | 基础设施，无外部依赖 |
| Level 1 | accounts | 依赖 core，被所有业务模块依赖 |
| Level 2 | examination (core/questions/classes) | 依赖 core + accounts |
| Level 3 | examination (grader/grades/qrcode) | 依赖 L0-L2 |
| Level 4 | examination (autosubmit/anticheat/notifications) | 依赖 L0-L3 |

---

## 四、模块功能描述

### 4.1 accounts 模块 (M1: 用户认证与授权)

**职责**: 用户身份认证、会话管理、角色权限控制、密码策略管理、批量学生导入。

**核心类/函数**:

| 名称 | 类型 | 文件 | 说明 |
|------|------|------|------|
| `User` | Model | models.py | 自定义用户模型，支持 teacher/student 角色 |
| `LoginAttempt` | Model | models.py | 登录尝试记录，用于 IP 限流 |
| `AuthService` | Service | services.py | 认证业务逻辑统一入口 |
| `AuthService.authenticate_user()` | Method | services.py | 用户认证（支持学号/邮箱/用户名） |
| `AuthService.import_students_from_excel()` | Method | services.py | Excel 批量导入学生 |
| `student_login()` | View | views.py | 学生登录视图 |
| `teacher_login()` | View | views.py | 教师登录视图 |
| `teacher_required` | Decorator | decorators.py | 教师权限装饰器 |
| `student_required` | Decorator | decorators.py | 学生权限装饰器 |
| `PasswordComplexityValidator` | Validator | validators.py | 密码复杂度验证 |

### 4.2 examination 模块 (M2-M9: 考试核心)

**职责**: 考试管理、题目管理、班级管理、判题评分、成绩管理、自动交卷、二维码管理、防作弊。

#### 4.2.1 考试管理子模块 (M2)

| 名称 | 类型 | 文件 | 说明 |
|------|------|------|------|
| `Exam` | Model | models.py | 考试主模型 |
| `exam_list()` | View | views.py | 学生端考试列表 |
| `exam_detail()` | View | views.py | 考试详情 |
| `exam_take()` | View | views.py | 答题页面 |
| `exam_submit()` | View | views.py | 提交答卷 |
| `exam_result()` | View | views.py | 查看成绩 |

#### 4.2.2 题目管理子模块 (M3)

| 名称 | 类型 | 文件 | 说明 |
|------|------|------|------|
| `Question` | Model | models.py | 题目模型（choice/blank） |
| `ExamQuestion` | Model | models.py | 考试-题目关联模型 |
| `import_questions_from_excel()` | Function | excel_importer.py | Excel 导入题目 |

#### 4.2.3 班级管理子模块 (M4)

| 名称 | 类型 | 文件 | 说明 |
|------|------|------|------|
| `ClassInfo` | Model | models.py | 班级模型 |
| `StudentClassRelation` | Model | models.py | 学生-班级关系模型 |

#### 4.2.4 判题评分子模块 (M5)

| 名称 | 类型 | 文件 | 说明 |
|------|------|------|------|
| `grade_exam()` | Function | grader.py | 考试总分计算 |
| `grade_choice_question()` | Function | grader.py | 选择题判分 |
| `grade_blank_question()` | Function | grader.py | 填空题判分 |

### 4.3 core 模块 (M12: 核心公共)

**职责**: 通用工具、自定义异常、常量定义、中间件、统一响应格式。

| 名称 | 类型 | 文件 | 说明 |
|------|------|------|------|
| `ExamNotStartedError` | Exception | exceptions.py | 考试未开始异常 |
| `ExamFinishedError` | Exception | exceptions.py | 考试已结束异常 |
| `PermissionDeniedError` | Exception | exceptions.py | 权限拒绝异常 |
| `ExceptionHandlerMiddleware` | Middleware | middleware.py | 全局异常处理 |
| `success_response()` | Function | responses.py | 成功响应格式化 |
| `error_response()` | Function | responses.py | 错误响应格式化 |

---

## 五、API 接口规范

### 5.1 统一响应格式

所有 API 接口必须使用 `core/responses.py` 提供的统一格式：

```python
# 成功响应
{
    "code": 200,
    "message": "操作成功",
    "data": { ... }
}

# 错误响应
{
    "code": 400,
    "message": "错误描述",
    "data": null
}
```

### 5.2 认证模块 API

| 方法 | 路径 | 功能 | 权限 | 请求体 | 响应 |
|------|------|------|------|--------|------|
| GET | `/accounts/login/` | 学生登录页 | 公开 | - | HTML |
| POST | `/accounts/login/` | 学生登录 | 公开 | `username`, `password` | 重定向 |
| GET | `/accounts/teacher/login/` | 教师登录页 | 公开 | - | HTML |
| POST | `/accounts/teacher/login/` | 教师登录 | 公开 | `username`, `password` | 重定向 |
| GET/POST | `/accounts/logout/` | 登出 | 已登录 | - | 重定向 |
| GET | `/accounts/api/session-id/` | 生成 QR Session ID | 公开 | - | `{session_id, login_url, expire_time}` |
| POST | `/accounts/api/session-id/verify/` | 验证 QR Session | 公开 | `session_id` | `{success}` |
| GET/POST | `/accounts/change-password/` | 修改密码 | 已登录 | `old_password`, `new_password` | 重定向 |
| POST | `/accounts/upload-students/` | 批量上传学生 | Superuser | `file` (multipart) | `{success, success_count, errors}` |

### 5.3 考试模块 API

| 方法 | 路径 | 功能 | 权限 | 请求体 | 响应 |
|------|------|------|------|--------|------|
| GET | `/exams/` | 考试列表 | 学生 | - | HTML |
| GET | `/exams/{exam_id}/` | 考试详情 | 学生 | - | HTML |
| GET | `/exams/{exam_id}/take/` | 答题页面 | 学生+授权 | - | HTML |
| POST | `/exams/{exam_id}/submit/` | 提交答卷 | 学生+授权 | `answers` (JSON) | JSON |
| POST | `/exams/{exam_id}/save-answer/` | 保存草稿 | 学生+授权 | `answers` (JSON) | JSON |
| GET | `/exams/{exam_id}/result/` | 查看成绩 | 学生+授权 | - | HTML |
| POST | `/exams/{exam_id}/enter/` | 进入考试验证 | 学生 | `qr_code` (可选) | JSON |

### 5.4 教师端 API

| 方法 | 路径 | 功能 | 权限 | 请求体 | 响应 |
|------|------|------|------|--------|------|
| GET | `/teacher/` | 仪表盘 | 教师 | - | HTML |
| GET | `/teacher/exams/` | 考试列表 | 教师 | - | HTML |
| GET/POST | `/teacher/exams/create/` | 创建考试 | 教师 | 表单 | 重定向 |
| GET/POST | `/teacher/exams/{id}/edit/` | 编辑考试 | 教师(创建者) | 表单 | 重定向 |
| POST | `/teacher/exams/{id}/delete/` | 删除考试 | 教师(创建者) | - | 重定向 |
| GET | `/teacher/exams/{id}/qrcode/` | 生成二维码 | 教师(创建者) | - | HTML |
| GET | `/teacher/questions/` | 题目管理 | 教师 | - | HTML |
| POST | `/teacher/api/questions/import/` | 导入题目 | 教师 | Excel 文件 | JSON |
| GET | `/teacher/scores/` | 成绩管理 | 教师 | - | HTML |
| GET | `/teacher/classes/` | 班级管理 | 教师 | - | HTML |

### 5.5 HTTP 状态码规范

| 状态码 | 含义 | 使用场景 |
|--------|------|----------|
| 200 | 成功 | 请求正常处理 |
| 201 | 已创建 | 成功创建资源 |
| 400 | 请求错误 | 参数验证失败 |
| 401 | 未授权 | 未登录或认证失败 |
| 403 | 禁止访问 | 权限不足 |
| 404 | 未找到 | 资源不存在 |
| 429 | 请求过多 | 触发限流 |
| 500 | 服务器错误 | 内部异常 |

---

## 六、数据模型规范

### 6.1 核心模型关系

```
User(1) ────< ClassInfo(N) ────< Exam(N)
  │               │                   │
  │               │                   ├───< ExamQuestion(N) ───> Question(N)
  │               │
  │               └───< StudentClassRelation(N) ───> User(student)
  │
  └───< ExamRecord(N) ────> Exam(N)
```

### 6.2 User 模型 (accounts_user)

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | AutoField | PK | 主键 |
| username | CharField(150) | UNIQUE | 用户名 |
| password | CharField | - | 加密密码 |
| role | CharField(10) | teacher/student | 角色 |
| student_id | CharField(20) | UNIQUE, nullable | 学号 |
| first_name | CharField(150) | - | 姓名 |
| email | EmailField | - | 邮箱 |
| must_change_password | BooleanField | default=False | 首次登录强制改密 |
| last_login_ip | GenericIPAddressField | nullable | 最后登录 IP |
| is_active | BooleanField | default=True | 软删除标记 |

### 6.3 Exam 模型 (examination_exam)

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | AutoField | PK | 主键 |
| title | CharField(200) | - | 考试名称 |
| description | TextField | - | 考试描述 |
| exam_code | CharField(50) | UNIQUE | 考试码 |
| created_by | FK(User) | - | 创建者 |
| visibility | CharField(20) | public/class_specific | 可见性 |
| start_time | DateTimeField | nullable | 开始时间 |
| end_time | DateTimeField | nullable | 结束时间 |
| duration | IntegerField | default=60 | 时长(分钟) |
| total_score | IntegerField | default=100 | 满分 |
| require_qr | BooleanField | default=False | 需扫码 |
| submission_method | CharField(10) | manual/auto | 提交方式 |
| shuffle_questions | BooleanField | default=False | 题目乱序 |
| shuffle_options | BooleanField | default=False | 选项乱序 |
| is_active | BooleanField | default=True | 启用标记 |
| allowed_classes | M2M(ClassInfo) | - | 可见班级 |

### 6.4 Question 模型 (examination_question)

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | AutoField | PK | 主键 |
| exam | FK(Exam) | nullable | 所属考试 |
| question_type | CharField(10) | choice/blank | 题型 |
| content | TextField | - | 题干 |
| options | TextField | JSON 字符串 | 选项 |
| answer | TextField | - | 正确答案 |
| score | IntegerField | default=10 | 分值 |
| explanation | TextField | - | 解析 |
| difficulty | CharField(10) | easy/medium/hard | 难度 |
| order | IntegerField | default=0 | 排序 |

### 6.5 ExamRecord 模型 (examination_examrecord)

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | AutoField | PK | 主键 |
| exam | FK(Exam) | - | 考试 |
| student | FK(User) | - | 学生 |
| answers | TextField | JSON | 答案 |
| score | IntegerField | default=0 | 得分 |
| total_score | IntegerField | - | 总分 |
| grading_details | TextField | JSON | 判题详情 |
| is_graded | BooleanField | default=False | 已判题 |
| start_time | DateTimeField | auto_now_add | 开始时间 |
| submit_time | DateTimeField | nullable | 提交时间 |
| submission_method | CharField(10) | manual/auto | 提交方式 |
| ip_address | CharField(45) | - | 答题 IP |
| status | CharField(20) | draft/submitted/auto_graded/manual_grading/manual_graded/reviewed | 状态机 |

### 6.6 ClassInfo 模型 (examination_classinfo)

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | AutoField | PK | 主键 |
| name | CharField | - | 班级名称 |
| description | TextField | - | 描述 |
| teacher | FK(User) | - | 班主任 |
| created_at | DateTimeField | auto_now_add | 创建时间 |
| updated_at | DateTimeField | auto_now | 更新时间 |
| is_active | BooleanField | default=True | 启用标记 |

---

## 七、Claude Code 开发流程

### 7.1 Claude Code 工作流

```
1. 理解需求 → 阅读本指南相关章节
2. 定位代码 → 根据模块归属找到对应文件
3. 编写测试 → 先在 tests/ 对应目录编写测试用例
4. 实现功能 → 在 Service 层实现业务逻辑，View 层仅做请求处理和响应
5. 运行测试 → 执行 pytest 验证
6. 子模块文档攥写 → 填写模块文档
7. 检查质量 → 运行 flake8/black/isort 检查
8. 提交变更 → 使用 Conventional Commits 规范
```

### 7.2 模块开发顺序

严格按照依赖层级从低到高开发：

```
Level 0: core 模块（基础设施）
    ↓
Level 1: accounts 模块（认证授权）
    ↓
Level 2: examination core/questions/classes（考试/题目/班级管理）
    ↓
Level 3: examination grader/grades/qrcode（判题/成绩/二维码）
    ↓
Level 4: examination autosubmit/anticheat/notifications（自动交卷/防作弊/通知）
```

### 7.3 开发命令参考

```bash
# 启动开发服务器
python manage.py runserver

# 运行测试
pytest

# 运行指定模块测试
pytest tests/test_auth/ -v

# 代码格式化
black .
isort .

# 代码检查
flake8 .

# 数据库迁移
python manage.py makemigrations
python manage.py migrate

# 创建管理员
python manage.py create_admin

# 检查安全问题
python manage.py check --deploy
```

### 7.4 新功能开发 Checklist

- [ ] 在 `core/constants.py` 中定义相关常量（如有）
- [ ] 在对应模块的 `models.py` 中定义数据模型（如有）
- [ ] 在 `services.py` 中实现业务逻辑
- [ ] 在 `views.py` 中编写视图（仅处理请求/响应）
- [ ] 在 `urls.py` 中注册路由
- [ ] 在 `tests/` 中编写单元测试
- [ ] 运行 `pytest` 确保通过
- [ ] 运行 `flake8` 和 `black` 确保代码质量

### 7.5 Claude Code 操作规范

1. **每次只处理一个任务**：完成单个模块/功能的代码编写 + 测试 + 验证后再进入下一个
2. **先读后改**：修改任何文件前，先完整阅读该文件及其相关依赖文件
3. **小步提交**：每次修改保持最小变更范围，便于验证和回滚
4. **优先修复 P0**：按优化优先级顺序处理问题
5. **保持向后兼容**：重构时确保现有功能不受影响

---

## 八、代码规范要求

### 8.1 Python 代码规范

| 规则 | 要求 | 工具 |
|------|------|------|
| 代码风格 | PEP 8 | flake8 |
| 格式化 | Black (line-length=120) | black |
| 导入排序 | isort (profile=black) | isort |
| 类型注解 | Service 层函数必须有 | mypy (可选) |
| 命名规范 | 类 PascalCase，函数/变量 snake_case | - |
| 字符串 | 优先使用 f-string | - |
| 最大行长度 | 120 字符 | black |

### 8.2 架构规范

#### 8.2.1 Service Layer 模式

**规则**: 所有业务逻辑必须在 Service 层实现，View 层仅处理 HTTP 请求/响应。

```python
# 正确做法
class ExamService:
    @staticmethod
    def submit_exam(exam_id: int, student: User, answers: dict):
        data, error = ExamGrader.grade(exam_id, answers)
        if error:
            return None, error
        record = ExamRecord.objects.create(...)
        return record, None

# View 层仅调用 Service
def exam_submit(request, exam_id):
    record, error = ExamService.submit_exam(exam_id, request.user, answers)
    if error:
        return error_response(400, error)
    return success_response(data={'score': record.score})
```

#### 8.2.2 错误处理规范

**规则**: Service 层方法必须返回 `(data, error)` 元组，禁止裸抛异常给 View 层。

```python
# 正确做法
def do_something():
    try:
        result = some_operation()
        return result, None
    except SpecificError as e:
        return None, str(e)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return None, "操作失败，请稍后重试"
```

#### 8.2.3 数据库查询规范

**规则**: 
- 所有外键查询必须使用 `select_related()`
- 所有反向关联查询必须使用 `prefetch_related()`
- 禁止在循环中执行数据库查询

```python
# 正确：预加载关联数据
exams = Exam.objects.filter(
    is_active=True
).select_related('created_by').prefetch_related(
    'allowed_classes',
    'questions'
).order_by('-created_at')

# 错误：N+1 查询
exams = Exam.objects.filter(is_active=True)
for exam in exams:
    teacher = exam.created_by  # 每次循环一条查询
```

### 8.3 前端规范

| 规则 | 要求 |
|------|------|
| 模板引擎 | Django Templates |
| CSS | 内联 style 标签 + 自定义 CSS |
| JavaScript | Vanilla JS，避免 jQuery |
| 表单 | 使用 Django forms 渲染，前端验证 + 后端验证 |
| 安全 | 模板自动转义，API 返回做 escape 处理 |

### 8.4 Git 提交规范

遵循 Conventional Commits 规范：

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

| Type | 说明 | 示例 |
|------|------|------|
| feat | 新功能 | feat(examination): 添加考试码模式 |
| fix | Bug 修复 | fix(accounts): 修复 IP 限流逻辑 |
| refactor | 重构 | refactor(examination): 抽取 Service 层 |
| test | 测试相关 | test(grader): 添加选择题判分测试 |
| docs | 文档 | docs: 更新开发指南 |
| chore | 构建/工具 | chore: 添加 pre-commit hooks |

---

## 九、测试规范

### 9.1 测试框架

| 工具 | 用途 |
|------|------|
| pytest | 测试运行器 |
| pytest-django | Django 测试支持 |
| pytest-cov | 测试覆盖率 |
| factory-boy | 测试数据工厂 |

### 9.2 测试目录结构

```
tests/
├── conftest.py              # 全局 fixture
├── factories.py             # 测试数据工厂
├── test_auth/               # accounts 模块测试
│   ├── test_views.py
│   ├── test_services.py
│   ├── test_models.py
│   └── test_decorators.py
├── test_core/               # core 模块测试
│   ├── test_utils.py
│   ├── test_responses.py
│   ├── test_middleware.py
│   ├── test_exceptions.py
│   └── test_constants.py
├── test_examination/        # examination 模块测试
│   ├── test_views.py        # (待创建)
│   ├── test_grader.py       # (待创建)
│   ├── test_services.py     # (待创建)
│   └── test_models.py       # (待创建)
└── integration/             # 集成测试
    ├── test_login_flow.py
    ├── test_exam_flow.py    # (待创建)
    └── test_auto_submit.py  # (待创建)
```

### 9.3 测试编写规范

```python
import pytest
from pytest_django.asserts import assertContains, assertNotContains
from tests.factories import ExamFactory, QuestionFactory

@pytest.mark.django_db
def test_exam_list_returns_active_exams(client, django_user_model):
    """考试列表仅返回启用状态的考试"""
    # Given: 已登录的学生用户
    student = django_user_model.objects.create_user(
        username='test', password='Test@123', role='student'
    )
    client.login(username='test', password='Test@123')
    
    # And: 已创建一个启用考试和一个禁用考试
    active_exam = ExamFactory.create(is_active=True)
    inactive_exam = ExamFactory.create(is_active=False)
    
    # When: 请求考试列表
    response = client.get('/exams/')
    
    # Then: 仅包含启用的考试
    assertContains(response, active_exam.title)
    assertNotContains(response, inactive_exam.title)
```

### 9.4 测试覆盖率目标

| 模块 | 覆盖率目标 |
|------|-----------|
| core | >= 90% |
| accounts/services | >= 85% |
| examination/grader | >= 90% |
| examination/services | >= 80% |
| accounts/views | >= 70% |
| examination/views | >= 70% |

---

## 十、部署指南

### 10.1 开发环境

```bash
# 1. 克隆项目
git clone <repo_url>
cd project

# 2. 创建虚拟环境
python -m venv .venv
.venv\Scripts\activate  # Windows

# 3. 安装依赖
pip install -r requirements.txt

# 4. 配置环境变量
cp .env.example .env
# 编辑 .env 填入数据库等配置

# 5. 数据库迁移
python manage.py migrate

# 6. 创建管理员
python manage.py create_admin

# 7. 启动
python manage.py runserver
```

### 10.2 生产环境部署

```
┌────────────────────────────────────────────────────────────┐
│                        Nginx (反向代理)                       │
├────────────────────────────────────────────────────────────┤
│  Gunicorn (Django WSGI)    │  Celery Worker (异步任务)       │
├────────────────────────────┼────────────────────────────────┤
│  Redis (缓存 + Session)    │  MySQL (数据存储)               │
└────────────────────────────────────────────────────────────┘
```

**关键配置项**:

```python
# config/settings/production.py
DEBUG = False
ALLOWED_HOSTS = ['your-domain.com']

SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Strict'
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_SAMESITE = 'Strict'

SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
```

### 10.3 环境变量清单

| 变量名 | 说明 | 示例值 |
|--------|------|--------|
| `DATABASE_URL` | 数据库连接串 | `mysql://user:pass@host:3306/exam_system` |
| `REDIS_URL` | Redis 连接串 | `redis://:password@host:6379/0` |
| `SECRET_KEY` | Django 密钥 | (随机生成) |
| `DEBUG` | 调试模式 | `False` |
| `ALLOWED_HOSTS` | 允许的域名 | `exam.example.com` |
| `EMAIL_HOST` | SMTP 服务器 | `smtp.example.com` |
| `CELERY_BROKER_URL` | Celery 代理 | `redis://:password@host:6379/1` |

---

## 十一、常见问题解决方案

### 11.1 认证与权限

#### Q1: 如何添加新的用户角色？

1. 在 `accounts/models.py` 的 `User` 模型中添加新的角色常量
2. 在 `core/constants.py` 中定义角色枚举
3. 在 `accounts/decorators.py` 中添加对应的装饰器
4. 编写测试验证权限隔离

#### Q2: 如何处理 IP 被锁定？

IP 锁定由 `accounts/utils.py` 中的 `is_ip_locked()` 函数控制：
- 锁定阈值：`AuthService.MAX_LOGIN_ATTEMPTS = 5`
- 锁定时长：`AuthService.LOCKOUT_MINUTES = 30`
- 解锁方式：等待 30 分钟或手动清除 Redis 中的锁定记录

```bash
# 手动解锁（Redis CLI）
redis-cli -h HOST -a PASSWORD DEL "login_attempts:{ip_address}"
```

#### Q3: 首次登录强制改密不生效？

检查 `accounts/middleware.py` 中的 `PasswordChangeMiddleware` 是否正确配置：
1. 确认 `MIDDLEWARE` 列表中包含该中间件
2. 确认用户的 `must_change_password` 字段为 `True`
3. 确认中间件未排除改密页面本身（避免无限重定向）

### 11.2 考试相关

#### Q4: 考试列表看不到考试？

排查步骤：
1. 确认考试 `is_active=True`
2. 确认考试时间在有效范围内
3. 如果 `visibility=class_specific`，确认学生所在班级在 `allowed_classes` 中
4. 检查 `Exam.is_visible_to_student()` 方法逻辑

#### Q5: 提交答卷失败？

常见原因：
1. **重复提交**: 检查 `ExamRecord.is_submitted` 或 `status` 是否已非 draft
2. **考试超时**: 检查 `timezone.now() > exam.end_time`
3. **并发冲突**: `select_for_update` 锁超时，检查数据库锁等待配置

#### Q6: 自动交卷不触发？

排查步骤：
1. 确认 Celery Worker 已启动：`celery -A config worker -l info`
2. 确认 Redis 连接正常
3. 检查 `examination/auto_submit.py` 中 Celery 任务是否正确注册
4. 查看 Celery 日志确认任务是否被调度

### 11.3 数据库相关

#### Q7: 数据库迁移失败？

```bash
# 1. 检查迁移状态
python manage.py showmigrations

# 2. 如果遇到冲突
python manage.py migrate --fake <app_name> <migration_name>

# 3. 重新生成迁移
python manage.py makemigrations --merge
```

#### Q8: 查询性能慢？

优化方案：
1. 使用 Django Debug Toolbar 分析 SQL 查询
2. 添加 `select_related` / `prefetch_related`
3. 为常用查询字段添加数据库索引
4. 使用 `EXPLAIN` 分析查询计划

### 11.4 部署相关

#### Q9: 静态文件 404？

生产环境静态文件处理：
```bash
# 1. 收集静态文件
python manage.py collectstatic

# 2. 配置 Nginx 指向 STATIC_ROOT
# 或使用 WhiteNoise
pip install whitenoise
# settings.py 中添加:
MIDDLEWARE.insert(1, 'whitenoise.middleware.WhiteNoiseMiddleware')
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
```

#### Q10: Celery 任务不执行？

排查步骤：
1. 确认 Worker 进程运行：`ps aux | grep celery`
2. 确认 Broker (Redis) 可达：`redis-cli ping`
3. 检查任务注册：`celery -A config inspect registered`
4. 查看 Worker 日志中的错误信息

---

## 十二、风险与对策表

### 12.1 Top 5 最容易出 Bug 的地方

| 排名 | 风险点 | 场景 | 根因 | 解决思路 |
|------|--------|------|------|----------|
| #1 | **自动判分与人工判分混合状态竞争** | 学生提交含主观题答卷 → 客观题自动判分 → 教师正在人工判分时学生刷新看分数 | 状态机不清晰 | (1) `auto_graded` 仅表示客观题完成；(2) `manual_grading` 状态时显示"阅卷中"；(3) 非终态不展示总分 |
| #2 | **并发提交导致重复判分** | 学生网络不稳定，多次点击交卷 | 前端未完全阻止 + 后端竞态 | (1) 前端 disabled + loading；(2) Redis 分布式锁 `SET NX`，TTL=10s；(3) 检查 `status != draft` |
| #3 | **考试时间边界条件** | end_time 到达瞬间学生提交 vs 系统自动交卷 | 时间判断入口不统一 | (1) 统一为 `exam.is_submission_allowed()`；(2) 自动交卷前检查 status；(3) 30 秒宽限期 |
| #4 | **题目/选项乱序映射错乱** | 学生答案用乱序索引提交，后端用原始 ID 判分 | 映射关系不一致 | (1) 前端使用原始 `question_id` 提交；(2) 乱序仅改变渲染顺序 |
| #5 | **人工判分覆盖自动判分数据不一致** | 教师手动修改分数后总分不一致 | `score` 和 `grading_details` 不同步 | (1) `score` 始终由 `grading_details` 汇总计算；(2) 重写 `save()` 校验一致性 |

### 12.2 通用风险对策

| 风险类别 | 对策 |
|----------|------|
| SQL 注入 | ORM 全覆盖 + Code Review 检查所有 `raw()` / `extra()` 调用 |
| XSS | Django 模板自动转义 + JSON API 返回做 escape + CSP 头 |
| Session 劫持 | HTTPS 强制 + SESSION_COOKIE_SECURE + cycle_key() 登录后刷新 |
| 性能退化 | 每个变更附带 Django Debug Toolbar 截图证明查询数未增加 |
| 数据丢失 | 每日自动备份 MySQL + Redis RDB 持久化 |

---

## 十三、重构路线图

### 阶段一：基础设施加固（P0）

| 序号 | 任务 | 涉及文件 | 验收标准 |
|------|------|---------|---------|
| 1.1 | 重命名项目目录 | `exam/` → `config/`, `exams/` → `examination/` | 项目正常运行，所有导入路径正确 |
| 1.2 | 数据库迁移标准化 | `accounts/migrations/`, `examination/migrations/` | `migrate` 零错误 |
| 1.3 | 补全 core 异常类 | `core/exceptions.py` | 所有业务异常可被 middleware 捕获 |
| 1.4 | 全局异常处理中间件 | `core/middleware.py` | 未捕获异常返回结构化 JSON |
| 1.5 | 统一响应格式 | `core/responses.py` | 所有 API 返回格式统一 |
| 1.6 | 配置测试框架 | `pytest.ini`, `tests/conftest.py` | `pytest` 可执行 |

### 阶段二：核心业务重构（P0）

| 序号 | 任务 | 涉及文件 | 验收标准 |
|------|------|---------|---------|
| 2.1 | 统一登录入口 | `accounts/views.py` | 学号+密码登录 → 跳转考试列表 |
| 2.2 | 首次改密中间件 | `accounts/middleware.py` | 首次登录重定向到改密页 |
| 2.3 | 考试查询优化 | `examination/views.py` | JOIN 查询完成可见性过滤 |
| 2.4 | Service 层分离 | `examination/services.py` | 业务逻辑从视图下沉 |
| 2.5 | 判题增强 | `examination/grader.py` | 填空题支持多答案匹配 |
| 2.6 | 修复 CSRF 豁免 | `accounts/views.py` | 移除 `upload_students` 的 `@csrf_exempt` |
| 2.7 | 修复文件上传路径 | `accounts/views.py` | 使用 `tempfile` 替代 `/tmp/` |

### 阶段三：代码质量提升（P1）

| 序号 | 任务 | 涉及文件 | 验收标准 |
|------|------|---------|---------|
| 3.1 | 消除重复代码 | `accounts/views.py` | 抽取公共登录处理逻辑 |
| 3.2 | 添加 select_related | 全局 views | 所有外键查询优化 |
| 3.3 | 完善状态机 | `examination/models.py` | ExamRecord 状态流转使用显式状态机 |
| 3.4 | 添加类型注解 | services.py | 所有 Service 函数有类型注解 |
| 3.5 | 提取魔法数字 | `core/constants.py` | 所有硬编码值提取为常量 |

### 阶段四：功能扩展（P1-P2）

| 序号 | 任务 | 优先级 |
|------|------|--------|
| 4.1 | 成绩 Excel 导出 | P1 |
| 4.2 | 切屏检测 | P1 |
| 4.3 | 操作审计日志 | P1 |
| 4.4 | 题目乱序/选项乱序 | P1 |
| 4.5 | 消息通知 | P1 |
| 4.6 | 题目标签系统 | P2 |
| 4.7 | 成绩趋势分析 | P2 |

---

## 附录：目录重命名对照表

| 原路径 | 新路径 | 说明 |
|--------|--------|------|
| `exam/settings.py` | `config/settings.py` | 项目设置入口 |
| `exam/settings/base.py` | `config/settings/base.py` | 基础配置 |
| `exam/settings/development.py` | `config/settings/development.py` | 开发配置 |
| `exam/settings/production.py` | `config/settings/production.py` | 生产配置 |
| `exam/settings/testing.py` | `config/settings/testing.py` | 测试配置 |
| `exam/urls.py` | `config/urls.py` | 主路由 |
| `exam/wsgi.py` | `config/wsgi.py` | WSGI 入口 |
| `exam/asgi.py` | `config/asgi.py` | ASGI 入口 |
| `exams/models.py` | `examination/models.py` | 考试数据模型 |
| `exams/views.py` | `examination/views.py` | 学生端视图 |
| `exams/teacher_views.py` | `examination/teacher_views.py` | 教师端视图 |
| `exams/grader.py` | `examination/grader.py` | 判题算法 |
| `exams/auto_submit.py` | `examination/auto_submit.py` | 自动交卷 |
| `exams/excel_importer.py` | `examination/excel_importer.py` | Excel 导入 |
| `exams/urls.py` | `examination/urls.py` | 学生端路由 |
| `exams/teacher_urls.py` | `examination/teacher_urls.py` | 教师端路由 |

**注意**: 重命名后需要更新以下引用：
- `manage.py` 中的 `DJANGO_SETTINGS_MODULE`
- `config/settings/base.py` 中的 `INSTALLED_APPS`
- 所有 `import exams` 改为 `import examination`
- 模板中 `{% url 'exams:xxx' %}` 改为 `{% url 'examination:xxx' %}`
- 测试中的模块导入路径

---

*文档版本: 2.0*  
*创建日期: 2026-05-24*  
*基于文档: MODULE_ARCHITECTURE.md, project_blueprint.md, project_summary.md*  
*更新说明: 修正目录命名 (exam→config, exams→examination)，优化为 Claude Code 重构专用指南*
