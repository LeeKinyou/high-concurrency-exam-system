import pytest

from examination.grader import grade_blank_question, grade_choice_question, grade_exam


@pytest.mark.django_db
class TestGradeChoiceQuestion:
    def test_correct_single(self):
        correct, score = grade_choice_question("A", "A", 10)
        assert correct is True
        assert score == 10

    def test_wrong_single(self):
        correct, score = grade_choice_question("A", "B", 10)
        assert correct is False
        assert score == 0

    def test_correct_multiple(self):
        correct, score = grade_choice_question("A,B", "B,A", 10)
        assert correct is True
        assert score == 10

    def test_case_insensitive(self):
        correct, score = grade_choice_question("a", "A", 10)
        assert correct is True

    def test_partial_multiple_wrong(self):
        correct, score = grade_choice_question("A,B", "A", 10)
        assert correct is False
        assert score == 0


@pytest.mark.django_db
class TestGradeBlankQuestion:
    def test_correct_single(self):
        correct, score = grade_blank_question("北京", "北京", 10)
        assert correct is True
        assert score == 10

    def test_wrong_single(self):
        correct, score = grade_blank_question("北京", "上海", 10)
        assert correct is False
        assert score == 0

    def test_case_insensitive(self):
        correct, score = grade_blank_question("beijing", "Beijing", 10)
        assert correct is True

    def test_multiple_answers(self):
        correct, score = grade_blank_question("北京|Beijing", "北京", 10)
        assert correct is True

    def test_multiple_answers_second_match(self):
        correct, score = grade_blank_question("北京|Beijing", "Beijing", 10)
        assert correct is True

    def test_empty_answer(self):
        correct, score = grade_blank_question("北京", "", 10)
        assert correct is False
        assert score == 0

    def test_multi_blank_full_correct(self):
        correct, score = grade_blank_question("北京|上海", "北京,上海", 20)
        assert correct is True
        assert score == 20

    def test_multi_blank_partial(self):
        correct, score = grade_blank_question("北京|上海", "北京,南京", 20)
        assert correct is False
        assert score == 10


@pytest.mark.django_db
class TestGradeExam:
    def test_grade_full_exam(self, teacher):
        from examination.models import Exam, ExamQuestion, Question

        exam = Exam.objects.create(title="测试考试", created_by=teacher, total_score=30)
        q1 = Question.objects.create(exam=exam, question_type="choice", content="1+1=?", options="[]", answer="B", score=10, order=1)
        q2 = Question.objects.create(exam=exam, question_type="choice", content="2+2=?", options="[]", answer="C", score=10, order=2)
        q3 = Question.objects.create(exam=exam, question_type="blank", content="中国的首都是___", answer="北京", score=10, order=3)
        ExamQuestion.objects.create(exam=exam, question=q1, order=1)
        ExamQuestion.objects.create(exam=exam, question=q2, order=2)
        ExamQuestion.objects.create(exam=exam, question=q3, order=3)

        answers = {str(q1.id): "B", str(q2.id): "A", str(q3.id): "北京"}
        total, details = grade_exam(exam.id, answers)

        assert total == 20  # q1 correct, q2 wrong, q3 correct
        assert details[str(q1.id)]["correct"] is True
        assert details[str(q2.id)]["correct"] is False
        assert details[str(q3.id)]["correct"] is True


def grade_blank_answer(expected, student_answer, max_score):
    return grade_blank_question(expected, student_answer, max_score)
