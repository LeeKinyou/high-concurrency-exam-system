import json
import math
import statistics
from datetime import datetime, timedelta

from django.db.models import Avg, Count, Q
from django.http import JsonResponse
from django.utils import timezone

from accounts.decorators import teacher_required, student_required
from accounts.models import User
from core.responses import success_response

from .models import ClassInfo, Exam, ExamRecord, StudentClassRelation


# ---------------------------------------------------------------------------
# 教师端 API
# ---------------------------------------------------------------------------

@teacher_required
def teacher_kpi_api(request):
    """教师仪表盘 KPI 数据"""
    teacher = request.user
    today = timezone.now().date()
    today_start = datetime.combine(today, datetime.min.time())

    # 今日参考率
    today_exams = Exam.objects.filter(
        created_by=teacher, is_active=True,
        start_time__date=today
    )
    total_assigned = 0
    total_submitted = 0
    for exam in today_exams:
        if exam.visibility == "public":
            assigned = User.objects.filter(role="student", is_active=True).count()
        else:
            assigned = StudentClassRelation.objects.filter(
                class_info__in=exam.allowed_classes.all()
            ).values("student").distinct().count()
        submitted = ExamRecord.objects.filter(
            exam=exam, status__in=["submitted", "auto_graded", "manual_graded", "reviewed"]
        ).count()
        total_assigned += assigned
        total_submitted += submitted

    attendance_rate = round(total_submitted / total_assigned * 100, 1) if total_assigned else 0

    # 平均分 & 及格率（最近一场考试）
    latest_exam = Exam.objects.filter(
        created_by=teacher, is_active=True
    ).order_by("-start_time").first()

    avg_score = 0
    pass_rate = 0
    excellent_rate = 0
    pending_grading = 0

    if latest_exam:
        records = ExamRecord.objects.filter(exam=latest_exam, is_graded=True)
        scores = [r.score for r in records]
        if scores:
            avg_score = round(sum(scores) / len(scores), 1)
            pass_rate = round(len([s for s in scores if s >= latest_exam.total_score * 0.6]) / len(scores) * 100, 1)
            excellent_rate = round(len([s for s in scores if s >= latest_exam.total_score * 0.9]) / len(scores) * 100, 1)

        pending_grading = ExamRecord.objects.filter(
            exam=latest_exam, status="submitted"
        ).count()

    return success_response(data={
        "attendance_rate": attendance_rate,
        "avg_score": avg_score,
        "pass_rate": pass_rate,
        "excellent_rate": excellent_rate,
        "pending_grading": pending_grading,
        "latest_exam_title": latest_exam.title if latest_exam else "暂无考试",
    })


@teacher_required
def class_distribution_api(request):
    """班级成绩分布 - 正态分布数据"""
    exam_id = request.GET.get("exam_id")
    class_id = request.GET.get("class_id")

    if not exam_id:
        return success_response(data={"bins": [], "counts": [], "curve": []})

    records = ExamRecord.objects.filter(exam_id=int(exam_id), is_graded=True)
    if class_id:
        student_ids = StudentClassRelation.objects.filter(
            class_info_id=int(class_id)
        ).values_list("student_id", flat=True)
        records = records.filter(student_id__in=student_ids)

    scores = [r.score for r in records]
    if not scores:
        return success_response(data={"bins": [], "counts": [], "curve": []})

    exam = Exam.objects.get(id=int(exam_id))
    max_score = exam.total_score

    # 分数段统计
    bin_size = max(5, max_score // 20)
    bins = list(range(0, max_score + bin_size, bin_size))
    counts = [0] * (len(bins) - 1)

    for s in scores:
        for i in range(len(bins) - 1):
            if bins[i] <= s < bins[i + 1]:
                counts[i] += 1
                break
        if s >= bins[-1]:
            counts[-1] += 1

    # 正态分布曲线
    if len(scores) > 1:
        mean = statistics.mean(scores)
        std = statistics.stdev(scores)
    else:
        mean = scores[0] if scores else 0
        std = 1

    curve = []
    for x in range(0, max_score + 1):
        if std > 0:
            y = (1 / (std * math.sqrt(2 * math.pi))) * math.exp(-0.5 * ((x - mean) / std) ** 2)
        else:
            y = 0
        curve.append([x, round(y * len(scores) * bin_size, 2)])

    return success_response(data={
        "bins": bins[:-1],
        "counts": counts,
        "curve": curve,
        "mean": round(mean, 1),
        "std": round(std, 2),
        "max_score": max_score,
    })


@teacher_required
def knowledge_mastery_api(request):
    """知识点掌握热力图数据"""
    exam_id = request.GET.get("exam_id")
    if not exam_id:
        return success_response(data={"chapters": [], "knowledge_points": [], "data": []})

    # 模拟知识点数据结构（实际应从 Question 模型扩展知识点字段）
    # 这里基于 grading_details 分析每道题的班级得分率
    records = ExamRecord.objects.filter(exam_id=int(exam_id), is_graded=True)
    exam = Exam.objects.get(id=int(exam_id))

    # 获取题目列表
    questions = exam.exam_questions.select_related("question").order_by("order")

    chapters = []
    knowledge_points = []
    data = []

    # 按题目分组计算得分率
    for eq in questions:
        q = eq.question
        # 模拟章节和知识点（实际应存储在 Question 模型中）
        chapter = f"第{(eq.order - 1) // 3 + 1}章"
        kp = f"知识点{eq.order}"

        if chapter not in chapters:
            chapters.append(chapter)
        if kp not in knowledge_points:
            knowledge_points.append(kp)

        # 计算该题班级平均得分率
        total_score = 0
        got_score = 0
        for r in records:
            details = r.get_grading_details_dict()
            q_key = str(q.id)
            if q_key in details:
                got_score += details[q_key].get("score", 0)
                total_score += q.score

        rate = round(got_score / total_score * 100, 1) if total_score else 0
        data.append([chapters.index(chapter), knowledge_points.index(kp), rate])

    return success_response(data={
        "chapters": chapters,
        "knowledge_points": knowledge_points,
        "data": data,
    })


@teacher_required
def trend_analysis_api(request):
    """成绩趋势雷达图"""
    class_id = request.GET.get("class_id")
    exam_ids = request.GET.getlist("exam_ids")

    if not exam_ids:
        # 默认最近 3 场考试
        exams = Exam.objects.filter(
            created_by=request.user, is_active=True
        ).order_by("-start_time")[:3]
        exam_ids = [str(e.id) for e in exams]

    dimensions = ["计算能力", "逻辑推理", "知识记忆", "应用分析", "创新思维"]
    series = []

    for exam_id in exam_ids[:5]:
        try:
            exam = Exam.objects.get(id=int(exam_id))
        except Exam.DoesNotExist:
            continue

        records = ExamRecord.objects.filter(exam=exam, is_graded=True)
        if class_id:
            student_ids = StudentClassRelation.objects.filter(
                class_info_id=int(class_id)
            ).values_list("student_id", flat=True)
            records = records.filter(student_id__in=student_ids)

        # 模拟各维度得分（实际应基于题目知识点分类）
        scores = [r.score for r in records]
        if not scores:
            continue

        avg = sum(scores) / len(scores)
        max_s = exam.total_score

        # 基于平均分模拟各维度表现
        values = [
            round(min(100, avg / max_s * 100 + 5), 1),
            round(min(100, avg / max_s * 100 - 3), 1),
            round(min(100, avg / max_s * 100 + 2), 1),
            round(min(100, avg / max_s * 100 - 1), 1),
            round(min(100, avg / max_s * 100 + 8), 1),
        ]

        series.append({
            "name": exam.title,
            "value": values,
        })

    return success_response(data={
        "dimensions": dimensions,
        "series": series,
    })


@teacher_required
def error_analysis_api(request):
    """错题高频分析"""
    exam_id = request.GET.get("exam_id")
    if not exam_id:
        return success_response(data={"errors": [], "word_cloud": []})

    records = ExamRecord.objects.filter(exam_id=int(exam_id), is_graded=True)
    exam = Exam.objects.get(id=int(exam_id))
    questions = exam.exam_questions.select_related("question").order_by("order")

    error_counts = []
    for eq in questions:
        q = eq.question
        wrong = 0
        for r in records:
            details = r.get_grading_details_dict()
            q_key = str(q.id)
            if q_key in details and details[q_key].get("score", 0) < q.score:
                wrong += 1

        error_counts.append({
            "question": f"题{eq.order}",
            "count": wrong,
            "type": q.get_question_type_display(),
            "difficulty": q.get_difficulty_display(),
        })

    error_counts.sort(key=lambda x: x["count"], reverse=True)

    # 词云数据（从错题题干提取关键词）
    word_cloud = []
    for item in error_counts[:10]:
        word_cloud.append({
            "name": item["question"],
            "value": item["count"],
        })

    return success_response(data={
        "errors": error_counts,
        "word_cloud": word_cloud,
    })


# ---------------------------------------------------------------------------
# 学生端 API
# ---------------------------------------------------------------------------

@student_required
def student_skills_api(request):
    """学生能力六维雷达"""
    student = request.user

    # 获取最近 5 次考试
    records = ExamRecord.objects.filter(
        student=student, is_graded=True
    ).select_related("exam").order_by("-start_time")[:5]

    dimensions = ["基础知识", "运算速度", "解题技巧", "审题习惯", "创新思维", "应试心态"]

    series = []
    for r in records:
        score_pct = r.score / r.total_score * 100 if r.total_score else 0

        # 基于总分模拟各维度（实际应根据每道题的评分细节）
        values = [
            round(min(100, score_pct + 5), 1),
            round(min(100, score_pct - 2), 1),
            round(min(100, score_pct + 3), 1),
            round(min(100, score_pct - 5), 1),
            round(min(100, score_pct + 8), 1),
            round(min(100, score_pct - 3), 1),
        ]

        series.append({
            "name": r.exam.title,
            "date": r.start_time.strftime("%m-%d"),
            "value": values,
        })

    return success_response(data={
        "dimensions": dimensions,
        "series": series,
    })


@student_required
def error_stats_api(request):
    """错题消灭进度"""
    student = request.user

    records = ExamRecord.objects.filter(
        student=student, is_graded=True
    ).order_by("-start_time")

    total_wrong = 0
    mastered = 0
    pending = 0

    for r in records:
        details = r.get_grading_details_dict()
        for q_id, detail in details.items():
            if detail.get("score", 0) < detail.get("total", 10):
                total_wrong += 1
                # 模拟掌握状态（实际应有专门的错题本模型）
                if detail.get("score", 0) > 0:
                    mastered += 1
                else:
                    pending += 1

    if total_wrong == 0:
        total_wrong = 1  # 避免除零

    return success_response(data={
        "total_wrong": total_wrong,
        "mastered": mastered,
        "pending": pending,
        "mastered_rate": round(mastered / total_wrong * 100, 1),
    })


@student_required
def student_timeline_api(request):
    """学习行为时间轴"""
    student = request.user

    records = ExamRecord.objects.filter(
        student=student
    ).select_related("exam").order_by("-start_time")[:20]

    events = []
    for r in records:
        duration = 0
        if r.submit_time and r.start_time:
            duration = int((r.submit_time - r.start_time).total_seconds() / 60)

        events.append({
            "type": "exam",
            "title": f"参加「{r.exam.title}」",
            "time": r.start_time.strftime("%Y-%m-%d %H:%M"),
            "score": r.score if r.is_graded else None,
            "duration": duration,
            "status": r.status,
        })

    # 添加登录事件（模拟）
    events.append({
        "type": "login",
        "title": "登录系统",
        "time": student.last_login.strftime("%Y-%m-%d %H:%M") if student.last_login else "",
    })

    events.sort(key=lambda x: x["time"], reverse=True)

    return success_response(data={"events": events[:15]})


@student_required
def prediction_api(request):
    """成绩预测分析"""
    student = request.user

    records = ExamRecord.objects.filter(
        student=student, is_graded=True
    ).order_by("start_time")

    scores = [(i, r.score / r.total_score * 100) for i, r in enumerate(records)]

    prediction = None
    trend = []
    suggestion = "继续加油，多参加模考以获取更准确的预测。"

    if len(scores) >= 3:
        # 简单线性回归预测
        n = len(scores)
        x_mean = sum(x for x, y in scores) / n
        y_mean = sum(y for x, y in scores) / n

        numerator = sum((x - x_mean) * (y - y_mean) for x, y in scores)
        denominator = sum((x - x_mean) ** 2 for x, y in scores)

        if denominator != 0:
            slope = numerator / denominator
            intercept = y_mean - slope * x_mean
            next_x = n
            prediction = round(slope * next_x + intercept, 1)

            # 生成趋势数据
            for x, y in scores:
                trend.append({"x": x + 1, "actual": round(y, 1), "predicted": None})
            trend.append({"x": n + 1, "actual": None, "predicted": prediction})

            if slope > 0:
                suggestion = f"成绩呈上升趋势，预计下次可提升 {round(slope, 1)} 分。建议保持当前学习节奏。"
            else:
                suggestion = "成绩有所波动，建议回顾近期错题，加强薄弱环节复习。"

    return success_response(data={
        "prediction": prediction,
        "trend": trend,
        "suggestion": suggestion,
        "history": [{"x": i + 1, "score": round(y, 1)} for i, (x, y) in enumerate(scores)],
    })


@student_required
def class_ranking_api(request):
    """班级排名可视化"""
    student = request.user

    # 获取学生所在班级
    relations = StudentClassRelation.objects.filter(student=student)
    if not relations.exists():
        return success_response(data={"rankings": []})

    class_info = relations.first().class_info
    student_ids = StudentClassRelation.objects.filter(
        class_info=class_info
    ).values_list("student_id", flat=True)

    # 获取班级所有学生的最新考试成绩
    rankings = []
    for sid in student_ids:
        latest = ExamRecord.objects.filter(
            student_id=sid, is_graded=True
        ).order_by("-start_time").first()

        if latest:
            rankings.append({
                "student_id": sid,
                "name": latest.student.first_name or latest.student.username,
                "score": latest.score,
                "total": latest.total_score,
            })

    rankings.sort(key=lambda x: x["score"], reverse=True)

    # 计算排名和分差
    for i, r in enumerate(rankings):
        r["rank"] = i + 1
        r["gap_prev"] = round(r["score"] - rankings[i - 1]["score"], 1) if i > 0 else 0
        r["gap_next"] = round(rankings[i + 1]["score"] - r["score"], 1) if i < len(rankings) - 1 else 0

    return success_response(data={
        "class_name": class_info.name,
        "rankings": rankings,
        "my_rank": next((r["rank"] for r in rankings if r["student_id"] == student.id), None),
    })
