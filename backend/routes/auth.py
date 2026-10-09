"""
舆情分析系统 - 身份认证路由
============================

该模块负责用户身份认证相关的API接口，包括：
1. 用户注册
2. 用户登录
3. 获取当前用户信息
4. 查询登录日志（管理员权限）

技术实现：
- JWT令牌认证：使用Flask-JWT-Extended生成访问令牌
- 密码加密：使用Bcrypt算法加密存储密码
- 密码验证：至少6位，必须包含字母和数字
- 登录日志：记录用户登录IP、User-Agent、成功/失败状态

API接口：
- POST /api/auth/register: 用户注册
- POST /api/auth/login: 用户登录
- GET /api/auth/me: 获取当前用户信息
- GET /api/auth/login-logs: 查询登录日志（管理员权限）
"""

from datetime import datetime

from flask import Blueprint, g, request
from flask_jwt_extended import create_access_token

from decorators import jwt_required_custom, role_required
from extensions import db
from models import LoginLog, User
from utils.response import err, ok
from utils.security import hash_password, verify_password

auth_bp = Blueprint("auth", __name__)


def _client_ip():
    """
    获取客户端真实IP地址
    
    功能说明：
    - 优先从X-Forwarded-For头部获取（反向代理场景）
    - 回退到request.remote_addr（直连场景）
    
    返回值：
    - 客户端IP地址字符串
    """
    xff = request.headers.get("X-Forwarded-For", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.remote_addr or "unknown"


@auth_bp.post("/register")
def register():
    """
    用户注册接口
    
    功能说明：
    - 接收用户注册信息
    - 验证用户名、密码、角色
    - 创建用户账户
    
    参数说明：
    - username: 用户名（必填）
    - password: 密码（必填，至少6位，必须包含字母和数字）
    - display_name: 显示名（可选，默认使用用户名）
    - role: 角色（可选，默认user，只能是user或viewer）
    
    返回值：
    - 成功：返回用户ID、用户名、角色
    - 失败：返回错误信息
    """
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    display_name = (data.get("display_name") or "").strip() or username
    role = (data.get("role") or "user").strip()
    
    # 验证必填字段
    if not username or not password:
        return err("用户名和密码不能为空")
    
    # 验证密码长度
    if len(password) < 6:
        return err("密码长度至少 6 位")
    
    # 验证密码复杂度：必须包含字母和数字
    has_letter = any(c.isalpha() for c in password)
    has_number = any(c.isdigit() for c in password)
    if not has_letter or not has_number:
        return err("密码必须包含字母和数字")
    
    # 验证角色：注册时只能选择user或viewer
    if role not in ["user", "viewer"]:
        return err("角色只能是 user 或 viewer")
    
    # 检查用户名是否已存在
    if User.query.filter_by(username=username).first():
        return err("用户名已存在")
    
    # 创建用户
    user = User(
        username=username, 
        password_hash=hash_password(password), 
        role=role, 
        display_name=display_name
    )
    db.session.add(user)
    db.session.commit()
    return ok({"id": user.id, "username": user.username, "role": user.role}, "注册成功")


@auth_bp.post("/login")
def login():
    """
    用户登录接口
    
    功能说明：
    - 验证用户名和密码
    - 生成JWT访问令牌
    - 记录登录日志
    
    参数说明：
    - username: 用户名
    - password: 密码
    
    返回值：
    - 成功：返回JWT令牌和用户信息
    - 失败：返回错误信息
    
    安全措施：
    - 记录登录IP和User-Agent
    - 记录登录成功/失败状态
    - 密码使用Bcrypt验证
    """
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    
    # 查询用户并验证密码
    user = User.query.filter_by(username=username).first()
    success = bool(user and verify_password(password, user.password_hash))
    
    # 记录登录日志
    log = LoginLog(
        user_id=user.id if user else None,
        ip=_client_ip(),
        user_agent=request.headers.get("User-Agent", "")[:512],
        success=success,
        message="login success" if success else "invalid credentials",
    )
    db.session.add(log)
    
    if not success:
        db.session.commit()
        return err("用户名或密码错误", code=401, http_status=401)
    
    # 生成JWT令牌
    token = create_access_token(identity=str(user.id))
    db.session.commit()
    return ok({"access_token": token, "user": {"id": user.id, "username": user.username, "role": user.role}}, "登录成功")


@auth_bp.get("/me")
@jwt_required_custom
def me():
    """
    获取当前登录用户信息
    
    功能说明：
    - 返回当前登录用户的详细信息
    - 需要JWT认证
    
    返回值：
    - 用户ID、用户名、角色、显示名
    """
    user = g.current_user
    return ok({"id": user.id, "username": user.username, "role": user.role, "display_name": user.display_name})


@auth_bp.get("/login-logs")
@jwt_required_custom
@role_required("admin")
def login_logs():
    """
    查询登录日志（管理员权限）
    
    功能说明：
    - 分页查询所有用户的登录日志
    - 仅管理员可访问
    - 按时间倒序排列
    
    参数说明：
    - page: 页码（默认1）
    - size: 每页数量（默认20，最大100）
    
    返回值：
    - 登录日志列表，包含用户名、IP、成功状态、时间等
    """
    page = max(int(request.args.get("page", 1)), 1)
    size = min(max(int(request.args.get("size", 20)), 1), 100)
    q = LoginLog.query.order_by(LoginLog.created_at.desc())
    p = q.paginate(page=page, per_page=size, error_out=False)
    items = []
    for row in p.items:
        items.append(
            {
                "id": row.id,
                "user_id": row.user_id,
                "username": row.user.username if row.user else None,
                "ip": row.ip,
                "success": row.success,
                "message": row.message,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
        )
    return ok({"items": items, "total": p.total, "page": page, "size": size, "server_time": datetime.utcnow().isoformat()})
