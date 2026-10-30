"""
数据处理页（Python 版）
=======================
按照简单脚本的写法：pandas 清洗数据，numpy 计算融合分值，matplotlib 画图。
图表颜色和前端页面保持一致（蓝色 #79c0ff、绿色 #21d0b2）。
"""

import base64
import io
import re

import matplotlib

matplotlib.use("Agg")  # 不弹窗，只把图片保存到内存
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from dash import Dash, Input, Output, State, callback_context, dcc, html, no_update
from flask import current_app, jsonify, request as flask_request
from flask_jwt_extended import decode_token

from extensions import db
from models import FusionConfig, RawData

# 页面用的颜色
BLUE = "#79c0ff"
GREEN = "#21d0b2"
TEXT = "#eff5ff"
GRID = "#a1bfff"

# 让 matplotlib 能显示中文
plt.rcParams["font.sans-serif"] = ["PingFang HK", "Arial Unicode MS", "Heiti TC"]
plt.rcParams["axes.unicode_minus"] = False


# 表情符号的范围
EMOJI = re.compile("[\U0001F300-\U0001FAFF\U0001F600-\U0001F64F\U0001F000-\U0001F0FF\u2600-\u26FF\u2700-\u27BF\uFE0F\u200D]")


def clean_text(text):
    """清洗文本：去掉标签、符号、表情包、重复标点和多余空格"""
    text = str(text or "")
    text = text.replace("\u3000", " ").replace("\xa0", " ")
    text = text.replace("\u200b", "").replace("\u200c", "").replace("\u200d", "")
    text = re.sub(r"<[^>]+>", " ", text)  # 去掉 <p> 这类标签
    text = re.sub(r"http[s]?://\S+", " ", text)  # 去掉网址
    # 去掉 # 《 》 「 」 【 】 @ 等符号
    text = re.sub(r"[#＃《》〈〉「」『』【】〔〕@＠<>/\\|*~`^_=+{}\[\]]", " ", text)
    text = EMOJI.sub(" ", text)  # 去掉表情包
    text = re.sub(r"([^\w\s])\1+", r"\1", text)  # 重复符号只留一个，比如 ？？？→？
    text = re.sub(r"\s+([，。！？：；、,.!?:;])", r"\1", text)  # 去掉标点前面的空格
    text = re.sub(r"\s+", " ", text)  # 多个空格合并成一个
    return text.strip(" ，。！？：；、,.!?:;")


def load_data():
    """从数据库读取原始数据，放进 pandas 的 DataFrame"""
    rows = RawData.query.order_by(RawData.id.desc()).limit(1000).all()
    data = pd.DataFrame([
        {
            "id": row.id,
            "title": row.title or "",
            "content": row.content or "",
            "source_type": row.source_type or "",
            "keyword_hit": row.keyword_hit or "",
            "published_at": row.published_at,
        }
        for row in rows
    ])
    return data


def make_chart(result_data):
    """用 matplotlib 画柱状图，颜色和页面一致"""
    top_data = result_data.head(10)

    figure, axes = plt.subplots(figsize=(8, 4))
    figure.patch.set_facecolor("#0b1a2b")
    axes.set_facecolor("#0b1a2b")

    # 柱子颜色：蓝绿交替，和页面强调色一致
    colors = []
    for i in range(len(top_data)):
        if i % 2 == 0:
            colors.append(BLUE)
        else:
            colors.append(GREEN)

    axes.bar(top_data["keyword"], top_data["fused_score"], color=colors, width=0.6)
    axes.set_xlabel("关键词", color=TEXT)
    axes.set_ylabel("融合分值", color=TEXT)
    axes.set_title("关键词融合分值", color=TEXT)
    axes.tick_params(axis="x", labelcolor=TEXT, colors=TEXT, labelrotation=45)
    axes.tick_params(axis="y", labelcolor=TEXT, colors=TEXT)
    axes.grid(axis="y", color=GRID, alpha=0.15)
    axes.spines["top"].set_visible(False)
    axes.spines["right"].set_visible(False)
    axes.spines["bottom"].set_color(GRID)
    axes.spines["left"].set_color(GRID)
    figure.tight_layout()

    buffer = io.BytesIO()
    figure.savefig(buffer, format="png", dpi=110, facecolor=figure.get_facecolor())
    plt.close(figure)
    image = base64.b64encode(buffer.getvalue()).decode()
    return "data:image/png;base64," + image


def make_table(headers, rows):
    """把二维列表变成网页里的表格"""
    head = html.Thead(html.Tr([html.Th(x) for x in headers]))
    body = html.Tbody([html.Tr([html.Td(x) for x in row]) for row in rows])
    return html.Div(html.Table([head, body], className="python-data-table"), className="table-shell python-table-shell")


def make_fused_list(fused_rows):
    """把融合结果做成卡片列表，比普通表格更好看"""
    if not fused_rows:
        return html.P("暂无结果。", className="empty-note")

    rows = [html.Div([
        html.Span("关键词", className="fused-head-cell"),
        html.Span("新闻", className="fused-head-cell"),
        html.Span("微博", className="fused-head-cell"),
        html.Span("融合分值", className="fused-head-cell fused-head-score"),
    ], className="fused-row fused-head")]

    for item in fused_rows:
        rows.append(html.Div([
            html.Span(item[0], className="fused-keyword"),
            html.Span(f"新闻 {item[1]}", className="fused-chip fused-chip-news"),
            html.Span(f"微博 {item[2]}", className="fused-chip fused-chip-weibo"),
            html.Strong(str(item[3]), className="fused-score"),
        ], className="fused-row"))

    return html.Div(rows, className="fused-list")


def load_and_compute(weight_news, weight_weibo, window_minutes):
    """读取 → 按时间窗口筛选 → 清洗 → 统计 → 算分 → 画图"""
    data = load_data()

    # 没有数据就直接返回
    if len(data) == 0:
        return 0, 0, [], [], ""

    # 时间窗口：0 表示不限时间，其余按最近 N 分钟筛选
    if window_minutes > 0:
        data["published_at"] = pd.to_datetime(data["published_at"], errors="coerce")
        latest = data["published_at"].max()
        if pd.notna(latest):
            start = latest - pd.Timedelta(minutes=window_minutes)
            data = data[data["published_at"] >= start]
            data = data.reset_index(drop=True)
            if len(data) == 0:
                return 0, 0, [], [], ""

    # 1. 把空值变成空字符串
    data["title"] = data["title"].fillna("")
    data["content"] = data["content"].fillna("")
    data["source_type"] = data["source_type"].fillna("")
    data["keyword_hit"] = data["keyword_hit"].fillna("")

    # 2. 清洗文本（去掉 #《@ 这些符号）
    data["title"] = data["title"].apply(clean_text)
    data["content"] = data["content"].apply(clean_text)

    # 3. 提取关键词：优先用 keyword_hit 的第一个词，没有就用标题
    data["keyword"] = ""
    for i in range(len(data)):
        keyword_hit = data.loc[i, "keyword_hit"]
        if keyword_hit != "":
            data.loc[i, "keyword"] = keyword_hit.split(",")[0].strip()
        elif data.loc[i, "title"] != "":
            data.loc[i, "keyword"] = data.loc[i, "title"][:10]
        else:
            data.loc[i, "keyword"] = "其他"

    # 4. 统计每个关键词的新闻数量和微博数量
    result = []
    keywords = data["keyword"].unique()

    for word in keywords:
        news_count = 0
        weibo_count = 0

        for i in range(len(data)):
            if data.loc[i, "keyword"] == word:
                source = str(data.loc[i, "source_type"]).lower()
                if source == "news" or source == "新闻":
                    news_count = news_count + 1
                elif source == "weibo" or source == "微博":
                    weibo_count = weibo_count + 1

        # 用 numpy 计算融合分值：新闻数 × 新闻权重 + 微博数 × 微博权重
        counts = np.array([news_count, weibo_count])
        weights = np.array([weight_news, weight_weibo])
        fused_score = np.round(np.sum(counts * weights), 2)

        result.append([word, news_count, weibo_count, fused_score])

    # 5. 转成表格，按分值从高到低排序
    result_data = pd.DataFrame(result, columns=["keyword", "news_count", "weibo_count", "fused_score"])
    result_data = result_data.sort_values(by="fused_score", ascending=False)

    # 6. 准备页面要显示的数据
    fused_rows = []
    for i in range(len(result_data)):
        fused_rows.append([
            result_data.iloc[i]["keyword"],
            int(result_data.iloc[i]["news_count"]),
            int(result_data.iloc[i]["weibo_count"]),
            result_data.iloc[i]["fused_score"],
        ])

    sample_rows = []
    for i in range(min(10, len(data))):
        sample_rows.append([
            data.loc[i, "id"],
            data.loc[i, "title"][:30],
            data.loc[i, "content"][:80],
            data.loc[i, "keyword"],
        ])

    chart = make_chart(result_data)
    return len(data), len(result_data), fused_rows, sample_rows, chart


def layout():
    """页面结构"""
    return html.Div([
        html.Section(html.Div([
            html.Div([
                html.Div([
                    html.P("处理", className="eyebrow"),
                    html.H3("预处理与融合"),
                    html.P("先清洗文本，再按时间窗口筛选数据，最后计算融合分值并生成图表。"),
                ]),
                html.Span("融合", className="python-status-tag"),
            ], className="section-title"),
            html.Div([
                html.Div([html.Div([html.P("操作", className="mini-label"), html.H3("处理流程"), html.P("预处理负责清洗文本，融合负责统计数量并计算分值。")])], className="section-title"),
                html.Div([
                    html.Button("执行预处理", id="pre-button", className="py-btn py-btn-primary"),
                    html.Button("执行融合", id="fusion-button", className="py-btn py-btn-success"),
                    html.Button("刷新数据", id="refresh-button", className="py-btn py-btn-ghost"),
                    html.Button("导出数据", id="export-button", className="py-btn py-btn-warn"),
                ], className="toolbar"),
                html.Div([
                    html.Span("时间窗口", className="config-unit"),
                    dcc.Input(id="window-minutes", type="number", min=0, step=10, value=0, className="python-input-number"),
                    html.Span("分钟（0 = 全部）", className="config-unit"),
                    html.Span("新闻权重", className="config-unit"),
                    dcc.Input(id="weight-news", type="number", value=1.0, step=0.1, className="python-input-number"),
                    html.Span("微博权重", className="config-unit"),
                    dcc.Input(id="weight-weibo", type="number", value=0.8, step=0.1, className="python-input-number"),
                    html.Button("保存配置", id="save-config-button", className="py-btn py-btn-ghost"),
                    html.Button("恢复默认", id="reset-config-button", className="py-btn py-btn-ghost"),
                ], className="toolbar"),
                html.Div(id="config-message", className="panel-note"),
                html.P("预处理后再执行融合。", className="panel-note"),
                html.Div(id="message", className="panel-note"),
                dcc.Download(id="download"),
            ], className="glass-panel"),
            html.Div([
                html.Div([html.Div([html.P("概览", className="mini-label"), html.H3("结果统计"), html.P("展示本次处理的数据量、关键词数量和最高分值。")])], className="section-title"),
                html.Div([
                    html.Div([html.Span("原始记录"), html.Strong("0", id="metric-raw")], className="metric-card"),
                    html.Div([html.Span("关键词"), html.Strong("0", id="metric-keyword")], className="metric-card"),
                    html.Div([html.Span("最高分值"), html.Strong("0", id="metric-top")], className="metric-card"),
                ], className="metric-grid"),
            ], className="glass-panel"),
            html.Div([
                html.Div([html.Div([html.P("图表", className="mini-label"), html.H3("融合分值排行"), html.P("按融合分值从高到低展示前 10 个关键词。")])], className="section-title"),
                html.Img(id="chart", style={"width": "100%"}),
            ], className="glass-panel"),
            html.Div([
                html.Div([html.Div([html.P("结果", className="mini-label"), html.H3("融合结果列表"), html.P("每个关键词对应的新闻数、微博数和融合分值。")])], className="section-title"),
                html.Div(id="fused-table"),
            ], className="glass-panel"),
            html.Div([
                html.Div([html.Div([html.P("样本", className="mini-label"), html.H3("清洗后的样本（前 10 条）"), html.P("去掉标签、符号、表情和多余空格后的文本。")])], className="section-title"),
                html.Div(id="sample-table"),
            ], className="glass-panel"),
        ], className="panel-stack"), className="view-shell python-analysis-view"),
    ])


def init_python_process(server):
    """把 Python 处理页挂到 Flask 上"""

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
        response.set_cookie("python_process_token", token, max_age=86400, httponly=True,
                            secure=flask_request.is_secure, samesite="Strict", path="/python-process")
        return response

    dash_app = Dash(
        "python_process",
        server=server,
        url_base_pathname="/python-process/",
        title="数据处理",
        update_title=None,
        suppress_callback_exceptions=True,
    )
    dash_app.index_string = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  {%metas%}<title>{%title%}</title>{%favicon%}{%css%}
  <link rel="stylesheet" href="/python-analysis/styles.css">
  <style>html,body{margin:0;min-height:100%;background:transparent}.python-analysis-view{margin:0}
  .fused-list{display:flex;flex-direction:column;gap:10px}
  .fused-row{display:grid;grid-template-columns:2fr 1fr 1fr 1fr;align-items:center;gap:10px;padding:12px 18px;border:1px solid rgba(161,191,255,.12);border-radius:12px;background:rgba(255,255,255,.03);transition:all .2s ease}
  .fused-row:hover{border-color:rgba(121,192,255,.4);background:rgba(121,192,255,.07);transform:translateY(-1px)}
  .fused-head{background:transparent;border:none;padding:0 18px 6px}
  .fused-head-cell{color:#9db0ce;font-size:13px;font-weight:600}
  .fused-head-score{justify-self:end}
  .fused-keyword{font-weight:600;color:#eff5ff}
  .fused-chip{font-size:13px}
  .fused-chip-news{color:#79c0ff}
  .fused-chip-weibo{color:#21d0b2}
  .fused-score{justify-self:end;padding:4px 14px;border-radius:999px;background:rgba(33,208,178,.14);color:#83f2d1;font-weight:700}
  .py-btn{border:none;border-radius:10px;padding:10px 18px;font:inherit;font-weight:600;cursor:pointer;transition:transform .15s,filter .15s}
  .py-btn-primary{background:linear-gradient(135deg,#79c0ff,#4f9cff);color:#06121f}
  .py-btn-success{background:linear-gradient(135deg,#21d0b2,#12a58c);color:#04131a}
  .py-btn-ghost{background:rgba(121,192,255,.08);border:1px solid rgba(121,192,255,.3);color:#eff5ff}
  .py-btn-warn{background:linear-gradient(135deg,#ff8b6a,#ff6b6b);color:#ffffff}
  .py-btn:hover{filter:brightness(1.12)}
  .py-btn:active{transform:translateY(2px);filter:brightness(.85)}
  .python-analysis-view .python-input-number{background:rgba(4,12,22,.6);border:1px solid rgba(161,191,255,.25);border-radius:8px;padding:8px 12px;min-height:40px;color:#eff5ff;font-size:15px;width:110px}
  .python-analysis-view .python-input-number:focus{border-color:#79c0ff;outline:none}
  .python-analysis-view .metric-card strong{color:#eff5ff}
  .python-analysis-view .section-title{align-items:flex-end;margin-bottom:12px}
  .python-analysis-view .section-title h3{margin:0;line-height:1.25;font-size:1.4rem}
  .python-analysis-view .section-title p{margin:6px 0 0;font-size:14px;line-height:1.45}
  .python-analysis-view .glass-panel{padding:14px 18px 18px}
  .python-analysis-view .panel-stack{gap:14px}
  .python-analysis-view .python-status-tag{display:inline-flex;align-items:center;padding:8px 16px;border:1px solid rgba(240,198,116,.45);border-radius:999px;background:rgba(240,198,116,.12);color:#f0c674;font-weight:600;white-space:nowrap}
  .python-analysis-view .section-title .mini-label,.python-analysis-view .section-title .eyebrow{margin:0 0 4px}
  @media(max-width:700px){.fused-row{grid-template-columns:1fr 1fr}.fused-head{display:none}}
  </style>
</head>
<body><div id="react-entry-point">{%app_entry%}</div><footer>{%config%}{%scripts%}{%renderer%}</footer></body>
</html>"""
    dash_app.layout = layout

    @dash_app.callback(
        Output("message", "children"),
        Output("metric-raw", "children"),
        Output("metric-keyword", "children"),
        Output("metric-top", "children"),
        Output("chart", "src"),
        Output("fused-table", "children"),
        Output("sample-table", "children"),
        Input("pre-button", "n_clicks"),
        Input("fusion-button", "n_clicks"),
        Input("refresh-button", "n_clicks"),
        State("window-minutes", "value"),
        State("weight-news", "value"),
        State("weight-weibo", "value"),
    )
    def run_process(pre_clicks, fusion_clicks, refresh_clicks, window_minutes, weight_news, weight_weibo):
        if not flask_request.cookies.get("python_process_token"):
            return "请先登录系统，再刷新页面。", "0", "0", "0", "", "", ""

        window_minutes = int(float(window_minutes or 0))
        weight_news = float(weight_news or 1.0)
        weight_weibo = float(weight_weibo or 0.8)
        with current_app.app_context():
            raw_count, keyword_count, fused_rows, sample_rows, chart = load_and_compute(weight_news, weight_weibo, window_minutes)

        if raw_count == 0:
            if window_minutes > 0:
                return "当前时间窗口内没有数据，请调大时间窗口或设为 0。", "0", "0", "0", "", "", ""
            return "还没有采集到数据，请先执行采集。", "0", "0", "0", "", "", ""

        top_score = fused_rows[0][3] if fused_rows else 0
        sample_table = make_table(["ID", "标题", "清洗后内容", "关键词"], sample_rows)

        # 点了“执行预处理”：只更新清洗结果
        if callback_context.triggered_id == "pre-button":
            message = f"预处理完成：共清洗 {raw_count} 条数据。"
            return message, str(raw_count), str(keyword_count), str(top_score), no_update, no_update, sample_table

        # 默认、“执行融合”和“刷新数据”：显示图表和融合结果
        window_text = "全部数据" if window_minutes == 0 else f"最近 {window_minutes} 分钟"
        message = f"融合完成：{window_text}，共 {raw_count} 条原始数据，得到 {keyword_count} 个关键词。"
        return message, str(raw_count), str(keyword_count), str(top_score), chart, make_fused_list(fused_rows), sample_table

    @dash_app.callback(
        Output("config-message", "children"),
        Output("weight-news", "value"),
        Output("weight-weibo", "value"),
        Output("window-minutes", "value"),
        Input("save-config-button", "n_clicks"),
        Input("reset-config-button", "n_clicks"),
        State("window-minutes", "value"),
        State("weight-news", "value"),
        State("weight-weibo", "value"),
    )
    def save_or_reset_config(save_clicks, reset_clicks, window_minutes, weight_news, weight_weibo):
        if not flask_request.cookies.get("python_process_token"):
            return "请先登录系统。", no_update, no_update, no_update

        if callback_context.triggered_id == "reset-config-button":
            window_minutes = 0
            weight_news = 1.0
            weight_weibo = 0.8

        with current_app.app_context():
            config = FusionConfig.query.first()
            if config is None:
                config = FusionConfig()
                db.session.add(config)
            config.time_window_minutes = int(float(window_minutes or 0))
            config.weight_news = float(weight_news or 1.0)
            config.weight_weibo = float(weight_weibo or 0.8)
            db.session.commit()

        return "配置已保存", weight_news, weight_weibo, window_minutes

    @dash_app.callback(
        Output("download", "data"),
        Input("export-button", "n_clicks"),
        State("window-minutes", "value"),
        State("weight-news", "value"),
        State("weight-weibo", "value"),
        prevent_initial_call=True,
    )
    def export_fused_data(export_clicks, window_minutes, weight_news, weight_weibo):
        if not flask_request.cookies.get("python_process_token"):
            return no_update

        with current_app.app_context():
            raw_count, keyword_count, fused_rows, sample_rows, chart = load_and_compute(
                float(weight_news or 1.0), float(weight_weibo or 0.8), int(float(window_minutes or 0))
            )

        frame = pd.DataFrame(fused_rows, columns=["关键词", "新闻数", "微博数", "融合分值"])
        return dcc.send_data_frame(frame.to_csv, "融合结果.csv", index=False, encoding="utf-8-sig")
