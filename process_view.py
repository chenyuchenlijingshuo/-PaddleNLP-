"""
ProcessView.vue 的 Python 版本
==============================

这个页面（frontend/src/views/ProcessView.vue）原本是前端的「预处理与融合」页面，
里面做的事是：

  1. 预处理：清洗文本、分词、去重
  2. 融合：在时间窗口内，按关键词统计新闻数量和微博数量
  3. 算分：融合分值 = 新闻数量 x 新闻权重 + 微博数量 x 微博权重
  4. 查看结果、导出 CSV

下面用最基础的 numpy / pandas / matplotlib 把这几步重新写一遍，
不连后端、不连数据库，直接读 data/raw_data_export.csv。

运行方式：在项目根目录执行
    python3 process_view.py
"""

import os
import re
from datetime import datetime

import matplotlib.pyplot as plt
import pandas as pd

# ==========================================================
# 1. 融合配置（对应页面上的三个输入框）
# ==========================================================
# 页面默认是 60 分钟；这里数据是前几天采集的，窗口开大一点才有结果，
# 想体验页面默认值就把 1440 改成 60
TIME_WINDOW_MINUTES = 1440   # 时间窗口：只看最近多少分钟的数据
WEIGHT_NEWS = 1.0            # 新闻权重
WEIGHT_WEIBO = 0.8           # 微博权重

DATA_FILE = "data/raw_data_export.csv"
OUTPUT_DIR = "output"


# ==========================================================
# 2. 预处理：清洗 + 分词（对应「执行预处理」按钮）
# ==========================================================
def clean_text(text):
    """把文本里的 HTML 标签、多余空格去掉"""
    text = str(text).replace("\u3000", " ").replace("\xa0", " ")
    text = re.sub(r"<[^>]+>", " ", text)          # 去掉 <xxx> 这种标签
    text = re.sub(r"\s+", " ", text)             # 多个空格合成一个
    return text.strip()


def split_words(text):
    """简单分词：连续的汉字算一个词，连续的小写字母/数字算一个词"""
    text = clean_text(text).lower()
    words = re.findall(r"[\u4e00-\u9fff]{1,}|[a-z0-9_]{2,}", text)

    stop_words = ["的", "了", "和", "是", "在", "与", "就", "都", "及", "the", "and", "for"]
    result = []
    for word in words:
        if word not in stop_words:
            result.append(word)
    return result


def get_keywords(row):
    """取出这条数据的关键词：先看 keyword_hit，没有就从标题+正文里分词"""
    keywords = []
    raw = str(row["keyword_hit"])
    for item in raw.split(","):
        item = item.strip()
        if item != "":
            keywords.append(item)

    if len(keywords) == 0:
        keywords = split_words(row["title"] + " " + row["content_clean"])[:3]

    if len(keywords) == 0:
        keywords = ["未知主题"]

    return keywords


print("=" * 50)
print("第 1 步：读取数据")
print("=" * 50)

df = pd.read_csv(DATA_FILE, encoding="utf-8-sig")
df["published_at"] = pd.to_datetime(df["published_at"])
print("原始数据条数：", len(df))


print()
print("=" * 50)
print("第 2 步：预处理（清洗 / 分词 / 去重）")
print("=" * 50)

# 清洗正文
df["content_clean"] = df["content"].apply(clean_text)

# 按 dedup_hash 去重，和页面里「去重」的意思一样
df = df.drop_duplicates(subset="dedup_hash")
df = df.reset_index(drop=True)
print("去重之后条数：", len(df))

# 每条数据拆出关键词，存到新的一列
df["keywords"] = df.apply(get_keywords, axis=1)

print("预处理完成。")


# ==========================================================
# 3. 时间窗口筛选
# ==========================================================
print()
print("=" * 50)
print("第 3 步：按时间窗口筛选")
print("=" * 50)

end_time = df["published_at"].max()              # 窗口结束时间 = 数据里最新的发布时间
start_time = end_time - pd.Timedelta(minutes=TIME_WINDOW_MINUTES)

window_df = df[(df["published_at"] >= start_time) & (df["published_at"] <= end_time)]
print("窗口开始：", start_time)
print("窗口结束：", end_time)
print("窗口内数据条数：", len(window_df))


# ==========================================================
# 4. 融合：统计每个关键词的新闻数 / 微博数，再算分值
# ==========================================================
print()
print("=" * 50)
print("第 4 步：融合计算")
print("=" * 50)

# 先一条一条展开：一个关键词算一行，记录它来自 news 还是 weibo
detail_rows = []
for _, row in window_df.iterrows():
    source = row["source_type"]
    if source not in ["news", "weibo"]:
        source = "news"
    for keyword in row["keywords"]:
        detail_rows.append({"keyword": keyword, "source": source})

if len(detail_rows) == 0:
    print("窗口内没有数据，请把 TIME_WINDOW_MINUTES 调大一点再试。")
else:
    detail = pd.DataFrame(detail_rows)

    # 透视成表格：行 = 关键词，列 = news / weibo
    counts = detail.groupby(["keyword", "source"]).size().unstack(fill_value=0)

    if "news" not in counts.columns:
        counts["news"] = 0
    if "weibo" not in counts.columns:
        counts["weibo"] = 0

    # 融合分值 = 新闻数量 x 新闻权重 + 微博数量 x 微博权重
    counts["fused_score"] = counts["news"] * WEIGHT_NEWS + counts["weibo"] * WEIGHT_WEIBO

    result = counts.reset_index()
    result = result[["keyword", "news", "weibo", "fused_score"]]
    result = result.sort_values("fused_score", ascending=False)
    result = result.reset_index(drop=True)

    # ==========================================================
    # 5. 查看结果（对应页面里的结果表格）
    # ==========================================================
    print()
    print("=" * 50)
    print("第 5 步：融合结果（按分值从高到低）")
    print("=" * 50)
    print(result.to_string(index=False))

    # ==========================================================
    # 6. 画图（matplotlib 柱状图）
    # ==========================================================
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # macOS 上显示中文
    plt.rcParams["font.sans-serif"] = ["Arial Unicode MS", "PingFang SC", "Heiti TC"]
    plt.rcParams["axes.unicode_minus"] = False

    top = result.head(10)

    plt.figure(figsize=(10, 5))
    plt.bar(top["keyword"], top["fused_score"], color="#79c0ff")
    plt.title("关键词融合分值排行")
    plt.xlabel("关键词")
    plt.ylabel("融合分值")
    plt.xticks(rotation=30)
    plt.grid(axis="y", linestyle="--", alpha=0.4)
    plt.tight_layout()

    chart_file = os.path.join(OUTPUT_DIR, "fused_score.png")
    plt.savefig(chart_file, dpi=150)
    print()
    print("图表已保存：", chart_file)

    # ==========================================================
    # 7. 导出 CSV（对应「导出数据」按钮）
    # ==========================================================
    now = datetime.now()
    csv_file = os.path.join(OUTPUT_DIR, "fused_data_" + now.strftime("%Y%m%d_%H%M%S") + ".csv")
    result.to_csv(csv_file, index=False, encoding="utf-8-sig")
    print("结果已导出：", csv_file)

print()
print("全部完成。")
