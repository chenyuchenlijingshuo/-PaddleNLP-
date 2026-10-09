"""
舆情分析系统 - Flask应用入口
==============================

该模块是舆情分析系统的核心入口文件，负责：
1. 初始化Flask应用及扩展（数据库、JWT、CORS）
2. 注册所有API蓝图路由
3. 创建数据库表结构
4. 初始化定时任务调度器
5. 确保默认管理员账户存在

技术栈：
- Flask: Web框架
- Flask-SQLAlchemy: ORM数据库操作
- Flask-JWT-Extended: JWT身份认证
- Flask-CORS: 跨域资源共享
"""

from flask import Flask
from flask_cors import CORS

from config import Config
from extensions import db, jwt
from models import *  # noqa: F401,F403
from routes.alert import alert_bp
from routes.analyze import analyze_bp
from routes.auth import auth_bp
from routes.collect import collect_bp
from routes.dashboard import dashboard_bp
from routes.process import process_bp
from routes.users import users_bp
from tasks.scheduler import init_scheduler
from utils.security import hash_password


def ensure_default_admin():
    """
    确保系统中存在默认管理员账户
    
    功能说明：
    - 检查数据库中是否存在用户
    - 如果不存在，创建默认管理员账户
    - 支持通过环境变量自定义管理员用户名和密码
    
    环境变量：
    - DEFAULT_ADMIN_USERNAME: 管理员用户名（默认：admin）
    - DEFAULT_ADMIN_PASSWORD: 管理员密码（默认：admin123456）
    
    安全说明：
    - 密码长度至少6位，不足时使用默认密码
    - 密码使用Bcrypt加密存储
    """
    import os

    if User.query.count() > 0:
        return
    username = (os.getenv("DEFAULT_ADMIN_USERNAME") or "admin").strip()
    password = os.getenv("DEFAULT_ADMIN_PASSWORD") or "admin123456"
    if len(password) < 6:
        password = "admin123456"
    user = User(
        username=username,
        password_hash=hash_password(password),
        role="admin",
        display_name="Administrator",
    )
    db.session.add(user)
    db.session.commit()


def create_app():
    """
    Flask应用工厂函数
    
    功能说明：
    - 创建并配置Flask应用实例
    - 初始化数据库、JWT、CORS等扩展
    - 注册所有API蓝图路由
    - 创建数据库表结构
    - 初始化定时任务调度器
    
    路由说明：
    - /api/auth: 身份认证相关接口（登录、注册）
    - /api/users: 用户管理接口
    - /api/collect: 数据采集接口
    - /api/process: 数据处理接口
    - /api/analyze: 数据分析接口
    - /api/alert: 预警管理接口
    - /api/dashboard: 首页总览接口
    
    返回值：
    - Flask应用实例
    """
    app = Flask(__name__)
    app.config.from_object(Config)

    # 初始化扩展
    db.init_app(app)
    jwt.init_app(app)
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    # 注册API蓝图
    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(users_bp, url_prefix="/api/users")
    app.register_blueprint(collect_bp, url_prefix="/api/collect")
    app.register_blueprint(process_bp, url_prefix="/api/process")
    app.register_blueprint(analyze_bp, url_prefix="/api/analyze")
    app.register_blueprint(alert_bp, url_prefix="/api/alert")
    app.register_blueprint(dashboard_bp, url_prefix="/api/dashboard")

    # 注册Flask CLI命令：创建数据库表
    @app.cli.command("create_tables")
    def create_tables():
        """Flask CLI命令：创建所有数据库表"""
        with app.app_context():
            db.create_all()
            print("database tables created.")

    # 应用启动时初始化
    with app.app_context():
        db.create_all()  # 创建数据库表
        ensure_default_admin()  # 确保默认管理员存在
        init_scheduler(app)  # 初始化定时任务调度器

    # 健康检查接口
    @app.get("/api/health")
    def health():
        """
        健康检查接口
        
        功能说明：
        - 用于监控系统运行状态
        - 可用于负载均衡健康检查
        
        返回值：
        - code: 状态码（0表示成功）
        - message: 状态消息
        - data: 详细状态信息
        """
        return {"code": 0, "message": "ok", "data": {"status": "up"}}, 200

    return app


# 创建Flask应用实例
app = create_app()

if __name__ == "__main__":
    # 开发模式启动服务器
    app.run(host="0.0.0.0", port=5000, debug=True)
