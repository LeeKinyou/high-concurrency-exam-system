"""
判题算法模块
实现选择题和填空题的自动判分逻辑
"""


def grade_choice_question(student_answer, correct_answer, score):
    """
    选择题判分逻辑
    精准比对，完全匹配得满分，否则得 0 分
    
    Args:
        student_answer: 学生答案 (str)
        correct_answer: 正确答案 (str)
        score: 题目分值 (int)
    
    Returns:
        int: 得分
    """
    if not student_answer or not correct_answer:
        return 0
    
    # 去除空格和大小写影响
    student_answer = str(student_answer).strip().upper()
    correct_answer = str(correct_answer).strip().upper()
    
    # 完全匹配得满分
    if student_answer == correct_answer:
        return score
    
    return 0


def grade_blank_question(student_answer, correct_answer, score):
    """
    填空题判分逻辑
    两阶段判分：
    1. 完全匹配：得满分
    2. 包含匹配：正确答案是学生答案的子串，得 50% 分数（向上取整）
    3. 完全不匹配：得 0 分
    
    Args:
        student_answer: 学生答案 (str)
        correct_answer: 正确答案 (str)
        score: 题目分值 (int)
    
    Returns:
        int: 得分
    """
    if not student_answer or not correct_answer:
        return 0
    
    # 去除首尾空格
    student_answer = str(student_answer).strip()
    correct_answer = str(correct_answer).strip()
    
    # 第一阶段：完全匹配
    if student_answer == correct_answer:
        return score
    
    # 第二阶段：包含匹配（宽容模式）
    # 检查正确答案是否作为子串包含在学生回答中
    if correct_answer in student_answer:
        # 给予 50% 分数，向上取整
        from math import ceil
        return ceil(score * 0.5)
    
    # 完全不匹配
    return 0


def grade_exam(exam, answer_sheet):
    """
    判阅整张试卷
    
    Args:
        exam: Exam 对象
        answer_sheet: 答题数据 (dict)
                     格式：{question_id: answer, ...}
    
    Returns:
        dict: 判题结果
            - total_score: 总分
            - question_scores: 每题得分详情
            - correct_count: 正确题数
            - wrong_count: 错误题数
    """
    from .models import Question, ExamQuestion
    
    total_score = 0
    question_scores = {}
    correct_count = 0
    wrong_count = 0
    
    # 获取所有题目（通过 ExamQuestion 表）
    exam_questions = ExamQuestion.objects.filter(exam=exam).select_related('question')
    
    for eq in exam_questions:
        question = eq.question
        question_id = str(question.id)
        student_answer = answer_sheet.get(question_id, '')
        
        # 使用 ExamQuestion 中的分值
        question_score = eq.score
        
        # 根据题型调用不同的判分函数
        if question.question_type == 'choice':
            score = grade_choice_question(
                student_answer,
                question.answer,
                question_score
            )
        elif question.question_type == 'blank':
            score = grade_blank_question(
                student_answer,
                question.answer,
                question_score
            )
        else:
            # 未知题型，得 0 分
            score = 0
        
        total_score += score
        question_scores[question_id] = {
            'score': score,
            'max_score': question_score,
            'student_answer': student_answer,
            'correct_answer': question.answer,
            'is_correct': score == question_score
        }
        
        if score == question_score:
            correct_count += 1
        elif score > 0:
            # 部分得分（如填空题包含匹配）
            wrong_count += 1
        else:
            wrong_count += 1
    
    return {
        'total_score': total_score,
        'question_scores': question_scores,
        'correct_count': correct_count,
        'wrong_count': wrong_count,
        'question_count': exam_questions.count()
    }
