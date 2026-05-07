import openpyxl
from openpyxl import Workbook

# 创建工作簿
wb = Workbook()
ws = wb.active
ws.title = "题目"

# 写入表头
headers = ['题目类型', '题干', '选项 A', '选项 B', '选项 C', '选项 D', '答案']
ws.append(headers)

# 15 道选择题（每题 5 分，共 75 分）
choice_questions = [
    ['选择题', '1+1 等于多少？', '1', '2', '3', '4', 'B'],
    ['选择题', '中国的首都是哪里？', '上海', '北京', '广州', '深圳', 'B'],
    ['选择题', '地球是太阳系中的第几大行星？', '第一', '第二', '第三', '第四', 'C'],
    ['选择题', '水的化学式是什么？', 'CO2', 'H2O', 'O2', 'H2', 'B'],
    ['选择题', '以下哪个是质数？', '4', '6', '7', '9', 'C'],
    ['选择题', '一年有多少天？（平年）', '364', '365', '366', '367', 'B'],
    ['选择题', '光的速度约为？', '3×10^5 km/s', '3×10^6 km/s', '3×10^7 km/s', '3×10^8 km/s', 'A'],
    ['选择题', '以下哪个不是四大发明？', '造纸术', '指南针', '火药', '地动仪', 'D'],
    ['选择题', '人体有多少块骨头？', '206', '208', '210', '212', 'A'],
    ['选择题', '以下哪个是哺乳动物？', '鱼', '鸟', '猫', '蛇', 'C'],
    ['选择题', '三角形的内角和是多少度？', '90°', '180°', '270°', '360°', 'B'],
    ['选择题', '以下哪个元素符号表示氧？', 'H', 'C', 'O', 'N', 'C'],
    ['选择题', '长江是中国第几长河？', '第一', '第二', '第三', '第四', 'A'],
    ['选择题', '以下哪个是可再生能源？', '煤炭', '石油', '太阳能', '天然气', 'C'],
    ['选择题', '牛顿第一定律又称为什么？', '惯性定律', '加速度定律', '作用力定律', '反作用力定律', 'A'],
]

# 5 道填空题（每题 5 分，共 25 分）
blank_questions = [
    ['填空题', '地球自转一周需要____小时', '', '', '', '', '24'],
    ['填空题', '水的沸点是____摄氏度（标准大气压下）', '', '', '', '', '100'],
    ['填空题', '中国共有____个省级行政区', '', '', '', '', '34'],
    ['填空题', '人体正常体温约为____摄氏度', '', '', '', '', '37;36.5;36.8'],
    ['填空题', '一年有____个月', '', '', '', '', '12'],
]

# 写入选择题
for q in choice_questions:
    ws.append(q)

# 写入填空题
for q in blank_questions:
    ws.append(q)

# 调整列宽
ws.column_dimensions['A'].width = 15
ws.column_dimensions['B'].width = 50
ws.column_dimensions['C'].width = 20
ws.column_dimensions['D'].width = 20
ws.column_dimensions['E'].width = 20
ws.column_dimensions['F'].width = 20
ws.column_dimensions['G'].width = 15

# 保存文件
file_path = r'c:\Users\xd141\Desktop\exam\exam\题目示例.xlsx'
wb.save(file_path)
wb.close()

print(f'文件已生成：{file_path}')
print(f'题目总数：{len(choice_questions) + len(blank_questions)}')
print(f'- 选择题：{len(choice_questions)}道 × 5 分 = {len(choice_questions) * 5}分')
print(f'- 填空题：{len(blank_questions)}道 × 5 分 = {len(blank_questions) * 5}分')
print(f'总分：{len(choice_questions) * 5 + len(blank_questions) * 5}分')
