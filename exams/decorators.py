from functools import wraps
from django.shortcuts import redirect
from django.http import JsonResponse


def exam_authorization_required(view_func):
    """
    考试权限验证装饰器
    
    检查 session 中的 exam_authorized 标记，如果未授权则：
    - 对于 HTML 请求：重定向到权限拒绝页面
    - 对于 API 请求：返回 403 JSON 响应
    
    使用示例：
        @exam_authorization_required
        def my_view(request):
            ...
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.session.get('exam_authorized'):
            accept_header = request.META.get('HTTP_ACCEPT', '')
            content_type = request.META.get('CONTENT_TYPE', '')
            is_api_request = (
                'application/json' in accept_header or
                'application/json' in content_type or
                request.method in ['POST', 'PUT', 'DELETE', 'PATCH']
            )
            
            if is_api_request:
                return JsonResponse(
                    {'success': False, 'error': '未授权访问'}, 
                    status=403
                )
            else:
                return redirect('accounts:permission_denied')
        
        return view_func(request, *args, **kwargs)
    
    return _wrapped_view
