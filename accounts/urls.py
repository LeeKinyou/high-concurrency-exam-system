from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('upload/', views.upload_student_accounts, name='upload'),
    path('upload-success/', views.upload_success, name='upload_success'),
    
    # 二维码相关
    path('generate-qr/', views.generate_qr_code, name='generate_qr'),
    path('api/session-id/', views.get_session_id, name='get_session_id'),
    path('login/<str:session_id>/', views.student_login, name='login'),  # 支持 session_id 参数 - 放前面优先匹配
    path('login/', views.student_login, name='login'),
    path('login-error/', views.login_error, name='login_error'),
    path('permission-denied/', views.permission_denied, name='permission_denied'),
    
    # 教师登录
    path('teacher/login/', views.teacher_login, name='teacher_login'),
    path('teacher/logout/', views.teacher_logout, name='teacher_logout'),
]
