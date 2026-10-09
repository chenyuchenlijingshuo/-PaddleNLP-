"""
舆情分析系统 - 用户数据模型
============================

该模块定义用户相关的数据模型，包括：
1. User: 用户账户模型
2. LoginLog: 登录日志模型

数据模型说明：
- User: 存储用户账户信息，包括用户名、密码哈希、角色等
- LoginLog: 记录用户登录日志，包括IP、User-Agent、成功状态等

角色类型：
- admin: 管理员，拥有所有权限
- user: 普通用户，可采集、处理、分析数据
- viewer: 查看者，只能查看数据

关联关系：
- User.login_logs: 用户的所有登录日志
- LoginLog.user: 登录日志所属用户
"""

from datetime import datetime

from extensions import db


class User(db.Model):
    """
    用户账户模型
    
    字段说明：
    - id: 用户ID（主键）
    - username: 用户名（唯一，必填，索引）
    - password_hash: 密码哈希值（必填）
    - role: 用户角色（admin/user/viewer，默认user）
    - display_name: 显示名称
    - created_at: 创建时间
    
    关联关系：
    - login_logs: 用户的所有登录日志
    """
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(
        db.String(32), nullable=False, default="user"
    )  # admin | user | viewer
    display_name = db.Column(db.String(128))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # 关联登录日志
    login_logs = db.relationship(
        "LoginLog", backref="user", lazy="dynamic", cascade="all, delete-orphan"
    )


class LoginLog(db.Model):
    """
    登录日志模型
    
    字段说明：
    - id: 日志ID（主键）
    - user_id: 用户ID（外键）
    - ip: 登录IP地址
    - user_agent: 浏览器User-Agent
    - success: 登录是否成功
    - message: 日志消息
    - created_at: 创建时间（索引）
    
    关联关系：
    - user: 所属用户
    """
    __tablename__ = "login_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    ip = db.Column(db.String(64))
    user_agent = db.Column(db.String(512))
    success = db.Column(db.Boolean, default=True)
    message = db.Column(db.String(256))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
