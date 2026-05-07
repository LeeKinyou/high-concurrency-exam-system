# Data migration to migrate existing questions to new structure

from django.db import migrations


def migrate_questions_to_examquestion(apps, schema_editor):
    """将现有的 Question 关联迁移到 ExamQuestion 表"""
    Question = apps.get_model('exams', 'Question')
    ExamQuestion = apps.get_model('exams', 'ExamQuestion')
    
    # 查找所有还有 exam 外键的题目
    questions_with_exam = Question.objects.filter(exam__isnull=False)
    
    for question in questions_with_exam:
        # 为每个题目创建 ExamQuestion 关联
        ExamQuestion.objects.create(
            exam=question.exam,
            question=question,
            score=question.score,
            order=question.order if hasattr(question, 'order') else 0
        )
        
        # 设置 created_by 为考试的创建者
        if question.exam and question.exam.created_by:
            question.created_by = question.exam.created_by
            question.save()


class Migration(migrations.Migration):

    dependencies = [
        ('exams', '0003_examquestion_remove_question_exam_and_more'),
    ]

    operations = [
        migrations.RunPython(migrate_questions_to_examquestion),
    ]
