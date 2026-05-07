# Django 在线考试系统 - 详细项目文档

## 一、项目概述

这是一个基于 **Django 4.2** 和 **MySQL** 构建的完整在线考试管理系统，支持：
- **多班级管理**：教师可创建多个班级，学生可同时属于多个班级
- **题库建设**：独立于考试的题目库，支持 Excel 批量导入选择题/填空题
- **在线答题**：支持实时保存草稿、自动/手动提交、防作弊机制
- **智能判题**：选择题精准匹配，填空题宽容判分（包含匹配得 50%）
- **兜底策略**：考试结束后自动为未交卷学生判分

## 二、技术架构

### 2.1 核心依赖
```python
Django==6.0.3
MySQL>=8.0
Redis（用于 session 存储和缓存）
openpyxl（Excel 文件解析）```

### 2.2 数据库设计

#### 主要模型层级结构：
1. **accounts.User** - 自定义用户表（教师/学生角色）
2. **exams.ClassInfo** - 班级信息表
3. **exams.StudentClassRelation** - 学生 - 班级关联（多对多）
4. **exams.Exam** - 考试主表（时间控制、可见性设置）
5. **exams.Question** - 题目库表（独立于考试存在）
6. **exams.ExamQuestion** - 考试 - 题目关联表
7. **exams.ExamRecord** - 学生答卷记录（草稿 + 最终成绩）

## 三、核心功能模块详解

### 3.1 Excel 题库导入系统

#### 文件规范
| 列 A | 列 B | 列 C | 列 D | 列 E | 列 F | 列 G |
|------|------|------|------|------|------|------|
| 题型 | 题干 | 选项 A | 选项 B | 选项 C | 选项 D | 答案 |

**格式示例**：
- `选择题\u007c地球自转周期？\u007c24 小时\u007c365 天\u007c100 年\u007c1 年\u007cc`
- `填空题\u007c中国最大城市\u007c\u007c\u007c\u007c\u007c\u007c上海`

#### 导入流程（`exams/excel_importer.py`）
1. **解析阶段** (`parse_excel`)
   - 使用 `openpyxl` 读取数据
   - 跳过表头行，逐行解析
   - 自动规范化答案格式（大写、去除分隔符）
2. **验证阶段** (`validate_questions`)
   - Django Model 级校验（`full_clean()`）
3. **导入执行** (`import_questions`)
   - 事务性写入数据库
   - 返回统计报告（成功/失败数）

#### 容错机制：
- 空行自动跳过
- 列数不足抛出异常
- 答案格式错误自动修正

### 3.2 班级与权限系统

#### 多对多关系设计：
```python
# 学生可以同时加入多个班级
student <-> class_info (StudentClassRelation)
```

**可见性控制逻辑** (`Exam.is_visible_to_student`):
- **全局公开** (`public`)：所有学生可访问
- **指定班级** (`class_specific`)：检查学生是否属于 `allowed_classes`

### 3.3 判题算法引擎

#### 选择题判分（`grade_choice_question`）
```python
# 完全匹配得满分，否则 0 分
# 支持多答案格式："AB", "A,B", "A,C,D"
def grade_choice(student_ans, correct_ans):
    return score if student_ans == correct_ans else 0
```

#### 填空题判分（`grade_blank_question`）
```python
# 两阶段判分策略：
# 1. 完全匹配 → 满分
# 2. 正确答案在学生答案中作为子串存在 → 50% 分数（向上取整）
def grade_blank(student_ans, correct_ans):
    if student_ans == correct_ans: return score
    elif correct_ans in student_ans: return ceil(score * 0.5)
    else: return 0
```

#### 整卷判阅流程：
1. 遍历 `ExamQuestion` 关联表获取题目顺序
2. 按题型调用对应判分函数
3. 汇总总分并记录每题详情（用于结果展示）

### 3.4 防作弊机制

#### 提交保护：
```python
# 使用 select_for_update() + 事务防止重复提交
with transaction.atomic():
    record = ExamRecord.objects.select_for_update().get(...)
    if record.is_submitted: return "已交卷"
```

#### 时间窗口校验：
- 答题前检查 `start_time <= now <= end_time`
- API 提交时再次验证，防止跨设备作弊

### 3.5 兜底自动判分系统

文件：`exams/auto_submit.py`

**触发条件**：考试结束时间到达且存在未交卷记录

**执行逻辑**：
1. 查询所有 `end_time < now` 的考试
2. 对每个考试的未提交记录 `ExamRecord.is_submitted=False` 进行批处理
3. 使用最后一次保存的草稿 (`answer_sheet`) 自动判阅
4. 标记为 `submission_method='auto'`
5. 并发安全：加锁防止同一记录的重复处理

## 四、关键 API 接口文档

### 4.1 答题相关
| 端点 | 方法 | 功能 |
|------|------|------|
| `/exams/{exam_id}/take/` | GET | 渲染答题页，检查权限和时间 |
| `/exams/{exam_id}/save-answer/` | POST | 保存草稿（可多次调用） |
| `/exams/{exam_id}/submit/` | POST | 提交并判分（防重复提交保护） |

### 4.2 题库管理
| 端点 | 方法 | 功能 |
|------|------|------|
| `/exams/excel/upload/` | GET | Excel 上传预览页 |
| `/exams/excel/parse/` | POST | 解析文件，返回预览数据 |
| `/exams/excel/import/` | POST | 执行导入（需携带选中的行号） |

## 五、数据模型详解

### 5.1 ExamRecord 核心字段：
```python
class ExamRecord(models.Model):
    student = ForeignKey(User)
    exam = ForeignKey(Exam)
    answer_sheet = JSONField(default=dict)  # {"q1": "a", "q2": "b"}
    final_score = DecimalField(max_digits=5, decimal_places=2)
    is_submitted = BooleanField()
    submitted_at = DateTimeField(null=True)
    submission_method = CharField(choices=[('manual', '手动'), ('auto', '自动')])
    grading_details = JSONField()  # 判题详情用于结果展示
```

### 5.2 ExamQuestion 关联表：
```python
# 解耦考试和题目，支持题目复用
Exam(
  ExamQuestion,      # order=1, score=5
  Question           # question_id=42
)
```

## 六、部署配置要点

### 6.1 数据库连接：
```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'exam_system',
        'USER': 'root',
        'PASSWORD': 'your_password',
        'HOST': 'localhost',
        'OPTIONS': {'charset': 'utf8mb4'}  # 支持中文存储
    }
}
```

### 6.2 Redis 配置（用于 session）：
```python
REDIS_HOST = 'localhost'
REDIS_PORT = 6379
REDIS_PASSWORD = 'your_password'
```

### 6.3 临时文件存储：
```bash
# Excel 导入临时目录
MEDIA_ROOT/excel_temp/
# 二维码生成目录
media/qr_codes/
```

## 七、运行与维护命令

### 启动服务：
```bash
python manage.py runserver 0.0.0.0:8000
```

### 执行兜底判分（管理后台）：
```python
from exams.auto_submit import auto_submit_overdue_exams
result = auto_submit_overdue_exams()
# 返回统计：处理总数、成功数、失败详情
```

## 八、常见问题排查

### Q1: Excel 导入失败？
- 检查文件路径是否可读（`file_path` 临时保存）
- 确认列数至少为 7 列
- 查看 `errors` 字段获取具体行号错误信息

### Q2: 学生无法看到考试？
- 检查班级关联：`StudentClassRelation.objects.filter(student=user).values_list('class_info_id')`
- 检查可见性设置：`Exam.visibility` + `allowed_classes`

### Q3: 判分结果异常？
- 确认答案格式（大小写不敏感，但需去除空格）
- 填空题部分得分会记录为 `wrong_count+=1`（因为不是完全正确）

## 九、扩展建议

1. **增加题型**：在 `Question.clean()` 中添加判断题、多选题的验证逻辑
2. **防抄袭检测**：将 `answer_sheet` 历史记录到 Redis，比对相似答案
3. **考试监控面板**：实时统计在线答题人数（使用 Redis Set）
4. **成绩分析报表**：基于 `ExamRecord.grading_details` 生成题型得分分布图
