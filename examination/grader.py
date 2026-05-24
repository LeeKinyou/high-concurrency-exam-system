import json
import logging

from core.constants import QuestionType

logger = logging.getLogger(__name__)


def grade_exam(exam_id: int, answers: dict) -> tuple[int, dict]:
    """对整场考试进行判分。

    Args:
        exam_id: 考试 ID
        answers: {question_id: student_answer} 字典

    Returns:
        (total_score, details) 元组
        details 格式: {question_id: {"correct": bool, "score": int, "expected": str, "got": str}}
    """
    from .models import ExamQuestion

    exam_questions = ExamQuestion.objects.filter(exam_id=exam_id).select_related("question")

    total_score = 0
    details = {}

    for eq in exam_questions:
        q = eq.question
        student_answer = answers.get(str(q.id), "")
        expected = q.answer

        if q.question_type == QuestionType.CHOICE:
            correct, earned = grade_choice_question(expected, student_answer, q.score)
        else:
            correct, earned = grade_blank_question(expected, student_answer, q.score)

        total_score += earned
        details[str(q.id)] = {
            "correct": correct,
            "score": earned,
            "expected": expected,
            "got": student_answer,
        }

    return total_score, details


def grade_choice_question(expected: str, student_answer: str, max_score: int) -> tuple[bool, int]:
    """选择题判分。

    Args:
        expected: 正确答案（如 "A" 或 "A,B"）
        student_answer: 学生答案
        max_score: 该题满分

    Returns:
        (is_correct, earned_score)
    """
    expected_set = set(expected.replace(" ", "").upper().split(","))
    student_set = set(student_answer.replace(" ", "").upper().split(","))

    if expected_set == student_set:
        return True, max_score
    return False, 0


def grade_blank_question(expected: str, student_answer: str, max_score: int) -> tuple[bool, int]:
    """填空题判分，支持多答案匹配。

    正确答案用 "|" 分隔：单空题为可选答案，多空题为各空的正确答案。
    学生答案使用 "," 分隔多个空的答案。

    Args:
        expected: 正确答案
        student_answer: 学生答案
        max_score: 该题满分

    Returns:
        (is_correct, earned_score)
    """
    if not student_answer.strip():
        return False, 0

    expected_parts = expected.strip().split("|")
    student_parts = [s.strip() for s in student_answer.strip().split(",")]

    # 单空题（学生答案无逗号）：expected 用 "|" 分隔多个可接受答案
    if len(student_parts) == 1:
        student_lower = student_parts[0].lower()
        for alt in expected_parts:
            if student_lower == alt.strip().lower():
                return True, max_score
        return False, 0

    # 多空题（学生答案有逗号）：expected 用 "|" 分隔各空，每空内用 "," 分隔可选答案
    correct_count = 0
    for i, student_part in enumerate(student_parts):
        if i < len(expected_parts):
            acceptable = [a.strip().lower() for a in expected_parts[i].split(",")]
            if student_part.lower() in acceptable:
                correct_count += 1

    if correct_count == len(expected_parts):
        return True, max_score
    elif correct_count > 0:
        earned = int(max_score * correct_count / len(expected_parts))
        return False, earned
    return False, 0
