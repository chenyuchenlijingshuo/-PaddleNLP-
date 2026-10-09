"""
舆情分析系统 - 用户管理路由
============================

该模块负责用户管理相关的API接口，包括：
1. 查询用户列表
2. 创建新用户（管理员权限）
3. 更新用户信息
4. 删除用户（管理员权限）

权限控制：
- admin: 可查看所有用户，可创建/编辑/删除用户
- user: 可查看所有用户，只能编辑自己的信息
- viewer: 只能查看自己的信息

安全措施：
- 防止删除最后一个管理员
- 防止修改最后一个管理员的角色
- 密码强度验证（至少6位，包含字母和数字）

API接口：
- GET /api/users: 查询用户列表
- POST /api/users: 创建新用户（管理员权限）
- PUT /api/users/<id>: 更新用户信息
- DELETE /api/users/<id>: 删除用户（管理员权限）
"""

from flask import Blueprint, g, request

from decorators import jwt_required_custom, role_required
from extensions import db
from models import User
from utils.response import err, ok
from utils.security import hash_password

users_bp = Blueprint("users", __name__)

# 有效角色集合
VALID_ROLES = {"admin", "user", "viewer"}


def _normalize_role(value):
    """规范化角色值：转换为小写并去除空白"""
    return str(value or "").strip().lower()


def _ensure_last_admin_kept(target_user_id=None, next_role=None, deleting=False):
    """
    确保系统中至少保留一个管理员
    
    功能说明：
    - 防止删除最后一个管理员
    - 防止修改最后一个管理员的角色
    
    参数：
    - target_user_id: 目标用户ID
    - next_role: 新角色（修改角色时）
    - deleting: 是否删除操作
    
    返回值：
    - True: 可以执行操作
    - False: 不能执行操作（会破坏系统管理员）
    """
    admin_count = User.query.filter_by(role="admin").count()
    if deleting and target_user_id:
        target = db.session.get(User, target_user_id)
        if target and target.role == "admin" and admin_count <= 1:
            return False
    if target_user_id and next_role and next_role != "admin":
        target = db.session.get(User, target_user_id)
        if target and target.role == "admin" and admin_count <= 1:
            return False
    return True


@users_bp.get("")
@jwt_required_custom
@role_required("admin", "user", "viewer")
def list_users():
    current_user = g.current_user
    
    if current_user.role == "viewer":
        user = db.session.get(User, current_user.id)
        if not user:
            return err("用户不存在", code=404, http_status=404)
        return ok({
            "items": [{
                "id": user.id,
                "username": user.username,
                "role": user.role,
                "display_name": user.display_name
            }],
            "total": 1,
            "page": 1,
            "size": 20
        })
    
    page = max(int(request.args.get("page", 1)), 1)
    size = min(max(int(request.args.get("size", 20)), 1), 200)
    q = User.query.order_by(User.id.asc())
    p = q.paginate(page=page, per_page=size, error_out=False)
    items = [{"id": u.id, "username": u.username, "role": u.role, "display_name": u.display_name} for u in p.items]
    return ok({"items": items, "total": p.total, "page": page, "size": size})


@users_bp.post("")
@jwt_required_custom
@role_required("admin")
def create_user():
    data = request.get_json(silent=True) or {}
    username = str(data.get("username") or "").strip()
    password = data.get("password") or ""
    role = _normalize_role(data.get("role") or "user")
    display_name = str(data.get("display_name") or "").strip()[:128] or username
    if not username:
        return err("用户名不能为空")
    if len(password) < 6:
        return err("密码长度至少 6 位")
    if role not in VALID_ROLES:
        return err("role 必须是 admin/user/viewer")
    if User.query.filter_by(username=username).first():
        return err("用户名已存在")
    row = User(username=username, password_hash=hash_password(password), role=role, display_name=display_name)
    db.session.add(row)
    db.session.commit()
    return ok({"id": row.id, "username": row.username, "role": row.role, "display_name": row.display_name}, "用户创建成功")


@users_bp.put("/<int:user_id>")
@jwt_required_custom
@role_required("admin", "user", "viewer")
def update_user(user_id: int):
    current_user = g.current_user
    
    if current_user.role in ["user", "viewer"] and current_user.id != user_id:
        return err("只能修改自己的信息", code=403, http_status=403)
    
    row = db.session.get(User, user_id)
    if not row:
        return err("用户不存在", code=404, http_status=404)
    
    data = request.get_json(silent=True) or {}
    
    if current_user.role in ["user", "viewer"]:
        if "display_name" in data:
            row.display_name = str(data.get("display_name") or "").strip()[:128]
        if data.get("password"):
            if len(data.get("password") or "") < 6:
                return err("密码长度至少 6 位")
            row.password_hash = hash_password(data.get("password"))
    else:
        if "display_name" in data:
            row.display_name = str(data.get("display_name") or "").strip()[:128]
        if "role" in data:
            role = _normalize_role(data.get("role"))
            if role not in VALID_ROLES:
                return err("role 必须是 admin/user/viewer")
            if not _ensure_last_admin_kept(target_user_id=user_id, next_role=role):
                return err("系统至少需要保留 1 个管理员")
            row.role = role
        if data.get("password"):
            if len(data.get("password") or "") < 6:
                return err("密码长度至少 6 位")
            row.password_hash = hash_password(data.get("password"))
    
    db.session.commit()
    return ok({"id": row.id, "username": row.username, "role": row.role, "display_name": row.display_name}, "用户更新成功")


@users_bp.delete("/<int:user_id>")
@jwt_required_custom
@role_required("admin")
def delete_user(user_id: int):
    if g.current_user.id == user_id:
        return err("不能删除当前登录账号")
    row = db.session.get(User, user_id)
    if not row:
        return err("用户不存在", code=404, http_status=404)
    if not _ensure_last_admin_kept(target_user_id=user_id, deleting=True):
        return err("系统至少需要保留 1 个管理员")
    db.session.delete(row)
    db.session.commit()
    return ok(message="用户删除成功")


@users_bp.put("/me")
@jwt_required_custom
def update_me():
    data = request.get_json(silent=True) or {}
    user = g.current_user
    if "display_name" in data:
        user.display_name = str(data.get("display_name") or "").strip()[:128]
    if data.get("password"):
        if len(data["password"]) < 6:
            return err("密码长度至少 6 位")
        user.password_hash = hash_password(data["password"])
    db.session.commit()
    return ok({"id": user.id, "username": user.username, "role": user.role, "display_name": user.display_name}, "个人信息已更新")


@users_bp.put("/<int:user_id>/role")
@jwt_required_custom
@role_required("admin")
def update_user_role(user_id: int):
    role = _normalize_role((request.get_json(silent=True) or {}).get("role", ""))
    if role not in VALID_ROLES:
        return err("role 必须是 admin/user/viewer")
    user = db.session.get(User, user_id)
    if not user:
        return err("用户不存在", code=404, http_status=404)
    if not _ensure_last_admin_kept(target_user_id=user_id, next_role=role):
        return err("系统至少需要保留 1 个管理员")
    user.role = role
    db.session.commit()
    return ok({"id": user.id, "username": user.username, "role": user.role}, "角色更新成功")
