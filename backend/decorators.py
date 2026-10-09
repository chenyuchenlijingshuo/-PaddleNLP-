from functools import wraps

from flask import g, request
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request

from extensions import db
from models import User
from utils.response import err


def load_user():
    uid = get_jwt_identity()
    if not uid:
        return None
    try:
        user_id = int(uid)
    except (TypeError, ValueError):
        return None
    return db.session.get(User, user_id)


def jwt_required_custom(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            verify_jwt_in_request()
        except Exception:
            return err("未登录或令牌无效", code=401, http_status=401)
        g.current_user = load_user()
        if not g.current_user:
            return err("用户不存在", code=401, http_status=401)
        return fn(*args, **kwargs)

    return wrapper


def role_required(*roles):
    def deco(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not getattr(g, "current_user", None):
                return err("未登录", code=401, http_status=401)
            if g.current_user.role not in roles:
                return err("权限不足", code=403, http_status=403)
            return fn(*args, **kwargs)

        return wrapper

    return deco
