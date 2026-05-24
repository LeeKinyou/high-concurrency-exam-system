from django.core.paginator import Paginator
from django.http import JsonResponse


def success_response(data=None, message: str = "操作成功", status_code: int = 200) -> JsonResponse:
    return JsonResponse(
        {"code": status_code, "message": message, "data": data},
        status=status_code,
    )


def error_response(code: int = 400, message: str = "请求错误", data=None) -> JsonResponse:
    return JsonResponse(
        {"code": code, "message": message, "data": data},
        status=code,
    )


def paginated_response(queryset, page: int = 1, page_size: int = 20, serializer=None) -> JsonResponse:
    paginator = Paginator(queryset, page_size)
    page_obj = paginator.get_page(page)

    if serializer:
        items = [serializer(obj) for obj in page_obj]
    else:
        items = list(page_obj)

    return success_response(
        data={
            "items": items,
            "total": paginator.count,
            "page": page_obj.number,
            "page_size": page_size,
            "total_pages": paginator.num_pages,
        }
    )
