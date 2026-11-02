"""
舆情分析系统 - 处理页 Python 工作台
=====================================

使用 pandas / numpy / matplotlib 实现「处理」页的预处理与融合工作台，
通过 Dash 挂载到 Flask 的 /python-process/ 路径，由前端 ProcessView
以 iframe 方式嵌入。

功能：
1. 执行预处理与融合
2. 查看融合结果（分页表格）
3. 融合配置读取、保存、恢复默认
4. matplotlib 服务端渲染融合排行与趋势图
5. 管理员导出融合数据 CSV
"""

import base64
import io
import logging
import math
from datetime import datetime

import matplotlib

matplotlib.use("Agg")
import matplotlib as mpl
import numpy as np
import pandas as pd
import requests as http
from dash import Dash, Input, Output, State, callback_context, dcc, html, no_update
from flask import jsonify, request as flask_request, send_from_directory
from flask_jwt_extended import decode_token
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure

API_BASE = "http://127.0.0.1:5000/api"
FRONTEND_STYLES = "../frontend/src"

COLORS = {
    "text": "#eff5ff",
    "muted": "#9db0ce",
    "accent": "#79c0ff",
    "positive": "#21d0b2",
    "negative": "#ff6b9d",
    "grid": "rgba(161,191,255,0.08)",
}
DEFAULT_CONFIG = {"time_window_minutes": 60, "weight_news": 1.0, "weight_weibo": 0.8}

mpl.rcParams["font.family"] = ["PingFang SC", "Arial Unicode MS", "Hiragino Sans GB", "DejaVu Sans"]
mpl.rcParams["axes.unicode_minus"] = False
logging.getLogger("matplotlib.font_manager").setLevel(logging.ERROR)


def _api(token, method, path, **kwargs):
    """携带登录令牌请求后端 JSON 接口。"""
    response = http.request(
        method,
        f"{API_BASE}/{path.lstrip('/')}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=600,
        **kwargs,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("code") != 0:
        raise RuntimeError(payload.get("message") or "API 请求失败")
    return payload.get("data") or {}


def _role(token):
    try:
        return str(_api(token, "GET", "/auth/me").get("role") or "")
    except Exception:
        return ""


def _fmt_time(value):
    text = str(value or "").strip()
    return text.replace("T", " ")[:19] if text else "-"


def _new_figure(width=6.2, height=3.6):
    figure = Figure(figsize=(width, height), dpi=140)
    figure.patch.set_alpha(0)
    FigureCanvasAgg(figure)
    return figure


def _finish(figure):
    buffer = io.BytesIO()
    figure.savefig(buffer, format="png", transparent=True, facecolor="none", bbox_inches="tight")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _empty_chart(message):
    figure = _new_figure()
    axis = figure.add_subplot(111)
    axis.axis("off")
    axis.text(0.5, 0.5, message, transform=axis.transAxes, ha="center", va="center", color=COLORS["muted"], fontsize=12, linespacing=1.6)
    return _finish(figure)


def _style_axis(axis, xlabel="", ylabel=""):
    axis.set_facecolor((0, 0, 0, 0))
    for spine in axis.spines.values():
        spine.set_visible(False)
    axis.tick_params(colors=COLORS["muted"], labelsize=9, length=0)
    axis.grid(True, color="white", alpha=0.07, linewidth=0.8)
    axis.set_axisbelow(True)
    if xlabel:
        axis.set_xlabel(xlabel, color=COLORS["muted"], fontsize=10)
    if ylabel:
        axis.set_ylabel(ylabel, color=COLORS["muted"], fontsize=10)
    axis.title.set_color(COLORS["text"])
    axis.title.set_fontsize(12)


def _ranking_chart(frame):
    """横向柱状图：融合分值 TOP 12。"""
    if frame is None or frame.empty:
        return _empty_chart("暂无 iPhone Duo 议题数据\n请先执行融合")
    top = frame.dropna(subset=["fused_score"]).sort_values("fused_score", ascending=True).tail(12)
    if top.empty:
        return _empty_chart("暂无 iPhone Duo 议题数据\n请先执行融合")
    labels = [text if len(text) <= 12 else f"{text[:12]}…" for text in top["keyword"].astype(str)]
    values = top["fused_score"].to_numpy(dtype=float)
    figure = _new_figure(6.2, 3.9)
    axis = figure.add_subplot(111)
    colors = mpl.colormaps["Blues"](np.linspace(0.38, 0.86, len(values)))
    positions = np.arange(len(values))
    axis.barh(positions, values, height=0.62, color=colors, edgecolor="none")
    axis.set_yticks(positions)
    axis.set_yticklabels(labels, color=COLORS["text"], fontsize=9)
    _style_axis(axis, xlabel="融合热度")
    axis.set_title("iPhone Duo 议题热度排行（TOP 12）", pad=12)
    limit = float(values.max()) if values.size else 0.0
    axis.set_xlim(0, limit * 1.16 if limit > 0 else 1)
    for index, value in enumerate(values):
        axis.text(value + limit * 0.015, index, f"{value:.2f}", va="center", color=COLORS["muted"], fontsize=8)
    return _finish(figure)


def _trend_chart(frame):
    """折线图：按融合时间窗口汇总分值。"""
    if frame is None or frame.empty:
        return _empty_chart("暂无 iPhone Duo 议题趋势数据")
    data = frame.copy()
    data["window_start"] = pd.to_datetime(data["window_start"], errors="coerce")
    data = data.dropna(subset=["window_start"])
    if data.empty:
        return _empty_chart("暂无 iPhone Duo 议题趋势数据")
    grouped = (
        data.groupby("window_start", as_index=False)
        .agg(fused_score=("fused_score", "sum"))
        .sort_values("window_start")
        .tail(10)
    )
    values = grouped["fused_score"].to_numpy(dtype=float)
    positions = np.arange(len(values))
    figure = _new_figure(6.2, 3.9)
    axis = figure.add_subplot(111)
    axis.plot(
        positions,
        values,
        color=COLORS["accent"],
        linewidth=2.4,
        marker="o",
        markersize=6,
        markerfacecolor=COLORS["positive"],
        markeredgecolor="none",
    )
    axis.fill_between(positions, values, 0, color=COLORS["accent"], alpha=0.16)
    labels = grouped["window_start"].dt.strftime("%m-%d %H:%M").tolist()
    axis.set_xticks(positions)
    axis.set_xticklabels(labels, rotation=28, ha="right", fontsize=8, color=COLORS["muted"])
    _style_axis(axis, xlabel="融合时间窗口", ylabel="议题融合总分")
    axis.set_title("iPhone Duo 议题热度趋势", pad=12)
    bottom = float(values.min()) if values.size else 0.0
    top = float(values.max()) if values.size else 0.0
    span = top - min(bottom, 0.0)
    axis.set_ylim(min(bottom, 0.0) - span * 0.12 if span else 0, top + span * 0.22 if span else 1)
    if values.size:
        index = int(np.argmax(values))
        axis.annotate(
            f"峰值 {values[index]:.2f}",
            xy=(positions[index], values[index]),
            xytext=(8, 12),
            textcoords="offset points",
            color=COLORS["positive"],
            fontsize=9,
        )
    return _finish(figure)


def _table(rows):
    headers = ["ID", "议题关键词", "融合热度", "时间窗口开始"]
    head = html.Thead(html.Tr([html.Th(value) for value in headers]))
    body_rows = []
    for row in rows:
        body_rows.append(
            html.Tr([
                html.Td(row.get("id", "")),
                html.Td(row.get("keyword") or "", className="python-title-cell"),
                html.Td(f"{float(row.get('fused_score') or 0):.2f}"),
                html.Td(_fmt_time(row.get("window_start"))),
            ])
        )
    return html.Div(html.Table([head, html.Tbody(body_rows)], className="python-data-table"), className="table-shell python-table-shell")


def _formula(weight_news, weight_weibo):
    return [
        html.Span("议题热度", className="formula-var"),
        html.Span("=", className="formula-op"),
        html.Span("新闻数量", className="formula-var"),
        html.Span("×", className="formula-op"),
        html.Span(f"{weight_news:g}", className="formula-val"),
        html.Span("+", className="formula-op"),
        html.Span("微博数量", className="formula-var"),
        html.Span("×", className="formula-op"),
        html.Span(f"{weight_weibo:g}", className="formula-val"),
    ]


def _metric(label, element_id, initial):
    return html.Div([html.Span(label), html.Strong(initial, id=element_id)], className="metric-card")


def _layout():
    metrics = html.Div([
        _metric("首销议题数", "p-total", "0"),
        _metric("平均热度", "p-average", "0.00"),
        _metric("最高热度", "p-max", "0.00"),
        _metric("当前页", "p-page-metric", "第 1 / 1 页"),
    ], className="metric-grid metric-grid-quad")

    actions = html.Div([
        html.Div([html.P("操作", className="mini-label"), html.H3("处理流程")], className="section-title"),
        html.Div([
            html.Button("执行预处理", id="preprocess-button", className="el-button el-button--primary"),
            html.Button("执行融合", id="fusion-button", className="el-button el-button--success"),
            html.Button("刷新数据", id="refresh-button", className="el-button"),
            html.Button("导出数据", id="export-button", className="el-button export-btn"),
        ], className="toolbar"),
        html.P("预处理后再执行融合，融合热度用于衡量 iPhone Duo 首销期间价格、影像、供货等议题的讨论集中度。", className="panel-note"),
        html.Div(id="action-message", className="panel-note process-message"),
        html.Div(id="export-message", className="panel-note process-message"),
    ], className="glass-panel")

    config_cards = html.Div([
        html.Div([
            html.Div("⏱️", className="config-icon"),
            html.Div([html.H4("时间窗口"), html.P("筛选最近 N 分钟的 iPhone Duo 首销讨论进行融合")], className="config-title"),
        ], className="config-card-header"),
        html.Div([
            dcc.Input(id="p-time-window", type="number", min=5, max=480, step=5, value=60, className="python-input-number"),
            html.Span("分钟", className="config-unit"),
        ], className="config-card-body"),
    ], className="config-card")

    config_weights = html.Div([
        html.Div([
            html.Div("📰", className="config-icon"),
            html.Div([html.H4("新闻权重"), html.P("新闻样本在 iPhone Duo 议题融合热度中的权重系数")], className="config-title"),
        ], className="config-card-header"),
        html.Div([
            dcc.Input(id="p-weight-news", type="number", min=0.1, max=3.0, step=0.1, value=1.0, className="python-input-number"),
            html.Span("倍", className="config-unit"),
        ], className="config-card-body"),
    ], className="config-card")

    config_weibo = html.Div([
        html.Div([
            html.Div("💬", className="config-icon"),
            html.Div([html.H4("微博权重"), html.P("微博讨论在 iPhone Duo 议题融合热度中的权重系数")], className="config-title"),
        ], className="config-card-header"),
        html.Div([
            dcc.Input(id="p-weight-weibo", type="number", min=0.1, max=3.0, step=0.1, value=0.8, className="python-input-number"),
            html.Span("倍", className="config-unit"),
        ], className="config-card-body"),
    ], className="config-card")

    config = html.Div([
        html.Div([
            html.Div([html.P("配置", className="mini-label"), html.H3("融合配置"), html.P("调整首销议题融合的时间范围与新闻、微博权重。")]),
            html.Div(id="config-role-tag", className="config-header-actions"),
        ], className="section-title"),
        html.Div([config_cards, config_weights, config_weibo], className="fusion-config-grid"),
        html.Div([
            html.Div([
                html.Div("📊 iPhone Duo 议题热度计算公式", className="formula-label"),
                html.Div(_formula(DEFAULT_CONFIG["weight_news"], DEFAULT_CONFIG["weight_weibo"]), id="formula-weights", className="formula-equation"),
            ], className="formula-box"),
            html.Div([
                html.Button("保存配置", id="save-config-button", className="el-button el-button--primary save-btn", disabled=True),
                html.Button("恢复默认", id="reset-config-button", className="el-button reset-btn", disabled=True),
            ], className="config-actions"),
        ], className="config-footer"),
        html.Div(id="config-message", className="panel-note process-message"),
    ], className="glass-panel")

    ranking = html.Div([
        html.Div([html.P("议题排行", className="mini-label"), html.H3("iPhone Duo 议题热度排行"), html.P("按融合热度排序，快速识别首销期间讨论最集中的产品议题。")], className="section-title"),
        html.Div(id="rank-chart"),
    ], className="glass-panel")

    trend = html.Div([
        html.Div([html.P("传播变化", className="mini-label"), html.H3("iPhone Duo 议题热度趋势"), html.P("按融合时间窗口汇总议题热度，观察首销讨论的起伏与变化。")], className="section-title"),
        html.Div(id="trend-chart"),
    ], className="glass-panel")

    results = html.Div([
        html.Div([html.P("结果", className="mini-label"), html.H3("iPhone Duo 议题融合结果")], className="section-title"),
        html.Div(id="result-table"),
        html.Div([
            html.Div(id="pager-info", className="panel-note pager-info"),
            dcc.Dropdown(
                id="page-size",
                options=[{"label": f"{size} 条/页", "value": size} for size in (10, 20, 50, 100, 200)],
                value=20,
                clearable=False,
                className="python-select page-size-select",
            ),
            html.Button("上一页", id="prev-page", className="el-button", disabled=True),
            html.Button("下一页", id="next-page", className="el-button", disabled=True),
        ], className="pager-bar python-pager"),
    ], className="glass-panel")

    content = [
        html.Div([
            html.Div([
                html.P("处理", className="eyebrow"),
                html.H3("预处理与融合"),
                html.P("围绕 iPhone Duo 首销事件清洗微博与新闻样本，融合价格、影像、供货等议题热度。"),
            ]),
        ], className="section-title"),
        metrics,
        actions,
        config,
        html.Div([ranking, trend], className="split-grid"),
        results,
    ]
    return html.Div([
        dcc.Location(id="process-url", refresh=False),
        dcc.Store(id="page-store", data={"page": 1, "size": 20}),
        dcc.Download(id="process-download"),
        html.Section(html.Div(content, className="panel-stack"), className="view-shell python-process-view"),
    ])


def _guard(message):
    chart = _empty_chart(message)
    return (
        "0", "0.00", "0.00", "第 1 / 1 页",
        html.Span(message, className="empty-note"),
        chart, chart,
        html.P(message, className="empty-note"),
        "", {"page": 1, "size": 20},
        True, True, True,
    )


def _clamp_number(value, minimum, maximum, default):
    try:
        return min(max(float(value), minimum), maximum)
    except (TypeError, ValueError):
        return default


def init_python_process(server):
    @server.route("/python-process/session", methods=["POST", "DELETE"])
    def sync_python_process_session():
        if flask_request.method == "DELETE":
            response = jsonify({"ok": True})
            response.delete_cookie("python_process_token", path="/python-process", samesite="Strict")
            return response
        authorization = flask_request.headers.get("Authorization", "")
        token = authorization[7:].strip() if authorization.startswith("Bearer ") else ""
        try:
            decode_token(token)
        except Exception:
            return jsonify({"message": "登录状态无效"}), 401
        response = jsonify({"ok": True})
        response.set_cookie(
            "python_process_token",
            token,
            max_age=86400,
            httponly=True,
            secure=flask_request.is_secure,
            samesite="Strict",
            path="/python-process",
        )
        return response

    @server.get("/python-process/styles.css")
    def python_process_styles():
        return send_from_directory(FRONTEND_STYLES, "styles.css")

    dash_app = Dash(
        "python_process",
        server=server,
        url_base_pathname="/python-process/",
        title="处理工作台",
        update_title=None,
        suppress_callback_exceptions=False,
    )
    dash_app.index_string = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  {%metas%}<title>{%title%}</title>{%favicon%}{%css%}
  <link rel="stylesheet" href="/python-process/styles.css">
  <style>
  html,body{min-height:100%;margin:0}body{overflow-x:hidden}
  .python-process-view{margin:0;min-height:100vh}
  .python-process-view .section-title{align-items:flex-end}
  .python-process-view .el-button{cursor:pointer}
  .python-process-view .el-button:disabled{opacity:.55;cursor:not-allowed}
  .python-process-view .el-button--success{background:linear-gradient(135deg,#1cc6b7,#43e97b)!important;border:none!important}
  .python-process-view .python-input-number{width:100%;color:#eff5ff;background:rgba(4,12,22,.55);border:1px solid rgba(161,191,255,.18);border-radius:10px;padding:10px 12px;min-height:42px;font:inherit}
  .python-process-view .fusion-config-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:18px;margin:20px 0}
  .python-process-view .config-card{background:linear-gradient(135deg,rgba(121,192,255,.05),rgba(33,208,178,.03));border:1px solid rgba(121,192,255,.15);border-radius:16px;padding:18px;transition:all .3s ease}
  .python-process-view .config-card:hover{border-color:rgba(121,192,255,.32);box-shadow:0 8px 24px rgba(121,192,255,.15)}
  .python-process-view .config-card-header{display:flex;align-items:flex-start;gap:14px;margin-bottom:16px}
  .python-process-view .config-icon{width:44px;height:44px;display:flex;align-items:center;justify-content:center;background:linear-gradient(135deg,rgba(121,192,255,.15),rgba(33,208,178,.15));border-radius:12px;font-size:22px;flex:0 0 auto}
  .python-process-view .config-title h4{margin:0 0 6px;font-size:15px;color:#eff5ff}
  .python-process-view .config-title p{margin:0;font-size:12.5px;line-height:1.5;color:#9db0ce}
  .python-process-view .config-card-body{display:flex;align-items:center;gap:10px}
  .python-process-view .config-unit{font-size:13px;color:#9db0ce;min-width:34px}
  .python-process-view .config-footer{margin-top:22px;padding-top:18px;border-top:1px solid rgba(121,192,255,.12)}
  .python-process-view .formula-box{background:linear-gradient(135deg,rgba(33,208,178,.08),rgba(121,192,255,.08));border:1px solid rgba(33,208,178,.2);border-radius:12px;padding:14px 18px;margin-bottom:18px}
  .python-process-view .formula-label{font-size:13px;font-weight:600;color:#83f2d1;margin-bottom:10px}
  .python-process-view .formula-equation{display:flex;flex-wrap:wrap;align-items:center;gap:8px;font-family:'Courier New',monospace}
  .python-process-view .formula-var{color:#eff5ff;font-size:14px;font-weight:500}
  .python-process-view .formula-op{color:#79c0ff;font-size:16px;font-weight:600}
  .python-process-view .formula-val{background:rgba(121,192,255,.15);color:#79c0ff;padding:2px 8px;border-radius:6px;font-weight:600;font-size:14px}
  .python-process-view .config-actions{display:flex;gap:12px;flex-wrap:wrap}
  .python-process-view .save-btn,.python-process-view .reset-btn{flex:1;min-width:140px;height:44px}
  .python-process-view .reset-btn{background:transparent;border:1px solid rgba(121,192,255,.3);color:#9db0ce}
  .python-process-view .export-btn{background:linear-gradient(135deg,#ff8b6a,#ff6b6b)!important;border:none!important;color:#fff}
  .python-process-view .python-tag{display:inline-flex;align-items:center;padding:8px 14px;border:1px solid rgba(33,208,178,.3);border-radius:8px;color:#83f2d1;background:rgba(33,208,178,.08);font-weight:600;font-size:13px}
  .python-process-view .python-tag-locked{border-color:rgba(161,191,255,.25);color:#9db0ce;background:rgba(161,191,255,.08)}
  .python-process-view .config-header-actions{display:flex;gap:10px;align-items:center}
  .python-process-view .python-chart-img{display:block;width:100%;border-radius:12px}
  .python-process-view .python-data-table{width:100%;border-collapse:collapse;min-width:640px;color:#eff5ff}
  .python-process-view .python-data-table th,.python-process-view .python-data-table td{padding:12px 14px;border-bottom:1px solid rgba(161,191,255,.1);text-align:left;vertical-align:top}
  .python-process-view .python-data-table th{color:#9db0ce;font-weight:600;white-space:nowrap}
  .python-process-view .python-data-table tbody tr:nth-child(even){background:rgba(255,255,255,.025)}
  .python-process-view .python-table-shell{overflow-x:auto}
  .python-process-view .python-title-cell{min-width:200px}
  .python-process-view .process-message{min-height:20px}
  .python-process-view .python-pager{display:flex;flex-wrap:wrap;align-items:center;gap:12px;padding:14px 4px 0}
  .python-process-view .pager-info{margin:0;flex:1;min-width:200px}
  .python-process-view .page-size-select{width:130px;min-height:38px;color:#eff5ff;background:rgba(4,12,22,.55);border:1px solid rgba(161,191,255,.18);border-radius:8px}
  .python-process-view .page-size-select .Select-control,.python-process-view .page-size-select .Select-menu-outer{background:#0d1a2b;color:#eff5ff;border-color:rgba(161,191,255,.18)}
  .python-process-view .page-size-select .Select-value-label,.python-process-view .page-size-select .Select-placeholder,.python-process-view .page-size-select .Select-arrow{color:#eff5ff!important}
  .python-process-view .python-error{color:#ff8b6a}
  .python-process-view .python-success{color:#83f2d1}
  @media(max-width:900px){.python-process-view .metric-grid-quad{grid-template-columns:repeat(2,minmax(0,1fr))}.python-process-view .split-grid{grid-template-columns:1fr}.python-process-view .section-title{align-items:flex-start;flex-direction:column}.python-process-view .config-actions{flex-direction:column}.python-process-view .save-btn,.python-process-view .reset-btn{width:100%}}
  </style>
</head>
<body><div id="react-entry-point">{%app_entry%}</div><footer>{%config%}{%scripts%}{%renderer%}</footer></body>
</html>"""
    dash_app.layout = _layout

    @dash_app.callback(
        Output("p-total", "children"),
        Output("p-average", "children"),
        Output("p-max", "children"),
        Output("p-page-metric", "children"),
        Output("action-message", "children"),
        Output("rank-chart", "children"),
        Output("trend-chart", "children"),
        Output("result-table", "children"),
        Output("pager-info", "children"),
        Output("page-store", "data"),
        Output("prev-page", "disabled"),
        Output("next-page", "disabled"),
        Output("export-button", "disabled"),
        Input("process-url", "pathname"),
        Input("preprocess-button", "n_clicks"),
        Input("fusion-button", "n_clicks"),
        Input("refresh-button", "n_clicks"),
        Input("prev-page", "n_clicks"),
        Input("next-page", "n_clicks"),
        Input("page-size", "value"),
        State("page-store", "data"),
    )
    def refresh_process(pathname, pre_clicks, fusion_clicks, refresh_clicks, prev_clicks, next_clicks, page_size, store):
        token = flask_request.cookies.get("python_process_token", "")
        if not token:
            return _guard("请先登录系统。")
        store = store or {}
        size = int(_clamp_number(page_size or store.get("size") or 20, 10, 200, 20))
        size = min((10, 20, 50, 100, 200), key=lambda value: abs(value - size))
        page = max(int(store.get("page") or 1), 1)
        triggered = {item["prop_id"] for item in callback_context.triggered}
        message = ""
        try:
            if "page-size.value" in triggered:
                page = 1
            elif "prev-page.n_clicks" in triggered:
                page = max(page - 1, 1)
            elif "next-page.n_clicks" in triggered:
                page += 1
            if "preprocess-button.n_clicks" in triggered:
                result = _api(token, "POST", "/process/preprocess/run")
                message = f"预处理完成：处理 {result.get('total', 0)} 条，更新 {result.get('updated', 0)} 条。"
            elif "fusion-button.n_clicks" in triggered:
                result = _api(token, "POST", "/process/fusion/run")
                message = f"融合完成：原始 {result.get('raw_count', 0)} 条，生成 {result.get('fused_count', 0)} 条。"
                page = 1
            elif "refresh-button.n_clicks" in triggered:
                message = "数据刷新成功。"
            elif "prev-page.n_clicks" in triggered or "next-page.n_clicks" in triggered or "page-size.value" in triggered:
                message = ""

            requested_page = page
            page_data = _api(token, "GET", "/process/fused", params={"page": page, "size": size})
            total = int(page_data.get("total") or 0)
            items = page_data.get("items") or []
            total_pages = max(1, math.ceil(total / size))
            page = min(max(page, 1), total_pages)
            if page != requested_page:
                page_data = _api(token, "GET", "/process/fused", params={"page": page, "size": size})
                items = page_data.get("items") or []

            chart_data = _api(token, "GET", "/process/fused", params={"page": 1, "size": 200})
            frame = pd.DataFrame(chart_data.get("items") or [])
            if not frame.empty:
                frame["fused_score"] = pd.to_numeric(frame["fused_score"], errors="coerce").fillna(0.0)
                scores = frame["fused_score"].to_numpy(dtype=float)
                average = float(np.mean(scores))
                maximum = float(np.max(scores))
            else:
                average = 0.0
                maximum = 0.0

            table = _table(items) if items else html.P("暂无 iPhone Duo 议题融合结果，请先执行融合。", className="empty-note")
            pager = f"显示 {len(items)} 条，共 {total} 条记录 · 第 {page} / {total_pages} 页" if total else ""
            is_admin = _role(token) == "admin"
            return (
                str(total), f"{average:.2f}", f"{maximum:.2f}", f"第 {page} / {total_pages} 页",
                html.Span(message, className="python-success") if message else "",
                html.Img(src=_ranking_chart(frame), className="python-chart-img"),
                html.Img(src=_trend_chart(frame), className="python-chart-img"),
                table, pager, {"page": page, "size": size},
                page <= 1, page >= total_pages, not is_admin,
            )
        except Exception as exc:
            return _guard(f"处理数据加载失败：{exc}")

    @dash_app.callback(
        Output("p-time-window", "value"),
        Output("p-weight-news", "value"),
        Output("p-weight-weibo", "value"),
        Output("config-message", "children"),
        Output("formula-weights", "children"),
        Output("config-role-tag", "children"),
        Output("save-config-button", "disabled"),
        Output("reset-config-button", "disabled"),
        Input("process-url", "pathname"),
        Input("save-config-button", "n_clicks"),
        Input("reset-config-button", "n_clicks"),
        State("p-time-window", "value"),
        State("p-weight-news", "value"),
        State("p-weight-weibo", "value"),
    )
    def manage_config(pathname, save_clicks, reset_clicks, time_window, weight_news, weight_weibo):
        token = flask_request.cookies.get("python_process_token", "")
        if not token:
            return 60, 1.0, 0.8, html.Span("请先登录系统。", className="empty-note"), _formula(1.0, 0.8), "", True, True
        triggered = {item["prop_id"] for item in callback_context.triggered}
        is_admin = _role(token) == "admin"
        tag = html.Span("✏️ 可修改" if is_admin else "🔒 仅管理员可修改", className=f"python-tag{'' if is_admin else ' python-tag-locked'}")
        message = ""
        try:
            if "reset-config-button.n_clicks" in triggered:
                time_window = DEFAULT_CONFIG["time_window_minutes"]
                weight_news = DEFAULT_CONFIG["weight_news"]
                weight_weibo = DEFAULT_CONFIG["weight_weibo"]
                if is_admin:
                    _api(token, "PUT", "/process/fusion/config", json=DEFAULT_CONFIG)
                    message = html.Span("已恢复默认配置。", className="python-success")
                else:
                    message = html.Span("仅管理员可修改融合配置。", className="python-error")
            elif "save-config-button.n_clicks" in triggered:
                time_window = _clamp_number(time_window, 5, 480, DEFAULT_CONFIG["time_window_minutes"])
                weight_news = round(_clamp_number(weight_news, 0.1, 3.0, DEFAULT_CONFIG["weight_news"]), 1)
                weight_weibo = round(_clamp_number(weight_weibo, 0.1, 3.0, DEFAULT_CONFIG["weight_weibo"]), 1)
                if is_admin:
                    _api(token, "PUT", "/process/fusion/config", json={
                        "time_window_minutes": int(time_window),
                        "weight_news": weight_news,
                        "weight_weibo": weight_weibo,
                    })
                    message = html.Span("融合配置已保存。", className="python-success")
                else:
                    message = html.Span("仅管理员可修改融合配置。", className="python-error")
            else:
                config = _api(token, "GET", "/process/fusion/config")
                time_window = config.get("time_window_minutes") or DEFAULT_CONFIG["time_window_minutes"]
                weight_news = config.get("weight_news") or DEFAULT_CONFIG["weight_news"]
                weight_weibo = config.get("weight_weibo") or DEFAULT_CONFIG["weight_weibo"]
            return (
                time_window, weight_news, weight_weibo, message,
                _formula(float(weight_news), float(weight_weibo)),
                tag, not is_admin, not is_admin,
            )
        except Exception as exc:
            return (
                time_window or DEFAULT_CONFIG["time_window_minutes"],
                weight_news or DEFAULT_CONFIG["weight_news"],
                weight_weibo or DEFAULT_CONFIG["weight_weibo"],
                html.Span(f"融合配置读取失败：{exc}", className="python-error"),
                _formula(float(weight_news or DEFAULT_CONFIG["weight_news"]), float(weight_weibo or DEFAULT_CONFIG["weight_weibo"])) if weight_news else _formula(1.0, 0.8),
                tag, not is_admin, not is_admin,
            )

    @dash_app.callback(
        Output("process-download", "data"),
        Output("export-message", "children"),
        Input("export-button", "n_clicks"),
        prevent_initial_call=True,
    )
    def export_data(clicks):
        token = flask_request.cookies.get("python_process_token", "")
        if not token:
            return no_update, html.Span("请先登录系统。", className="python-error")
        try:
            response = http.get(
                f"{API_BASE}/process/fused/export.csv",
                headers={"Authorization": f"Bearer {token}"},
                timeout=600,
            )
            if response.status_code != 200:
                try:
                    message = response.json().get("message") or f"HTTP {response.status_code}"
                except Exception:
                    message = f"HTTP {response.status_code}"
                raise RuntimeError(message)
            filename = f"fused_data_{datetime.now():%Y%m%d_%H%M%S}.csv"
            return dcc.send_string(response.text, filename), html.Span(f"导出成功：{filename}", className="python-success")
        except Exception as exc:
            return no_update, html.Span(f"导出失败：{exc}", className="python-error")

    return dash_app
