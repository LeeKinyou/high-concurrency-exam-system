import redis
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
import uuid
import logging

logger = logging.getLogger(__name__)

# 内存存储作为后备方案
_memory_store = {}


def get_redis_connection():
    """
    获取 Redis 连接
    使用连接池避免连接泄露
    如果 Redis 不可用，返回 None 并使用内存存储
    """
    try:
        redis_conn = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            password=settings.REDIS_PASSWORD,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5
        )
        # 测试连接
        redis_conn.ping()
        return redis_conn
    except Exception as e:
        logger.warning(f'Redis 连接失败，使用内存存储：{e}')
        return None


def generate_session_id():
    """
    生成唯一的 session_id 并存储到 Redis
    
    Returns:
        str: 生成的 session_id
    """
    session_id = str(uuid.uuid4())
    # 使用统一的 key 格式，与 api_generate_qr 保持一致
    key = f'qr_session_{session_id}'
    
    # 使用 cache API 统一存储，60 秒过期
    cache.set(key, {
        'created_at': timezone.now().isoformat()
    }, timeout=60)
    
    return session_id


def verify_session_id(session_id):
    """
    验证 session_id 是否有效
    
    Args:
        session_id: 要验证的 session_id
        
    Returns:
        bool: session_id 是否有效
    """
    if not session_id:
        return False
    
    # 使用统一的 cache API，key 格式与 api_generate_qr 保持一致
    key = f'qr_session_{session_id}'
    data = cache.get(key)
    
    return data is not None


def refresh_session_id(session_id):
    """
    刷新 session_id 的过期时间
    
    Args:
        session_id: 要刷新的 session_id
        
    Returns:
        bool: 是否刷新成功
    """
    if not session_id:
        return False
    
    # 使用统一的 cache API
    key = f'qr_session_{session_id}'
    data = cache.get(key)
    
    if data:
        # 重新设置，延长过期时间到 60 秒
        cache.set(key, data, timeout=60)
        return True
    return False


def invalidate_session_id(session_id):
    """
    使 session_id 失效
    
    Args:
        session_id: 要使失效的 session_id
    """
    if session_id:
        # 使用统一的 cache API
        key = f'qr_session_{session_id}'
        cache.delete(key)
