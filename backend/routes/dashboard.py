"""
舆情分析系统 - 首页总览路由
============================

该模块负责首页总览相关的API接口，包括：
1. 系统概览数据
2. 热点关键词
3. 预警信息
4. 来源分布
5. 统计指标

数据内容：
- 采集总量：原始数据总数
- 预警数量：预警记录总数
- 热点词数：热点关键词数量
- 融合记录：融合数据总数
- 热点关键词列表：TOP关键词及热度
- 预警记录列表：最近的预警信息
- 来源分布：新闻和微博数据占比

API接口：
- GET /api/dashboard/overview: 获取系统概览数据
"""

from flask import Blueprint

from decorators import jwt_required_custom
from services.dashboard_service import build_dashboard_snapshot
from utils.response import ok

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.get("/overview")
@jwt_required_custom
def overview():
    """
    获取系统概览数据
    
    功能说明：
    - 返回首页所需的所有统计数据
    - 包括采集总量、预警数量、热点词数等
    - 包括热点关键词、预警记录、来源分布等详细数据
    
    返回值：
    - 系统概览数据对象
    """
    return ok(build_dashboard_snapshot())
