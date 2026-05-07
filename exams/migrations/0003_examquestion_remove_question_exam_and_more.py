# Generated migration for exam-question decoupling

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('exams', '0002_examrecord_grading_details_and_more'),
    ]

    operations = [
        # 第一步：创建 ExamQuestion 中间表
        migrations.CreateModel(
            name='ExamQuestion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('score', models.IntegerField(default=5, verbose_name='本题分值')),
                ('order', models.IntegerField(default=0, verbose_name='题目顺序')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='添加时间')),
                ('exam', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='exam_questions', to='exams.exam', verbose_name='考试')),
                ('question', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='exam_instances', to='exams.question', verbose_name='题目')),
            ],
            options={
                'verbose_name': '考试题目关联',
                'verbose_name_plural': '考试题目关联',
                'ordering': ['order', 'id'],
                'unique_together': {('exam', 'question')},
            },
        ),
        
        # 第二步：为 Question 表添加 created_by 字段（先允许为空）
        migrations.AddField(
            model_name='question',
            name='created_by',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='created_questions', to='accounts.user', verbose_name='创建者'),
        ),
        
        # 第三步：为 Question 表添加 updated_at 字段
        migrations.AddField(
            model_name='question',
            name='updated_at',
            field=models.DateTimeField(auto_now=True, verbose_name='更新时间'),
        ),
        
        # 第四步：移除 Question 表的 exam 外键依赖（先设为可空）
        migrations.AlterField(
            model_name='question',
            name='exam',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='questions_old', to='exams.exam', verbose_name='所属考试（已废弃）'),
        ),
    ]
