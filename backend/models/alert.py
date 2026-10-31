"""
微博平台下消费数码新品首发的舆情洞察与策略分析
================================================

预警数据模型 —— 适配研究主题：iPhone Duo 首销事件。

预警类型（metric_type）：
    threshold        阈值预警（热度 / 条数）
    sensitive        敏感词预警（关键词匹配）
    anomaly          异常检测预警（滑动窗口 z-score）
    launch_campaign  首发专项预警（按 iPhone Duo 首发阶段分桶）

规则类别（rule_category）：
    general          通用预警
    pre_launch       首发前：预热声量 / 黄牛接单 / 价格讨论
    launch_day       首发日：15min 滚动热度异常 / 负面情感集中爆发
    post_launch      首发后：BUG / 差评 / 续航发热槽点
"""

from datetime import datetime

from extensions import db

# —— 规则类别常量（Dictionary）——
CATEGORY_GENERAL = "general"
CATEGORY_PRE_LAUNCH = "pre_launch"
CATEGORY_LAUNCH_DAY = "launch_day"
CATEGORY_POST_LAUNCH = "post_launch"

VALID_CATEGORIES = {CATEGORY_GENERAL, CATEGORY_PRE_LAUNCH, CATEGORY_LAUNCH_DAY, CATEGORY_POST_LAUNCH}  # Ch8 Set

CATEGORY_LABELS = {  
    CATEGORY_GENERAL: "通用预警",
    CATEGORY_PRE_LAUNCH: "首发前",
    CATEGORY_LAUNCH_DAY: "首发日",
    CATEGORY_POST_LAUNCH: "首发后",
}

# iPhone Duo 首发场景默认负面关键词
DEFAULT_LAUNCH_NEGATIVE = (
    "bug,发热,续航差,信号差,差评,翻车,割韭菜,黄牛,"
    "价格虚高,掉帧,闪退,屏幕问题,漏液,进灰,缝隙大"
)
DEFAULT_LAUNCH_POSITIVE = "真香,值得买,首发必入,香爆,推荐买"


class AlertRule(db.Model):
    """
    预警规则模型
    """
    __tablename__ = "alert_rules"  
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    metric_type = db.Column(db.String(32), nullable=False)           # threshold/sensitive/anomaly/launch_campaign
    rule_category = db.Column(db.String(32), default=CATEGORY_GENERAL, index=True)

    
    threshold_value = db.Column(db.Float)
    level1_threshold = db.Column(db.Float)
    level2_threshold = db.Column(db.Float)
    sensitive_words = db.Column(db.Text)        # 逗号分隔
    positive_words = db.Column(db.Text)         # 逗号分隔
    negative_words = db.Column(db.Text)         # 逗号分隔

    anomaly_window_minutes = db.Column(db.Integer, default=60)
    zscore_threshold = db.Column(db.Float, default=2.5)

    enabled = db.Column(db.Boolean, default=True)
    scan_cron = db.Column(db.String(64))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class AlertLog(db.Model):
   """预警日志模型 —— 冗余 category / chart_path 便于分组 + Matplotlib 图"""
    
    __tablename__ = "alert_logs"

    id = db.Column(db.Integer, primary_key=True)
    rule_id = db.Column(db.Integer, db.ForeignKey("alert_rules.id"))
    category = db.Column(db.String(32), default=CATEGORY_GENERAL, index=True)
    level = db.Column(db.Integer, default=0)
    message = db.Column(db.Text)
    metric_type = db.Column(db.String(32))
    data_snapshot = db.Column(db.Text)
    chart_path = db.Column(db.String(256))     # Matplotlib 生成图片相对路径
    triggered_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    rule = db.relationship("AlertRule", backref="logs")
