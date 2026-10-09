<template>
  <section class="view-shell">
    <div class="section-title">
      <div>
        <p class="eyebrow">首页</p>
        <h3>系统态势总览</h3>
        <p>聚合舆情规模、近期热点、预警动态和快捷入口。</p>
      </div>
      <el-button type="primary" :loading="loading" @click="load">刷新总览</el-button>
    </div>

    <div class="panel-stack">
      <div class="metric-grid metric-grid-quad">
        <div v-for="card in overview.cards" :key="card.label" class="metric-card metric-card-strong">
          <span>{{ card.label }}</span>
          <strong>{{ card.value }}{{ card.unit || "" }}</strong>
          <small>{{ card.delta == null ? "实时状态" : `变化 ${card.delta}${card.unit || ""}` }}</small>
        </div>
      </div>

      <div class="hero-board">
        <div class="glass-panel hero-ranking-panel">
          <div class="section-title">
            <div>
              <p class="eyebrow">全局态势</p>
              <h3>热点排行总览</h3>
              <p>展示当前融合主题中的高热度关键词，方便快速识别主要舆情焦点。</p>
            </div>
          </div>
          
          <div class="ranking-stats">
            <div class="ranking-stat-item">
              <span class="ranking-stat-label">热点词数</span>
              <strong class="ranking-stat-value">{{ overview.hot_keywords.length }}</strong>
            </div>
            <div class="ranking-stat-item">
              <span class="ranking-stat-label">最高热度</span>
              <strong class="ranking-stat-value">{{ maxHotScore }}</strong>
            </div>
            <div class="ranking-stat-item">
              <span class="ranking-stat-label">平均热度</span>
              <strong class="ranking-stat-value">{{ avgHotScore }}</strong>
            </div>
          </div>
          
          <EChartPanel :option="heroRankingOption" height="280px" />
          
          <div class="rank-list" v-if="overview.hot_keywords.length">
            <div class="rank-list-header">
              <span class="rank-list-title">TOP 3 热点关键词</span>
              <span class="rank-list-hint">点击可跳转至分析页面</span>
            </div>
            <button
              v-for="(item, index) in overview.hot_keywords.slice(0, 3)"
              :key="`${item.keyword}-${index}`"
              type="button"
              class="rank-row"
              :class="`rank-row-${index + 1}`"
              @click="$emit('navigate', 'analyze')"
            >
              <span class="rank-index">{{ String(index + 1).padStart(2, '0') }}</span>
              <span class="rank-label">{{ item.keyword }}</span>
              <strong class="rank-score">{{ item.score }}</strong>
            </button>
          </div>
          <p v-else class="empty-note">暂无热点排行数据，请先完成采集与融合。</p>
        </div>

        <div class="hero-board-stats">
          <div class="hero-stat">
            <span>热点词数</span>
            <strong>{{ overview.hot_keywords.length }}</strong>
          </div>
          <div class="hero-stat">
            <span>预警条数</span>
            <strong>{{ overview.warnings.length }}</strong>
          </div>
          <div class="hero-stat">
            <span>来源类型</span>
            <strong>{{ overview.source_distribution.length }}</strong>
          </div>
          <div class="glass-panel">
            <div class="section-title">
              <div>
                <p class="mini-label">来源</p>
                <h3>来源占比</h3>
              </div>
            </div>
            <EChartPanel :option="heroSourceOption" height="220px" />
            <p v-if="!overview.source_distribution.length" class="empty-note">暂无来源分布数据。</p>
          </div>
        </div>
      </div>

      <div class="split-grid split-grid-3-2">
        <div class="glass-panel">
          <div class="section-title">
            <div>
              <p class="mini-label">热点</p>
              <h3>近期热点</h3>
            </div>
          </div>
          <div class="rank-list">
            <button
              v-for="(item, index) in overview.hot_keywords"
              :key="`${item.keyword}-${index}`"
              type="button"
              class="rank-row"
              @click="$emit('navigate', 'analyze')"
            >
              <span class="rank-index">{{ String(index + 1).padStart(2, '0') }}</span>
              <span class="rank-label">{{ item.keyword }}</span>
              <strong>{{ item.score }}</strong>
            </button>
            <p v-if="!overview.hot_keywords.length" class="empty-note">暂无热点数据。</p>
          </div>
        </div>

        <div class="glass-panel">
          <div class="section-title">
            <div>
              <p class="mini-label">预警</p>
              <h3>预警提示</h3>
            </div>
          </div>
          <div class="warning-list">
            <div v-for="item in overview.warnings" :key="item.id" class="warning-item">
              <div class="warning-badge" :class="item.level === 2 ? 'danger' : 'warning'">L{{ item.level || "-" }}</div>
              <div>
                <strong>{{ item.message }}</strong>
                <p>{{ item.triggered_at || "暂无时间" }}</p>
              </div>
            </div>
            <p v-if="!overview.warnings.length" class="empty-note">暂无预警记录。</p>
          </div>
        </div>
      </div>

      <div class="split-grid">
        <div class="glass-panel keyword-panel">
          <div class="section-title">
            <div>
              <p class="mini-label">词项</p>
              <h3>关键词摘要</h3>
            </div>
          </div>
          
          <div class="keyword-stats">
            <div class="keyword-stat-item">
              <span class="keyword-stat-label">关键词总数</span>
              <strong class="keyword-stat-value">{{ overview.keyword_brief.length }}</strong>
            </div>
            <div class="keyword-stat-item">
              <span class="keyword-stat-label">最高热度</span>
              <strong class="keyword-stat-value">{{ maxKeywordScore }}</strong>
            </div>
            <div class="keyword-stat-item">
              <span class="keyword-stat-label">平均热度</span>
              <strong class="keyword-stat-value">{{ avgKeywordScore }}</strong>
            </div>
          </div>
          
          <div class="keyword-cloud-lite">
            <span
              v-for="item in keywordBriefStyled"
              :key="item.term"
              class="keyword-token keyword-token-strong"
              :class="{ 'keyword-token-top': item.rank <= 3 }"
              :title="`${item.term}：${item.score}`"
              :style="{ fontSize: `${item.fontSize}px`, color: item.color, borderColor: item.borderColor }"
            >
              <span class="keyword-token-text">{{ item.term }}</span>
              <small class="keyword-token-score">{{ item.score }}</small>
              <em v-if="item.rank <= 3" class="keyword-token-badge">TOP{{ item.rank }}</em>
            </span>
            <p v-if="!overview.keyword_brief.length" class="empty-note">暂无词项摘要。</p>
          </div>
          
          <div class="keyword-legend" v-if="overview.keyword_brief.length">
            <div class="legend-item">
              <span class="legend-dot legend-dot-top"></span>
              <span>TOP 3 热词</span>
            </div>
            <div class="legend-item">
              <span class="legend-dot legend-dot-normal"></span>
              <span>普通关键词</span>
            </div>
            <div class="legend-item">
              <span class="legend-hint">字体大小表示热度高低</span>
            </div>
          </div>
        </div>

        <div class="glass-panel">
          <div class="section-title">
            <div>
              <p class="mini-label">入口</p>
              <h3>快捷入口</h3>
            </div>
          </div>
          <div class="quick-entry-list">
            <button
              v-for="entry in overview.quick_entries"
              :key="entry.key"
              type="button"
              class="quick-entry"
              @click="$emit('navigate', entry.key)"
            >
              <strong>{{ entry.title }}</strong>
              <p>{{ entry.desc }}</p>
            </button>
          </div>
        </div>
      </div>
    </div>
    <BackToTop />
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import http from "../api/http";
import EChartPanel from "../components/EChartPanel.vue";
import BackToTop from "../components/BackToTop.vue";

defineEmits(["navigate"]);

const overview = reactive({
  cards: [],
  hot_keywords: [],
  warnings: [],
  keyword_brief: [],
  source_distribution: [],
  quick_entries: [],
});
const loading = ref(false);
const CACHE_KEY = "dashboard_overview_cache_v1";

const loadFromCache = () => {
  try {
    const raw = localStorage.getItem(CACHE_KEY);
    if (!raw) return;
    const cached = JSON.parse(raw);
    if (cached && typeof cached === "object") {
      Object.assign(overview, cached);
    }
  } catch {
    // ignore
  }
};

const saveToCache = () => {
  try {
    localStorage.setItem(CACHE_KEY, JSON.stringify({ ...overview }));
  } catch {
    // ignore
  }
};

const baseChartStyle = {
  backgroundColor: "transparent",
  textStyle: { color: "#d8e6ff" },
  grid: { left: 96, right: 18, top: 24, bottom: 28, containLabel: true },
};

const heroRankingOption = computed(() => {
  const keywords = overview.hot_keywords.map((item) => item.keyword);
  const scores = overview.hot_keywords.map((item) => item.score);
  const maxScore = Math.max(...scores, 1);
  
  return {
    ...baseChartStyle,
    tooltip: { 
      trigger: "axis",
      backgroundColor: 'rgba(7, 20, 36, 0.95)',
      borderColor: 'rgba(121, 192, 255, 0.3)',
      textStyle: { color: '#eff5ff' },
      formatter: (params) => {
        if (!params || !params.length) return '';
        const { name, value } = params[0];
        return `<div style="font-weight: 600; margin-bottom: 4px;">${name}</div><div>热度: ${value}</div>`;
      }
    },
    xAxis: {
      type: "value",
      axisLabel: { color: "#9db0ce" },
      splitLine: { lineStyle: { color: "rgba(161,191,255,0.08)" } },
    },
    yAxis: {
      type: "category",
      data: keywords,
      axisLabel: { 
        color: "#eff5ff",
        fontWeight: 500,
      },
    },
    series: [
      {
        type: "bar",
        data: scores.map((score, index) => ({
          value: score,
          itemStyle: {
            borderRadius: [0, 10, 10, 0],
            color: {
              type: 'linear',
              x: 0,
              y: 0,
              x2: 1,
              y2: 0,
              colorStops: [
                { offset: 0, color: index === 0 ? '#4facfe' : index === 1 ? '#667eea' : index === 2 ? '#a8edea' : '#39a0ff' },
                { offset: 1, color: index === 0 ? '#00f2fe' : index === 1 ? '#764ba2' : index === 2 ? '#fed6e3' : '#667eea' },
              ],
            },
            shadowColor: index < 3 ? 'rgba(79, 172, 254, 0.4)' : 'rgba(57, 160, 255, 0.3)',
            shadowBlur: 10,
          },
        })),
        barWidth: 16,
        animationDelay: (idx) => idx * 100,
        animationEasing: 'elasticOut',
      },
    ],
    animationDuration: 1000,
    animationEasing: 'cubicOut',
  };
});

const sourceTypeMap = {
  news: "新闻",
  weibo: "微博",
  unknown: "未知",
};

const heroSourceOption = computed(() => ({
  backgroundColor: "transparent",
  tooltip: { 
    trigger: "item",
    formatter: (params) => {
      const name = sourceTypeMap[params.name] || params.name;
      return `${name}: ${params.value} (${params.percent}%)`;
    }
  },
  series: [
    {
      type: "pie",
      radius: ["48%", "72%"],
      center: ["50%", "50%"],
      data: overview.source_distribution.map((item) => ({
        name: sourceTypeMap[item.name] || item.name,
        value: item.value,
      })),
      label: { 
        color: "#eff5ff",
        formatter: "{b}: {c} ({d}%)"
      },
      itemStyle: {
        borderColor: "rgba(7,17,31,0.85)",
        borderWidth: 2,
      },
      color: ['#667eea', '#f093fb', '#4facfe', '#43e97b'],
    },
  ],
}));

const keywordBriefStyled = computed(() => {
  const list = (overview.keyword_brief || []).slice().sort((a, b) => (b.score || 0) - (a.score || 0));
  if (!list.length) return [];
  const maxValue = Math.max(...list.map((x) => Number(x.score || 0)));
  const minValue = Math.min(...list.map((x) => Number(x.score || 0)));
  const palette = ["#7cc5ff", "#83f2d1", "#f7c873", "#c9a7ff", "#7aa2ff", "#6ee7f0", "#f8a5c2", "#9be28d"];
  return list.map((item, index) => {
    const value = Number(item.score || 0);
    const ratio = maxValue === minValue ? 1 : (value - minValue) / (maxValue - minValue);
    const fontSize = Math.round(14 + ratio * 18);
    const color = palette[index % palette.length];
    return {
      ...item,
      rank: index + 1,
      fontSize,
      color,
      borderColor: `${color}66`,
    };
  });
});

const maxKeywordScore = computed(() => {
  const list = overview.keyword_brief || [];
  if (!list.length) return 0;
  return Math.max(...list.map((x) => Number(x.score || 0)));
});

const avgKeywordScore = computed(() => {
  const list = overview.keyword_brief || [];
  if (!list.length) return 0;
  const sum = list.reduce((acc, x) => acc + Number(x.score || 0), 0);
  return (sum / list.length).toFixed(1);
});

const maxHotScore = computed(() => {
  const list = overview.hot_keywords || [];
  if (!list.length) return 0;
  return Math.max(...list.map((x) => Number(x.score || 0)));
});

const avgHotScore = computed(() => {
  const list = overview.hot_keywords || [];
  if (!list.length) return 0;
  const sum = list.reduce((acc, x) => acc + Number(x.score || 0), 0);
  return (sum / list.length).toFixed(1);
});

const load = async () => {
  if (loading.value) return;
  loading.value = true;
  try {
    const { data } = await http.get("/dashboard/overview");
    Object.assign(overview, data.data || {});
    saveToCache();
    ElMessage.success("总览已刷新");
  } catch (e) {
    const msg = e.response?.data?.message || e.message || "刷新失败";
    ElMessage.error(msg);
  } finally {
    loading.value = false;
  }
};

onMounted(loadFromCache);
</script>
