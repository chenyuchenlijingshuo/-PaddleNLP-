"""
舆情分析系统 - 配置管理
========================

该模块负责管理系统的所有配置项，包括：
1. Flask应用配置（密钥、数据库等）
2. JWT认证配置（密钥、过期时间）
3. 数据库配置（连接字符串、连接池）
4. 采集配置（限流参数）

配置来源：
- 优先从环境变量读取
- 使用默认值作为后备

环境变量配置：
- SECRET_KEY: Flask应用密钥
- JWT_SECRET_KEY: JWT签名密钥
- JWT_ACCESS_HOURS: JWT访问令牌有效期（小时）
- DATABASE_URI: 数据库连接字符串
- COLLECT_MAX_REQUESTS_PER_MINUTE: 采集请求每分钟最大次数
"""

import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

# 加载.env文件中的环境变量
load_dotenv()

# 项目根目录
BASE_DIR = Path(__file__).resolve().parent


class Config:
    """
    Flask应用配置类
    
    该类包含所有系统配置项，支持通过环境变量自定义配置。
    配置项说明：
    - SECRET_KEY: Flask应用密钥，用于session签名等安全功能
    - JWT_SECRET_KEY: JWT令牌签名密钥
    - JWT_ACCESS_TOKEN_EXPIRES: JWT访问令牌有效期
    - SQLALCHEMY_DATABASE_URI: 数据库连接字符串
    - SQLALCHEMY_TRACK_MODIFICATIONS: 是否追踪对象修改
    - COLLECT_MAX_REQUESTS_PER_MINUTE: 采集限流参数
    """
    
    # Flask应用密钥
    # 用途：session签名、CSRF保护等安全功能
    # 建议：生产环境必须使用强随机密钥
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
    
    # JWT认证配置
    # JWT_SECRET_KEY: 用于签名JWT令牌的密钥
    # JWT_ACCESS_TOKEN_EXPIRES: 访问令牌有效期（默认24小时）
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-jwt-secret")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=int(os.getenv("JWT_ACCESS_HOURS", "24")))

    # 数据库配置
    # SQLALCHEMY_DATABASE_URI: 数据库连接字符串
    # - 默认使用SQLite数据库（开发环境）
    # - 生产环境建议使用MySQL/PostgreSQL
    # SQLALCHEMY_TRACK_MODIFICATIONS: 是否追踪对象修改（建议False以节省内存）
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URI",
        f"sqlite:///{BASE_DIR / 'instance' / 'app.db'}",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # 数据库连接池配置（仅MySQL）
    # pool_pre_ping: 启用连接健康检查
    # pool_recycle: 连接回收时间（秒）
    SQLALCHEMY_ENGINE_OPTIONS = (
        {"pool_pre_ping": True, "pool_recycle": 3600}
        if "mysql" in os.getenv("DATABASE_URI", "").lower()
        else {}
    )

    # 采集配置
    # COLLECT_MAX_REQUESTS_PER_MINUTE: 每分钟最大采集请求数
    # 用途：防止采集频率过高导致IP被封禁
    COLLECT_MAX_REQUESTS_PER_MINUTE = int(
        os.getenv("COLLECT_MAX_REQUESTS_PER_MINUTE", "30")
    )
