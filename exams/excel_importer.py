import openpyxl
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from .models import Question

User = get_user_model()


class ExcelQuestionImporter:
    """
    Excel 题目导入器
    
    支持从 Excel 文件批量导入题目到题库
    Excel 格式规范：
    - 第 1 列：题目类型（'选择题' 或 '填空题'）
    - 第 2 列：题干内容
    - 第 3-6 列：选项 A、B、C、D（仅选择题需要）
    - 第 7 列：正确答案
    
    选择题：题干 | 选项 A | 选项 B | 选项 C | 选项 D | 答案
    填空题：题干 | | | | | 答案
    """
    
    REQUIRED_COLUMNS = 7  # 至少需要 7 列
    QUESTION_TYPE_CHOICES = ['选择题', '填空题']
    
    def __init__(self, file_path, created_by_user):
        """
        初始化导入器
        
        Args:
            file_path: Excel 文件路径
            created_by_user: 创建者用户对象
        """
        self.file_path = file_path
        self.created_by = created_by_user
        self.parsed_questions = []
        self.errors = []
        self.success_count = 0
        self.failure_count = 0
    
    def parse_excel(self):
        """
        解析 Excel 文件
        
        Returns:
            dict: 包含解析结果和错误信息的字典
        """
        try:
            workbook = openpyxl.load_workbook(self.file_path, read_only=True, data_only=True)
            sheet = workbook.active
            
            # 跳过表头（第一行）
            for row_idx, row in enumerate(sheet.iter_rows(min_row=2), start=2):
                try:
                    question_data = self._parse_row(row, row_idx)
                    if question_data:
                        self.parsed_questions.append(question_data)
                except Exception as e:
                    self.errors.append({
                        'row': row_idx,
                        'error': f'解析失败：{str(e)}',
                        'data': self._get_row_data(row)
                    })
                    self.failure_count += 1
            
            workbook.close()
            
            return {
                'success': True,
                'questions': self.parsed_questions,
                'errors': self.errors,
                'total_count': len(self.parsed_questions) + len(self.errors),
                'parsed_count': len(self.parsed_questions),
                'error_count': len(self.errors)
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'文件解析失败：{str(e)}',
                'questions': [],
                'errors': []
            }
    
    def _parse_row(self, row, row_number):
        """
        解析单行数据
        
        Args:
            row: Excel 行对象
            row_number: 行号
            
        Returns:
            dict: 解析后的题目数据，如果无效则返回 None
        """
        # 获取单元格数据
        cells = [cell.value if cell.value is not None else '' for cell in row]
        
        # 检查是否为空行
        if not any(cells):
            return None
        
        # 检查列数
        if len(cells) < self.REQUIRED_COLUMNS:
            raise ValueError(f'列数不足，至少需要{self.REQUIRED_COLUMNS}列，当前{len(cells)}列')
        
        # 提取数据
        question_type_raw = str(cells[0]).strip()
        question_text = str(cells[1]).strip()
        option_a = str(cells[2]).strip() if cells[2] else ''
        option_b = str(cells[3]).strip() if cells[3] else ''
        option_c = str(cells[4]).strip() if cells[4] else ''
        option_d = str(cells[5]).strip() if cells[5] else ''
        answer_raw = str(cells[6]).strip() if cells[6] else ''
        
        # 验证题目类型
        question_type = self._parse_question_type(question_type_raw)
        
        # 验证题干
        if not question_text:
            raise ValueError('题干不能为空')
        
        # 解析答案
        answer = self._parse_answer(answer_raw, question_type)
        
        # 选择题验证
        if question_type == 'choice':
            if not option_a or not option_b:
                raise ValueError('选择题必须至少包含选项 A 和 B')
        
        # 构建题目数据
        question_data = {
            'row_number': row_number,
            'question_type': question_type,
            'question_text': question_text,
            'option_a': option_a if question_type == 'choice' else '',
            'option_b': option_b if question_type == 'choice' else '',
            'option_c': option_c if question_type == 'choice' else '',
            'option_d': option_d if question_type == 'choice' else '',
            'answer': answer,
            'score': 5  # 默认分值
        }
        
        return question_data
    
    def _parse_question_type(self, type_str):
        """
        解析题目类型
        
        Args:
            type_str: 题目类型字符串
            
        Returns:
            str: 'choice' 或 'blank'
        """
        type_str = type_str.strip()
        
        if type_str in ['选择题', 'choice', '单选择', '多选择']:
            return 'choice'
        elif type_str in ['填空题', 'blank', '填空']:
            return 'blank'
        else:
            raise ValueError(f'未知的题目类型：{type_str}，应为"选择题"或"填空题"')
    
    def _parse_answer(self, answer_str, question_type):
        """
        解析答案
        
        Args:
            answer_str: 答案字符串
            question_type: 题目类型
            
        Returns:
            str: 标准化后的答案
        """
        if not answer_str:
            raise ValueError('答案不能为空')
        
        answer_str = answer_str.strip().upper()
        
        if question_type == 'choice':
            # 选择题答案处理（支持多个答案，如"AB"或"A,B"）
            # 移除所有分隔符
            import re
            answer_chars = re.split(r'[,;,\s]+', answer_str)
            answer_chars = [c.strip() for c in answer_chars if c.strip()]
            
            # 验证答案字符
            valid_chars = set(['A', 'B', 'C', 'D'])
            for char in answer_chars:
                if char not in valid_chars:
                    raise ValueError(f'选择题答案只能包含 A-D，当前答案：{answer_str}')
            
            # 排序并连接
            answer_chars = sorted(set(answer_chars))
            return ''.join(answer_chars)
        
        elif question_type == 'blank':
            # 填空题答案处理（支持多个答案，用分号分隔）
            import re
            answers = re.split(r'[;,,\n]+', answer_str)
            answers = [a.strip() for a in answers if a.strip()]
            
            if not answers:
                raise ValueError('填空题答案不能为空')
            
            # 用分号连接多个答案
            return ';'.join(answers)
        
        return answer_str
    
    def _get_row_data(self, row):
        """获取行的原始数据（用于错误报告）"""
        return [cell.value if cell.value is not None else '' for cell in row[:7]]
    
    def validate_questions(self, question_ids):
        """
        验证待导入的题目
        
        Args:
            question_ids: 要导入的题目 ID 列表（来自解析后的数据）
            
        Returns:
            dict: 验证结果
        """
        validation_results = []
        
        for question_data in self.parsed_questions:
            row_num = question_data['row_number']
            
            # 检查是否在选中列表中
            if row_num not in question_ids:
                continue
            
            # 验证题目数据
            is_valid = True
            errors = []
            
            try:
                # 创建临时对象进行验证
                question = Question(
                    question_type=question_data['question_type'],
                    question_text=question_data['question_text'],
                    option_a=question_data['option_a'],
                    option_b=question_data['option_b'],
                    option_c=question_data['option_c'],
                    option_d=question_data['option_d'],
                    answer=question_data['answer'],
                    created_by=self.created_by
                )
                question.full_clean()
            except ValidationError as e:
                is_valid = False
                errors.append(str(e))
            
            validation_results.append({
                'row_number': row_num,
                'question_text': question_data['question_text'][:50],
                'is_valid': is_valid,
                'errors': errors
            })
        
        return {
            'results': validation_results,
            'valid_count': sum(1 for r in validation_results if r['is_valid']),
            'invalid_count': sum(1 for r in validation_results if not r['is_valid'])
        }
    
    def import_questions(self, question_ids=None):
        """
        执行题目导入
        
        Args:
            question_ids: 要导入的题目行号列表，如果为 None 则导入所有解析成功的题目
            
        Returns:
            dict: 导入结果报告
        """
        if question_ids is None:
            question_ids = [q['row_number'] for q in self.parsed_questions]
        
        imported_questions = []
        import_errors = []
        
        for question_data in self.parsed_questions:
            row_num = question_data['row_number']
            
            # 检查是否在选中列表中
            if row_num not in question_ids:
                continue
            
            try:
                # 创建题目
                question = Question.objects.create(
                    question_type=question_data['question_type'],
                    question_text=question_data['question_text'],
                    option_a=question_data['option_a'],
                    option_b=question_data['option_b'],
                    option_c=question_data['option_c'],
                    option_d=question_data['option_d'],
                    answer=question_data['answer'],
                    score=question_data['score'],
                    created_by=self.created_by
                )
                
                imported_questions.append({
                    'row_number': row_num,
                    'question_id': question.id,
                    'question_text': question_data['question_text'][:50],
                    'question_type': question.get_question_type_display()
                })
                self.success_count += 1
                
            except Exception as e:
                import_errors.append({
                    'row_number': row_num,
                    'question_text': question_data['question_text'][:50],
                    'error': str(e)
                })
                self.failure_count += 1
        
        return {
            'success': True,
            'imported_questions': imported_questions,
            'import_errors': import_errors,
            'imported_count': len(imported_questions),
            'failed_count': len(import_errors),
            'total_count': len(question_ids)
        }
    
    def get_statistics(self):
        """获取导入统计信息"""
        return {
            'total_parsed': len(self.parsed_questions),
            'total_errors': len(self.errors),
            'success_count': self.success_count,
            'failure_count': self.failure_count
        }
