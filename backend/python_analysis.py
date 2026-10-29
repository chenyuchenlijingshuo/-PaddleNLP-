from urllib.parse import parse_qs

import pandas as pd
import plotly.graph_objects as go
import requests as http
from dash import Dash, Input, Output, State, dcc, html, no_update
from flask import jsonify, request as flask_request, send_from_directory
from flask_jwt_extended import decode_token

API_BASE = "http://127.0.0.1:5000/api"
FRONTEND_STYLES = "../frontend/src"

COLORS = {
    "text": "#eff5ff",
    "muted": "#9db0ce",
    "accent": "#79c0ff",
    "positive": "#00d9ff",
    "negative": "#ff6b9d",
    "neutral": "#c4b5fd",
    "grid": "rgba(161,191,255,0.08)",
}
LABELS = {"positive": "正面", "negative": "负面", "neutral": "中性", "unknown": "未知"}
SOURCES = {"news": "新闻", "weibo": "微博", "unknown": "未知"}


def _token(search):
    return parse_qs((search or "").lstrip("?")).get("token", [""])[0]


def _api(token, method, path, **kwargs):
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


def _plot_layout():
    return {
        "paper_bgcolor": "rgba(0,0,0,0)",
        "plot_bgcolor": "rgba(0,0,0,0)",
        "font": {"color": COLORS["text"], "family": "Segoe UI, PingFang SC, Microsoft YaHei, sans-serif"},
        "margin": {"l": 90, "r": 20, "t": 20, "b": 45},
        "xaxis": {"gridcolor": COLORS["grid"], "zerolinecolor": COLORS["grid"], "tickfont": {"color": COLORS["muted"]}},
        "yaxis": {"gridcolor": COLORS["grid"], "zerolinecolor": COLORS["grid"], "tickfont": {"color": COLORS["muted"]}},
        "autosize": True,
    }


def _empty_figure(message="暂无数据"):
    figure = go.Figure()
    figure.update_layout(**_plot_layout(), annotations=[{"text": message, "showarrow": False, "font": {"color": COLORS["muted"]}}])
    return figure


def _ranking_figure(items):
    if not items:
        return _empty_figure("当前时间窗暂无融合议题")
    frame = pd.DataFrame(items).sort_values("score", ascending=True)
    figure = go.Figure(go.Bar(
        x=frame["score"],
        y=frame["keyword"],
        orientation="h",
        marker_color="#39a0ff",
        hovertemplate="%{y}<br>融合热度分值：%{x:.4f}<extra></extra>",
    ))
    layout = _plot_layout()
    layout["margin"] = {"l": 120, "r": 20, "t": 20, "b": 40}
    layout["xaxis"]["title"] = "融合热度分值"
    layout["yaxis"]["title"] = "融合议题关键词"
    figure.update_layout(**layout)
    return figure


def _trend_figure(items):
    if not items:
        return _empty_figure("当前时间窗暂无融合趋势点")
    frame = pd.DataFrame(items)
    figure = go.Figure(go.Scatter(
        x=frame["time"],
        y=frame["score"],
        mode="lines+markers",
        line={"color": COLORS["accent"], "width": 3},
        marker={"color": "#21d0b2", "size": 7},
        fill="tozeroy",
        fillcolor="rgba(121,192,255,0.18)",
        hovertemplate="时间窗口：%{x}<br>融合热度分值：%{y:.4f}<extra></extra>",
    ))
    layout = _plot_layout()
    layout["xaxis"]["title"] = "融合时间窗口"
    layout["yaxis"]["title"] = "融合热度分值"
    figure.update_layout(**layout)
    return figure


def _pie_figure(items, palette):
    if not items:
        return _empty_figure("当前筛选范围暂无可统计样本")
    names = [SOURCES.get(item["name"], item["name"]) for item in items]
    if items and items[0]["name"] in LABELS:
        names = [LABELS.get(item["name"], item["name"]) for item in items]
    figure = go.Figure(go.Pie(
        labels=names,
        values=[item["value"] for item in items],
        hole=0.5,
        marker={"colors": palette, "line": {"color": "rgba(7,17,31,0.85)", "width": 2}},
        textinfo="label+value+percent",
        textfont={"color": COLORS["text"]},
        hovertemplate="%{label}<br>样本数：%{value}<br>占比：%{percent}<extra></extra>",
    ))
    layout = _plot_layout()
    layout["margin"] = {"l": 20, "r": 20, "t": 20, "b": 20}
    layout["showlegend"] = True
    figure.update_layout(**layout)
    return figure


def _table(rows):
    headers = ["ID", "标题", "来源", "命中关键词", "情感", "置信度", "发布时间"]
    head = html.Thead(html.Tr([html.Th(value) for value in headers]))
    body_rows = []
    for row in rows:
        label = row.get("sentiment_label")
        score = row.get("sentiment_score")
        body_rows.append(html.Tr([
            html.Td(row.get("id", "")),
            html.Td(row.get("title") or "", className="python-title-cell"),
            html.Td(SOURCES.get(row.get("source_type"), row.get("source_type") or "未知")),
            html.Td(row.get("keyword_hit") or ""),
            html.Td(LABELS.get(label, label or "未分析")),
            html.Td(f"{float(score) * 100:.1f}%" if score is not None else "-"),
            html.Td(row.get("published_at") or ""),
        ]))
    body = html.Tbody(body_rows)
    return html.Div(html.Table([head, body], className="python-data-table"), className="table-shell python-table-shell")


def _word_cloud(items):
    if not items:
        return [html.P("当前筛选范围内没有可分析的原始样本。请先将微博采集结果导入本系统，再查看产品议题词云。", className="empty-note")]
    values = [float(item.get("value") or 0) for item in items]
    maximum, minimum = max(values), min(values)
    palette = ["#7cc5ff", "#83f2d1", "#f7c873", "#c9a7ff", "#7aa2ff", "#6ee7f0", "#f8a5c2", "#9be28d"]
    tokens = []
    for index, item in enumerate(sorted(items, key=lambda row: row.get("value", 0), reverse=True)):
        value = float(item.get("value") or 0)
        ratio = 1 if maximum == minimum else (value - minimum) / (maximum - minimum)
        color = palette[index % len(palette)]
        rank = index + 1
        tokens.append(html.Span([
            html.Span(item.get("name", ""), className="keyword-token-text"),
            html.Small(str(item.get("value", "")), className="keyword-token-score"),
            html.Em(f"TOP{rank}", className="keyword-token-badge") if rank <= 3 else None,
        ], className="keyword-token keyword-token-strong" + (" keyword-token-top" if rank <= 3 else ""), title=f"{item.get('name')}：{item.get('value')}", style={"fontSize": f"{round(14 + ratio * 24)}px", "color": color, "borderColor": f"{color}66"}))
    return tokens


def _sentiment_stats(items):
    counts = {name: 0 for name in ("positive", "negative", "neutral")}
    for item in items:
        if item.get("name") in counts:
            counts[item["name"]] = int(item.get("value") or 0)
    total = sum(counts.values())
    cards = []
    for key, css in (("positive", "sentiment-positive"), ("negative", "sentiment-negative"), ("neutral", "sentiment-neutral")):
        percent = f"{counts[key] / total * 100:.1f}" if total else "0.0"
        cards.append(html.Div([
            html.Span(LABELS[key], className="sentiment-stat-label"),
            html.Strong(str(counts[key]), className="sentiment-stat-value"),
            html.Span(f"{percent}%", className="sentiment-stat-percent"),
        ], className=f"sentiment-stat-item {css}"))
    trend = "数据不足"
    if total:
        leader = max(counts, key=counts.get)
        if list(counts.values()).count(counts[leader]) == 1:
            trend = {"positive": "积极向好", "negative": "负面主导", "neutral": "态度中立"}[leader]
        elif counts["positive"] == counts["negative"] and counts["positive"] > 0:
            trend = "正负均衡"
    trend_class = {"积极向好": "trend-positive", "负面主导": "trend-negative", "态度中立": "trend-neutral"}.get(trend, "")
    summary = html.Div([
        html.Div([html.Span("总体倾向", className="sentiment-summary-label"), html.Strong(trend, className=f"sentiment-summary-value {trend_class}")], className="sentiment-summary-item"),
        html.Div([html.Span("分析样本", className="sentiment-summary-label"), html.Strong(f"{total} 条", className="sentiment-summary-value")], className="sentiment-summary-item"),
    ], className="sentiment-summary") if total else html.P("暂无情感分布数据，请先点击「批次情感分析」。", className="empty-note")
    return cards if total else [], summary, total


def _demo_visualization(hours, top_k):
    topics = [
        ("价格与版本", 92.4),
        ("影像体验", 81.7),
        ("首发供货", 73.2),
        ("外观设计", 68.5),
        ("续航表现", 57.8),
        ("预售与发货", 51.3),
        ("系统体验", 44.6),
        ("售后服务", 32.1),
    ][:top_k]
    timeline = [
        {"time": label, "score": score}
        for label, score in zip(
            ("预热期", "发布日", "预售开启", "首销前夜", "首销日", "首销次日", "首周"),
            (18, 35, 54, 46, 100, 76, 43),
        )
    ]
    example_titles = [
        "iPhone Duo 价格配置讨论示例",
        "影像功能体验讨论示例",
        "首发供货与发货讨论示例",
        "外观设计反馈示例",
        "续航与性能体验示例",
    ]
    records = [
        {
            "id": f"demo-{index + 1}",
            "title": example_titles[index % len(example_titles)],
            "source_type": "weibo",
            "published_at": f"2026-10-{23 + index // 10:02d}T{9 + index % 12:02d}:00:00",
            "keyword_hit": topics[index % len(topics)][0],
            "sentiment_label": ("positive", "neutral", "negative", "positive", "neutral")[index % 5],
            "sentiment_score": (0.91, 0.78, 0.84, 0.88, 0.73)[index % 5],
        }
        for index in range(20)
    ]
    return {
        "wordcloud": [
            {"name": name, "value": value}
            for name, value in (("价格", 100), ("影像", 86), ("发货", 73), ("外观", 61), ("续航", 56), ("首发", 49), ("性能", 42), ("预售", 35), ("系统", 28), ("售后", 20))
        ],
        "ranking": [{"keyword": name, "score": score} for name, score in topics],
        "trend": timeline,
        "source_distribution": [{"name": "weibo", "value": 50}],
        "sentiment_distribution": [
            {"name": "positive", "value": 22},
            {"name": "neutral", "value": 16},
            {"name": "negative", "value": 12},
        ],
        "records": records,
        "records_total": 50,
        "wordcloud_demo_hours": hours,
    }


def _layout():
    metrics = html.Div([
        html.Div([html.Span("筛选时窗"), html.Strong("72h", id="metric-hours")], className="metric-card"),
        html.Div([html.Span("词云项数"), html.Strong("0", id="metric-wordcloud")], className="metric-card"),
        html.Div([html.Span("趋势点位"), html.Strong("0", id="metric-trend")], className="metric-card"),
        html.Div([html.Span("NLP 状态"), html.Strong("情感待配置", id="metric-nlp")], className="metric-card"),
    ], className="metric-grid metric-grid-quad")
    filters = html.Div([
        html.Div([html.P("筛选", className="mini-label"), html.H3("条件查询")], className="section-title"),
        html.Div([
            dcc.Input(id="hours", type="number", min=1, max=720, value=72, className="python-input-number"),
            dcc.Dropdown(id="source-type", options=[{"label": "全部来源", "value": ""}, {"label": "新闻", "value": "news"}, {"label": "微博", "value": "weibo"}], value="weibo", clearable=True, placeholder="来源类型", className="python-select"),
            dcc.Input(id="keyword", type="text", value="", placeholder="融合议题关键词（筛选排行/趋势）", className="python-text-input"),
            dcc.Input(id="top-k", type="number", min=5, max=50, value=20, className="python-input-number"),
            html.Button("更新图表", id="refresh-button", className="el-button el-button--primary"),
            html.Button("载入演示数据", id="demo-button", className="el-button"),
            html.Button("批次情感分析", id="batch-button", className="el-button el-button--success"),
            html.Button("重置", id="reset-button", className="el-button"),
        ], className="toolbar"),
        html.Div(id="data-mode-note", className="panel-note"),
        html.P("批次情感分析会为已导入的原始样本写入情感结果。关键词仅筛选融合排行与趋势；原始样本、词云和情感分布按来源与时间窗统计。", className="panel-note"),
        html.Div(id="batch-message", className="panel-note"),
    ], className="glass-panel")
    wordcloud = html.Div([
        html.Div([html.P("产品议题", className="mini-label"), html.H3("新品关注词云"), html.P("从当前微博正文提取高频词；词频不等同于人工议题分类。")], className="section-title"),
        html.Div(id="word-cloud", className="keyword-cloud-board"),
    ], className="glass-panel")
    ranking = html.Div([
        html.Div([html.P("议题热度", className="mini-label"), html.H3("融合议题热度排行"), html.P("按系统融合分值排序，不代表微博点赞、评论或转发量。")], className="section-title"),
        dcc.Graph(id="ranking-chart", config={"displayModeBar": False}, style={"height": "320px"}),
    ], className="glass-panel")
    trend = html.Div([
        html.Div([html.P("传播变化", className="mini-label"), html.H3("融合议题热度趋势"), html.P("按融合时间窗口汇总分值，不等同于微博发帖量或首销事件因果效应。")], className="section-title"),
        dcc.Graph(id="trend-chart", config={"displayModeBar": False}, style={"height": "320px"}),
    ], className="glass-panel")
    sources = html.Div([
        html.Div([html.P("数据概况", className="mini-label"), html.H3("筛选样本来源构成"), html.P("统计当前时间窗和来源条件下已导入原始记录的来源类型。")], className="section-title"),
        dcc.Graph(id="source-chart", config={"displayModeBar": False}, style={"height": "320px"}),
    ], className="glass-panel")
    sentiment = html.Div([
        html.Div([
            html.Div([html.P("用户反馈", className="mini-label"), html.H3("微博情感倾向"), html.P("统计范围为当前筛选窗口内已完成情感分析的微博样本")]),
            html.Div(id="sentiment-stats", className="sentiment-stats"),
        ], className="section-title"),
        dcc.Graph(id="sentiment-chart", config={"displayModeBar": False}, style={"height": "320px"}),
        html.Div(id="sentiment-summary"),
    ], className="glass-panel sentiment-panel")
    tips = html.Div([
        html.Div([html.P("研究说明", className="mini-label"), html.H3("首销舆情分析流程"), html.P("围绕微博平台消费数码新品首发，按事件阶段筛选已导入样本，观察议题热度、情感倾向与讨论变化。")], className="section-title"),
        html.Div([
            html.Div([html.Strong("分析范围"), html.P("先选择微博来源和研究时间窗。当前没有导入 iPhone Duo 首销微博样本时，不能将现有其他来源数据解释为该事件结论。")], className="quick-entry"),
            html.Div([html.Strong("当前状态"), html.P(id="current-status")], className="quick-entry"),
            html.Div([html.Strong("数据说明"), html.P("本系统分析库目前未保存微博转发、评论、点赞计数及原创标记，因此不展示互动量和原创微博占比。关键词仅过滤融合排行与趋势。")], className="quick-entry"),
        ], className="quick-entry-list"),
        html.Div([html.Span(label, className="keyword-token keyword-token-strong") for label in ("价格", "影像", "性能", "供货", "售后")], className="keyword-cloud-board", style={"marginTop": "12px"}),
    ], className="glass-panel")
    nlp = html.Div([
                html.Div([html.P("文本研判", className="mini-label"), html.H3("首销微博文本分析"), html.P("可粘贴已采集的 iPhone Duo 相关微博进行单条情感分析或文本分类。"), html.P(id="nlp-guide")], className="section-title"),
        html.Div([
            dcc.Textarea(id="nlp-input", value="", rows=4, placeholder="粘贴 iPhone Duo 首销相关微博文本，每行一条", className="wide-input python-textarea"),
            html.Button("情感分析", id="sentiment-button", className="el-button el-button--primary", disabled=True),
            html.Button("文本分类", id="classify-button", className="el-button", disabled=True),
        ], className="toolbar"),
        html.Div(id="nlp-message", className="panel-note"),
        html.Div([
            html.Div([html.Div([html.Span(label) for label in ("文本", "情感", "置信度")], className="python-table-head"), html.Div(id="sentiment-table", className="python-table-body")], className="table-shell python-table-shell"),
            html.Div([html.Div([html.Span(label) for label in ("文本", "类别", "置信度")], className="python-table-head"), html.Div(id="classify-table", className="python-table-body")], className="table-shell python-table-shell"),
        ], className="split-grid"),
    ], className="glass-panel")
    evaluation = html.Div([
        html.Div([html.P("方法检验", className="mini-label"), html.H3("情感模型性能评估"), html.P("使用标注测试集检查情感模型的准确率、召回率和 F1；该结果评估模型，不代表 iPhone Duo 首销舆情结论。")], className="section-title"),
        html.Div([
            html.Button("开始评估", id="evaluation-button", className="el-button el-button--primary", disabled=True),
            html.Button("查看数据集", id="dataset-button", className="el-button"),
            html.Span(id="evaluation-accuracy", className="python-eval-accuracy"),
        ], className="toolbar eval-toolbar"),
        html.P('模型评估基于独立标注测试集，与当前微博筛选结果分开统计。', className="panel-note eval-note"),
        html.Div(id="dataset-info", className="metric-grid metric-grid-quad eval-dataset-info"),
        html.Div(id="evaluation-message"), html.Div(id="evaluation-results"), html.Div(id="dataset-message"),
    ], className="glass-panel")
    content = [
        html.Div([
            html.Div([html.P("微博新品首发研究", className="eyebrow"), html.H3("可视化分析工作台"), html.P("围绕 iPhone Duo 首销事件观察产品议题、用户情感与微博讨论变化。图表依据已采集且匹配当前筛选条件的样本生成。")]),
            html.Span("PaddleNLP 待就绪", id="nlp-tag", className="python-status-tag"),
        ], className="section-title"),
        metrics, filters,
        html.Div([wordcloud, ranking], className="split-grid"),
        html.Div([trend, sources], className="split-grid"),
        html.Div([sentiment, tips], className="split-grid"),
        html.Div([html.Div([html.P("明细", className="mini-label"), html.H3("已采集样本明细")], className="section-title"), html.Div(id="records-table"), html.Div(id="records-pager", className="pager-bar")], className="glass-panel"),
        nlp, evaluation,
    ]
    return html.Div([
        dcc.Location(id="analysis-url", refresh=False),
        dcc.Store(id="batch-result"),
        html.Section(html.Div(content, className="panel-stack"), className="view-shell python-analysis-view"),
    ])


def init_python_analysis(server):
    @server.route("/python-analysis/session", methods=["POST", "DELETE"])
    def sync_python_analysis_session():
        if flask_request.method == "DELETE":
            response = jsonify({"ok": True})
            response.delete_cookie("python_analysis_token", path="/python-analysis", samesite="Strict")
            return response
        authorization = flask_request.headers.get("Authorization", "")
        token = authorization[7:].strip() if authorization.startswith("Bearer ") else ""
        try:
            decode_token(token)
        except Exception:
            return jsonify({"message": "登录状态无效"}), 401
        response = jsonify({"ok": True})
        response.set_cookie(
            "python_analysis_token",
            token,
            max_age=86400,
            httponly=True,
            secure=flask_request.is_secure,
            samesite="Strict",
            path="/python-analysis",
        )
        return response

    @server.get("/python-analysis/styles.css")
    def python_analysis_styles():
        return send_from_directory(FRONTEND_STYLES, "styles.css")

    dash_app = Dash(
        "python_analysis",
        server=server,
        url_base_pathname="/python-analysis/",
        title="舆情分析工作台",
        update_title=None,
        suppress_callback_exceptions=False,
    )
    dash_app.index_string = """<!DOCTYPE html>
<html lang=\"zh-CN\">
<head>
  {%metas%}<title>{%title%}</title>{%favicon%}{%css%}
  <link rel=\"stylesheet\" href=\"/python-analysis/styles.css\">
  <style>html,body{min-height:100%;margin:0}body{overflow-x:hidden}.python-analysis-view{margin:0;min-height:100vh}.python-analysis-view .section-title{align-items:flex-end}.python-analysis-view .el-button{cursor:pointer}.python-analysis-view .el-button:disabled{opacity:.55;cursor:not-allowed}.python-analysis-view .python-input-number,.python-analysis-view .python-text-input,.python-analysis-view .python-select,.python-analysis-view .python-textarea{color:#eff5ff;background:rgba(4,12,22,.55);border:1px solid rgba(161,191,255,.18);border-radius:8px;padding:10px 12px;min-height:40px;font:inherit}.python-analysis-view .python-input-number{width:180px}.python-analysis-view .python-text-input{width:220px}.python-analysis-view .python-select{width:180px}.python-analysis-view .python-textarea{width:min(560px,100%);min-height:100px;resize:vertical}.python-analysis-view .python-select .Select-control,.python-analysis-view .python-select .Select-menu-outer{background:#0d1a2b;color:#eff5ff;border-color:rgba(161,191,255,.18)}.python-analysis-view .python-select .Select-value-label,.python-analysis-view .python-select .Select-placeholder{color:#eff5ff!important}.python-analysis-view .python-data-table{width:100%;border-collapse:collapse;min-width:860px;color:#eff5ff}.python-analysis-view .python-data-table th,.python-analysis-view .python-data-table td{padding:12px 14px;border-bottom:1px solid rgba(161,191,255,.1);text-align:left;vertical-align:top}.python-analysis-view .python-data-table th{color:#9db0ce;font-weight:600;white-space:nowrap}.python-analysis-view .python-data-table tbody tr:nth-child(even){background:rgba(255,255,255,.025)}.python-analysis-view .python-table-shell{overflow-x:auto}.python-analysis-view .python-title-cell{min-width:220px}.python-analysis-view .python-status-tag,.python-analysis-view .python-eval-accuracy{display:inline-flex;align-items:center;padding:8px 14px;border:1px solid rgba(33,208,178,.3);border-radius:8px;color:#83f2d1;background:rgba(33,208,178,.08);font-weight:600}.python-analysis-view .quick-entry-list{display:flex;flex-direction:column;gap:12px}.python-analysis-view .quick-entry{padding:12px;border:1px solid rgba(161,191,255,.1);border-radius:12px;background:rgba(255,255,255,.025)}.python-analysis-view .quick-entry p{margin-bottom:0}.python-analysis-view .python-table-head{display:grid;grid-template-columns:2fr 1fr 1fr;padding:12px 14px;color:#9db0ce;border-bottom:1px solid rgba(161,191,255,.1)}.python-analysis-view .python-table-body .python-table-row{display:grid;grid-template-columns:2fr 1fr 1fr;padding:12px 14px;border-bottom:1px solid rgba(161,191,255,.06);color:#eff5ff;gap:8px}.python-analysis-view .eval-results-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px}.python-analysis-view .eval-info{margin-top:16px;color:#b8c9e0}.python-analysis-view .confusion-matrix table{border-collapse:collapse;color:#eff5ff}.python-analysis-view .confusion-matrix th,.python-analysis-view .confusion-matrix td{padding:10px 14px;border:1px solid rgba(161,191,255,.12);text-align:center}.python-analysis-view .confusion-matrix .diagonal{background:rgba(33,208,178,.18)}.python-analysis-view .confusion-matrix .error{background:rgba(255,107,157,.18)}.python-analysis-view .python-error{color:#ff8b6a}@media(max-width:900px){.python-analysis-view .metric-grid-quad{grid-template-columns:repeat(2,minmax(0,1fr))}.python-analysis-view .split-grid{grid-template-columns:1fr}.python-analysis-view .section-title{align-items:flex-start;flex-direction:column}.python-analysis-view .sentiment-stats{flex-wrap:wrap}.python-analysis-view .eval-results-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}</style>
</head>
<body><div id=\"react-entry-point\">{%app_entry%}</div><footer>{%config%}{%scripts%}{%renderer%}</footer></body>
</html>"""
    dash_app.layout = _layout

    @dash_app.callback(
        Output("metric-hours", "children"), Output("metric-wordcloud", "children"), Output("metric-trend", "children"),
        Output("metric-nlp", "children"), Output("nlp-tag", "children"), Output("nlp-guide", "children"),
        Output("current-status", "children"), Output("data-mode-note", "children"), Output("word-cloud", "children"),
        Output("ranking-chart", "figure"), Output("trend-chart", "figure"), Output("source-chart", "figure"),
        Output("sentiment-chart", "figure"), Output("sentiment-stats", "children"), Output("sentiment-summary", "children"),
        Output("records-table", "children"), Output("records-pager", "children"), Output("dataset-info", "children"),
        Output("sentiment-button", "disabled"), Output("evaluation-button", "disabled"), Output("classify-button", "disabled"),
        Input("analysis-url", "pathname"), Input("refresh-button", "n_clicks"), Input("demo-button", "n_clicks"), Input("reset-button", "n_clicks"), Input("batch-result", "data"),
        State("hours", "value"), State("source-type", "value"), State("keyword", "value"), State("top-k", "value"),
    )
    def refresh_analysis(pathname, refresh_clicks, demo_clicks, reset_clicks, batch_result, hours, source_type, keyword, top_k):
        token = flask_request.cookies.get("python_analysis_token", "")
        if not token:
            return ("72h", "0", "0", "情感待配置", "PaddleNLP 待就绪", "请先登录系统。", "请先登录系统。", "", [], _empty_figure(), _empty_figure(), _empty_figure(), _empty_figure(), [], html.P("请先登录系统。", className="empty-note"), [], "", [], True, True, True)
        try:
            triggered = set(__import__("dash").callback_context.triggered_prop_ids)
            if "reset-button.n_clicks" in triggered:
                hours, source_type, keyword, top_k = 72, "weibo", "", 20
            hours = min(max(int(hours or 72), 1), 720)
            top_k = min(max(int(top_k or 20), 5), 50)
            demo_mode = "demo-button.n_clicks" in triggered
            data = _demo_visualization(hours, top_k) if demo_mode else _api(
                token,
                "GET",
                "/analyze/visualization",
                params={"hours": hours, "source_type": source_type or "", "keyword": keyword or "", "top_k": top_k, "page": 1, "size": 20},
            )
            status = _api(token, "GET", "/analyze/nlp/status")
            dataset = _api(token, "GET", "/analyze/nlp/dataset/info")
            sentiments = data.get("sentiment_distribution") or []
            stats, summary, total = _sentiment_stats(sentiments)
            records = data.get("records") or []
            distribution = data.get("source_distribution") or []
            dataset_cards = []
            if dataset.get("available"):
                for title, value in (("测试样本数", dataset.get("total_samples", 0)), ("正面样本", dataset.get("label_distribution", {}).get("positive", 0)), ("负面样本", dataset.get("label_distribution", {}).get("negative", 0)), ("中性样本", dataset.get("label_distribution", {}).get("neutral", 0))):
                    dataset_cards.append(html.Div([html.Span(title), html.Strong(str(value))], className="metric-card"))
            record_count = data.get("records_total", 0)
            records_view = _table(records) if records else html.P(
                "当前来源和时间窗内没有已导入的匹配样本。请先采集并导入相关微博，再分析 iPhone Duo 首销议题。",
                className="empty-note",
            )
            pager = html.P(f"显示 {len(records)} 条，共 {record_count} 条记录 · 第 1 页", className="panel-note") if record_count else ""
            status_label = "情感可用" if status.get("sentiment_ready") else "情感待配置"
            guide = "支持对多段文本执行情感分析与文本分类，可用于风险研判和主题归类。" if status.get("classification_ready") else "当前以情感分析为主，文本分类能力正在优化，可先使用情感分布与明细结果。"
            current_status = ("演示数据 · 虚构样本：50 条；未写入数据库。" if demo_mode else f"NLP：{status_label}；情感分布项：{len(sentiments)}；明细记录：{record_count}。")
            mode_note = html.Strong("演示数据（50 条虚构样本，仅供预览图表样式；未写入数据库）。点击“更新图表”可返回真实采集数据。") if demo_mode else ""
            return (
                f"{hours}h", str(len(data.get("wordcloud") or [])), str(len(data.get("trend") or [])), status_label,
                "PaddleNLP 已接入" if status.get("available") else "PaddleNLP 待就绪", guide, current_status, mode_note,
                _word_cloud(data.get("wordcloud") or []), _ranking_figure(data.get("ranking") or []),
                _trend_figure(data.get("trend") or []), _pie_figure(distribution, ["#667eea", "#f093fb", "#4facfe", "#43e97b"]),
                _pie_figure(sentiments, [COLORS["positive"], COLORS["negative"], COLORS["neutral"], "#94a3b8"]), stats, summary,
                records_view, pager, dataset_cards,
                not status.get("sentiment_ready", False), not status.get("sentiment_ready", False), not status.get("classification_ready", False),
            )
        except Exception as exc:
            message = str(exc)
            error = html.P(f"分析数据加载失败：{message}", className="python-error")
            return ("72h", "0", "0", "服务异常", "PaddleNLP 状态不可用", message, message, "", error, _empty_figure(), _empty_figure(), _empty_figure(), _empty_figure(), [], error, [], "", [], True, True, True)

    @dash_app.callback(Output("batch-result", "data"), Output("batch-message", "children"), Input("batch-button", "n_clicks"), prevent_initial_call=True)
    def run_batch(clicks):
        try:
            token = flask_request.cookies.get("python_analysis_token", "")
            result = _api(token, "POST", "/process/nlp/sentiment/run", json={"limit": 300, "only_missing": True})
            message = f"批次情感分析完成：处理 {result.get('processed', 0)} 条，写入 {result.get('upserted', 0)} 条。"
            return {"finished": clicks, "processed": result.get("processed", 0)}, html.Span(message)
        except Exception as exc:
            return no_update, html.Span(f"批次情感分析失败：{exc}", className="python-error")

    @dash_app.callback(Output("sentiment-table", "children"), Output("nlp-message", "children"), Input("sentiment-button", "n_clicks"), State("nlp-input", "value"), prevent_initial_call=True)
    def run_sentiment(clicks, text):
        try:
            token = flask_request.cookies.get("python_analysis_token", "")
            texts = [line.strip() for line in (text or "").splitlines() if line.strip()]
            result = _api(token, "POST", "/analyze/nlp/sentiment", json={"texts": texts})
            items = result.get("items") or []
            rows = [html.Div([html.Span(item.get("text", "")), html.Span(LABELS.get(item.get("label"), item.get("label", "-"))), html.Span(f"{float(item['score']) * 100:.1f}%" if item.get("score") is not None else "-")], className="python-table-row") for item in items]
            return rows, result.get("message", "情感分析完成")
        except Exception as exc:
            return [], html.Span(f"情感分析失败：{exc}", className="python-error")

    @dash_app.callback(Output("classify-table", "children"), Output("nlp-message", "children", allow_duplicate=True), Input("classify-button", "n_clicks"), State("nlp-input", "value"), prevent_initial_call=True)
    def run_classification(clicks, text):
        try:
            token = flask_request.cookies.get("python_analysis_token", "")
            texts = [line.strip() for line in (text or "").splitlines() if line.strip()]
            result = _api(token, "POST", "/analyze/nlp/classify", json={"texts": texts})
            items = result.get("items") or []
            rows = [html.Div([html.Span(item.get("text", "")), html.Span(item.get("label", "-")), html.Span(f"{float(item['score']) * 100:.1f}%" if item.get("score") is not None else "-")], className="python-table-row") for item in items]
            return rows, result.get("message", "文本分类完成")
        except Exception as exc:
            return [], html.Span(f"文本分类失败：{exc}", className="python-error")

    @dash_app.callback(Output("evaluation-results", "children"), Output("evaluation-accuracy", "children"), Output("evaluation-message", "children"), Input("evaluation-button", "n_clicks"), prevent_initial_call=True)
    def run_evaluation(clicks):
        try:
            token = flask_request.cookies.get("python_analysis_token", "")
            result = _api(token, "GET", "/analyze/nlp/evaluate")
            if not result.get("success"):
                return [], "", html.P(result.get("message", "评估失败"), className="python-error")
            metrics = result["metrics"]
            cards = []
            raw_metrics = result.get("model_metrics") or metrics
            for title, value in (
                ("规则增强准确率", metrics["accuracy"]),
                ("模型原始准确率", raw_metrics["accuracy"]),
                ("宏平均精确率", metrics["macro_avg"]["precision"]),
                ("宏平均召回率", metrics["macro_avg"]["recall"]),
                ("宏平均 F1", metrics["macro_avg"]["f1"]),
            ):
                cards.append(html.Div([html.Span(title), html.Strong(f"{value * 100:.2f}%")], className="metric-card"))
            labels = metrics["confusion_matrix"]["labels"]
            matrix_rows = [html.Tr([html.Th("")] + [html.Th(LABELS.get(label, label)) for label in labels])]
            for index, row in enumerate(metrics["confusion_matrix"]["matrix"]):
                matrix_rows.append(html.Tr([html.Th(LABELS.get(labels[index], labels[index]), className="row-label")] + [html.Td(value, className="diagonal" if index == col else ("error" if value else "")) for col, value in enumerate(row)]))
            per_class = []
            for label, values in metrics["per_class"].items():
                per_class.append(html.Tr([html.Td(LABELS.get(label, label)), html.Td(f"{values['precision'] * 100:.2f}%"), html.Td(f"{values['recall'] * 100:.2f}%"), html.Td(f"{values['f1'] * 100:.2f}%"), html.Td(values["support"])]))
            per_class_head = html.Thead(html.Tr([html.Th(label) for label in ("类别", "精确率", "召回率", "F1值", "样本数")]))
            per_class_table = html.Table([per_class_head, html.Tbody(per_class)], className="python-data-table")
            per_class_panel = html.Div([html.H4("各类别指标"), per_class_table], className="eval-section")
            confusion_table = html.Div(html.Table(matrix_rows), className="confusion-matrix")
            evaluation_info = html.Div([
                html.P(f"评估时间：{result['evaluation_info']['evaluated_at']}"),
                html.P(f"耗时：{result['evaluation_info']['duration_seconds']} 秒"),
                html.P(f"处理速度：{result['evaluation_info']['samples_per_second']} 样本/秒"),
                html.P(f"错误样本数：{result['total_errors']} / {metrics['total_samples']}"),
            ], className="eval-info")
            confusion_panel = html.Div([html.H4("混淆矩阵"), confusion_table, evaluation_info], className="eval-section")
            results = html.Div([
                html.Div(cards, className="eval-results-grid"),
                html.Div([per_class_panel, confusion_panel], className="split-grid"),
            ])
            enhancement = result.get("enhancement") or {}
            gain = float(enhancement.get("accuracy_gain") or 0) * 100
            message = (
                f"评估完成，共 {metrics['total_samples']} 个样本。"
                f"规则增强准确率 {metrics['accuracy'] * 100:.2f}%，"
                f"模型原始准确率 {raw_metrics['accuracy'] * 100:.2f}%，"
                f"增强差值 {gain:+.2f} 个百分点。"
            )
            return results, f"增强准确率: {metrics['accuracy'] * 100:.2f}%", html.P(message)
        except Exception as exc:
            return [], "", html.P(f"评估失败：{exc}", className="python-error")

    @dash_app.callback(Output("dataset-message", "children"), Input("dataset-button", "n_clicks"), prevent_initial_call=True)
    def show_dataset(clicks):
        try:
            token = flask_request.cookies.get("python_analysis_token", "")
            dataset = _api(token, "GET", "/analyze/nlp/dataset/info")
            return html.P(f"测试数据集共 {dataset.get('total_samples', 0)} 条，版本 {dataset.get('version', '-')}")
        except Exception as exc:
            return html.P(f"数据集读取失败：{exc}", className="python-error")

    return dash_app
