# Final cleanup migration

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('exams', '0004_migrate_questions_to_examquestion'),
    ]

    operations = [
        # 第五步：彻底删除 exam 字段
        migrations.RemoveField(
            model_name='question',
            name='exam',
        ),
        
        # 第六步：将 created_by 设为必填
        migrations.AlterField(
            model_name='question',
            name='created_by',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='created_questions', to='accounts.user', verbose_name='创建者'),
        ),
    ]
