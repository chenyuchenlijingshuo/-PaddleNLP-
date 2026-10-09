<template>
  <section class="view-shell">
    <div class="section-title">
      <div>
        <p class="eyebrow">分析</p>
        <h3>可视化分析工作台</h3>
        <p>支持词云、热点排行、时间趋势、来源统计、条件筛选，以及 PaddleNLP 情感分析与文本分类。</p>
      </div>
      <el-tag effect="dark" :type="nlpStatus.available ? 'success' : 'warning'">
        {{ nlpStatus.available ? "PaddleNLP 已接入" : "PaddleNLP 待就绪" }}
      </el-tag>
    </div>

    <div class="panel-stack">
      <div class="metric-grid metric-grid-quad">
        <div class="metric-card">
          <span>筛选时窗</span>
          <strong>{{ filters.hours }}h</strong>
        </div>
        <div class="metric-card">
          <span>词云项数</span>
          <strong>{{ visualization.wordcloud.length }}</strong>
        </div>
        <div class="metric-card">
          <span>趋势点位</span>
          <strong>{{ visualization.trend.length }}</strong>
        </div>
        <div class="metric-card">
          <span>NLP 状态</span>
          <strong>{{ nlpStatus.sentiment_ready ? "情感可用" : "情感待配置" }}</strong>
        </div>
      </div>

      <div class="glass-panel">
        <div class="section-title">
          <div>
            <p class="mini-label">筛选</p>
            <h3>条件查询</h3>
          </div>
        </div>
        <div class="toolbar">
          <el-input-number v-model="filters.hours" :min="1" :max="720" />
          <el-select v-model="filters.source_type" clearable placeholder="来源类型">
            <el-option label="全部来源" value="" />
            <el-option label="新闻" value="news" />
            <el-option label="微博" value="weibo" />
          </el-select>
          <el-input v-model="filters.keyword" placeholder="关键词筛选" />
          <el-input-number v-model="filters.top_k" :min="5" :max="50" />
          <el-button type="primary" :loading="vizLoading" @click="refreshVisualization">更新图表</el-button>
          <el-button type="success" :loading="batchSentimentLoading" @click="runBatchSentiment">
            批次情感分析
          </el-button>
          <el-button @click="resetFilters">重置</el-button>
        </div>
        <p class="panel-note">提示：批次情感分析会对已采集的原始数据写入情感结果，用于情感分布与明细展示。</p>
      </div>

      <div class="split-grid">
        <div class="glass-panel">
          <div class="section-title">
            <div>
              <p class="mini-label">词云</p>
              <h3>关键词热度云</h3>
            </div>
          </div>
          <div class="keyword-cloud-board">
            <span
              v-for="item in keywordCloudStyled"
              :key="item.name"
              class="keyword-token keyword-token-strong"
              :class="{ 'keyword-token-top': item.rank <= 3 }"
              :title="`${item.name}：${item.value}`"
              :style="{ fontSize: `${item.fontSize}px`, color: item.color, borderColor: item.borderColor }"
            >
              <span class="keyword-token-text">{{ item.name }}</span>
              <small class="keyword-token-score">{{ item.value }}</small>
              <em v-if="item.rank <= 3" class="keyword-token-badge">TOP{{ item.rank }}</em>
            </span>
            <p v-if="!visualization.wordcloud.length" class="empty-note">暂无词云数据。</p>
          </div>
        </div>

        <div class="glass-panel">
          <div class="section-title">
            <div>
              <p class="mini-label">排行</p>
              <h3>热点排行榜</h3>
            </div>
          </div>
          <EChartPanel :option="rankingOption" height="320px" />
        </div>
      </div>

      <div class="split-grid">
        <div class="glass-panel">
          <div class="section-title">
            <div>
              <p class="mini-label">趋势</p>
              <h3>时间趋势图</h3>
            </div>
          </div>
          <EChartPanel :option="trendOption" height="320px" />
        </div>

        <div class="glass-panel">
          <div class="section-title">
            <div>
              <p class="mini-label">来源</p>
              <h3>来源分布统计</h3>
            </div>
          </div>
          <EChartPanel :option="sourceOption" height="320px" />
        </div>
      </div>

      <div class="split-grid">
        <div class="glass-panel sentiment-panel">
          <div class="section-title">
            <div>
              <p class="mini-label">情感</p>
              <h3>情感分布统计</h3>
              <p>来自 PaddleNLP 批次情感分析结果</p>
            </div>
            <div class="sentiment-stats" v-if="visualization.sentiment_distribution?.length">
              <div class="sentiment-stat-item sentiment-positive">
                <span class="sentiment-stat-label">正面</span>
                <strong class="sentiment-stat-value">{{ sentimentStats.positive.count }}</strong>
                <span class="sentiment-stat-percent">{{ sentimentStats.positive.percent }}%</span>
              </div>
              <div class="sentiment-stat-item sentiment-negative">
                <span class="sentiment-stat-label">负面</span>
                <strong class="sentiment-stat-value">{{ sentimentStats.negative.count }}</strong>
                <span class="sentiment-stat-percent">{{ sentimentStats.negative.percent }}%</span>
              </div>
              <div class="sentiment-stat-item sentiment-neutral">
                <span class="sentiment-stat-label">中性</span>
                <strong class="sentiment-stat-value">{{ sentimentStats.neutral.count }}</strong>
                <span class="sentiment-stat-percent">{{ sentimentStats.neutral.percent }}%</span>
              </div>
            </div>
          </div>
          <EChartPanel :option="sentimentOption" height="320px" />
          <div class="sentiment-summary" v-if="visualization.sentiment_distribution?.length">
            <div class="sentiment-summary-item">
              <span class="sentiment-summary-label">总体倾向</span>
              <strong class="sentiment-summary-value" :class="sentimentTrendClass">{{ sentimentTrend }}</strong>
            </div>
            <div class="sentiment-summary-item">
              <span class="sentiment-summary-label">分析样本</span>
              <strong class="sentiment-summary-value">{{ sentimentStats.total }} 条</strong>
            </div>
          </div>
          <p v-if="!visualization.sentiment_distribution?.length" class="empty-note">
            暂无情感分布数据，请先点击「批次情感分析」。
          </p>
        </div>
        <div class="glass-panel">
          <div class="section-title">
            <div>
              <p class="mini-label">提示</p>
              <h3>如何使用</h3>
              <p>建议流程：采集 → 预处理/融合 → 批次情感分析 → 在本页查看情感分布与明细。</p>
            </div>
          </div>
          <div class="quick-entry-list">
            <div class="quick-entry">
              <strong>执行检查清单</strong>
              <p>1) 已采集原始数据 2) 已执行预处理/融合 3) 已点击批次情感分析。</p>
            </div>
            <div class="quick-entry">
              <strong>当前状态</strong>
              <p>
                NLP：{{ nlpStatus.sentiment_ready ? "情感可用" : "情感待配置" }}；
                情感分布项：{{ visualization.sentiment_distribution?.length || 0 }}；
                明细记录：{{ recordsTotal }}。
              </p>
            </div>
            <div class="quick-entry">
              <strong>常见问题</strong>
              <p>若图表无变化，请先点「更新图表」；若情感分布为空，请先执行一次「批次情感分析」。</p>
            </div>
          </div>
          <div class="keyword-cloud-board" style="margin-top: 12px;">
            <span class="keyword-token keyword-token-strong">PaddleNLP</span>
            <span class="keyword-token keyword-token-strong">情感分析</span>
            <span class="keyword-token keyword-token-strong">趋势研判</span>
            <span class="keyword-token keyword-token-strong">风险提示</span>
            <span class="keyword-token keyword-token-strong">来源对比</span>
          </div>
        </div>
      </div>

      <div class="glass-panel">
        <div class="section-title">
          <div>
            <p class="mini-label">明细</p>
            <h3>筛选结果列表</h3>
          </div>
        </div>
        <div class="table-shell">
          <el-table :data="visualization.records" stripe height="460">
            <el-table-column prop="id" label="ID" width="72" />
            <el-table-column prop="title" label="标题" min-width="240" />
            <el-table-column label="来源" width="100">
              <template #default="scope">
                {{ sourceTypeMap[scope.row.source_type] || scope.row.source_type || '未知' }}
              </template>
            </el-table-column>
            <el-table-column prop="keyword_hit" label="命中关键词" min-width="200" />
            <el-table-column label="情感" width="120">
              <template #default="scope">
                {{ sentimentLabelMap[scope.row.sentiment_label] || scope.row.sentiment_label || '未分析' }}
              </template>
            </el-table-column>
            <el-table-column prop="sentiment_score" label="置信度" width="120">
              <template #default="scope">
                {{ scope.row.sentiment_score ? (scope.row.sentiment_score * 100).toFixed(1) + '%' : '-' }}
              </template>
            </el-table-column>
            <el-table-column prop="published_at" label="发布时间" min-width="180" />
          </el-table>
        </div>
        <div class="pager-bar" v-if="recordsTotal">
          <el-pagination
            layout="prev, pager, next, sizes, total"
            :page-size="recordsPager.size"
            :page-sizes="[10, 20, 50, 100, 200]"
            :total="recordsTotal"
            :current-page="recordsPager.page"
            @size-change="onRecordsSizeChange"
            @current-change="onRecordsPageChange"
          />
        </div>
        <p v-if="!visualization.records.length" class="empty-note">暂无符合筛选条件的记录。</p>
      </div>

      <div class="glass-panel">
        <div class="section-title">
          <div>
            <p class="mini-label">NLP</p>
            <h3>PaddleNLP 文本分析</h3>
            <p>{{ nlpGuideText }}</p>
          </div>
        </div>
        <div class="toolbar">
          <el-input
            v-model="nlpInput"
            type="textarea"
            class="wide-input"
            :rows="4"
            placeholder="每行一段文本，用于 PaddleNLP 情感分析和文本分类"
          />
          <el-button type="primary" :disabled="!nlpStatus.sentiment_ready" @click="runSentiment">情感分析</el-button>
          <el-button :disabled="!nlpStatus.classification_ready" @click="runClassify">文本分类</el-button>
        </div>

        <div class="split-grid">
          <div class="table-shell">
            <el-table :data="sentimentRows" stripe>
              <el-table-column prop="text" label="文本" min-width="240" />
              <el-table-column label="情感" width="120">
                <template #default="scope">
                  {{ sentimentLabelMap[scope.row.label] || scope.row.label || '-' }}
                </template>
              </el-table-column>
              <el-table-column label="置信度" width="120">
                <template #default="scope">
                  {{ scope.row.score ? (scope.row.score * 100).toFixed(1) + '%' : '-' }}
                </template>
              </el-table-column>
            </el-table>
          </div>
          <div class="table-shell">
            <el-table :data="classifyRows" stripe>
              <el-table-column prop="text" label="文本" min-width="240" />
              <el-table-column prop="label" label="类别" width="160" />
              <el-table-column label="置信度" width="120">
                <template #default="scope">
                  {{ scope.row.score ? (scope.row.score * 100).toFixed(1) + '%' : '-' }}
                </template>
              </el-table-column>
            </el-table>
          </div>
        </div>
      </div>

      <div class="glass-panel">
        <div class="section-title">
          <div>
            <p class="mini-label">评估</p>
            <h3>模型性能评估</h3>
            <p>基于标注测试集评估 PaddleNLP 情感分析模型的准确率、召回率、F1值等指标。</p>
          </div>
        </div>

        <div class="toolbar eval-toolbar">
          <el-button type="primary" :loading="evalLoading" :disabled="!nlpStatus.sentiment_ready" @click="runEvaluation">
            开始评估
          </el-button>
          <el-button @click="loadDatasetInfo">查看数据集</el-button>
          <el-tag v-if="evalResult.metrics" type="success" effect="dark">
            准确率: {{ (evalResult.metrics.accuracy * 100).toFixed(2) }}%
          </el-tag>
        </div>

        <p class="panel-note eval-note">
          提示：点击"开始评估"按钮，系统将使用标注测试集对 PaddleNLP 情感分析模型进行性能评估，计算准确率、召回率、F1值等关键指标。
        </p>

        <div v-if="datasetInfo.available" class="metric-grid metric-grid-quad eval-dataset-info">
          <div class="metric-card">
            <span>测试样本数</span>
            <strong>{{ datasetInfo.total_samples }}</strong>
          </div>
          <div class="metric-card">
            <span>正面样本</span>
            <strong>{{ datasetInfo.label_distribution.positive || 0 }}</strong>
          </div>
          <div class="metric-card">
            <span>负面样本</span>
            <strong>{{ datasetInfo.label_distribution.negative || 0 }}</strong>
          </div>
          <div class="metric-card">
            <span>中性样本</span>
            <strong>{{ datasetInfo.label_distribution.neutral || 0 }}</strong>
          </div>
        </div>

        <div v-if="evalResult.metrics" class="eval-results">
          <div class="split-grid">
            <div class="eval-section">
              <h4>总体指标</h4>
              <div class="metric-grid metric-grid-quad">
                <div class="metric-card">
                  <span>准确率</span>
                  <strong>{{ (evalResult.metrics.accuracy * 100).toFixed(2) }}%</strong>
                </div>
                <div class="metric-card">
                  <span>宏平均精确率</span>
                  <strong>{{ (evalResult.metrics.macro_avg.precision * 100).toFixed(2) }}%</strong>
                </div>
                <div class="metric-card">
                  <span>宏平均召回率</span>
                  <strong>{{ (evalResult.metrics.macro_avg.recall * 100).toFixed(2) }}%</strong>
                </div>
                <div class="metric-card">
                  <span>宏平均 F1</span>
                  <strong>{{ (evalResult.metrics.macro_avg.f1 * 100).toFixed(2) }}%</strong>
                </div>
              </div>

              <h4 style="margin-top: 24px;">各类别指标</h4>
              <el-table :data="perClassData" stripe>
                <el-table-column prop="label" label="类别" width="120">
                  <template #default="scope">
                    {{ sentimentLabelMap[scope.row.label] || scope.row.label }}
                  </template>
                </el-table-column>
                <el-table-column label="精确率" width="120">
                  <template #default="scope">
                    {{ (scope.row.precision * 100).toFixed(2) }}%
                  </template>
                </el-table-column>
                <el-table-column label="召回率" width="120">
                  <template #default="scope">
                    {{ (scope.row.recall * 100).toFixed(2) }}%
                  </template>
                </el-table-column>
                <el-table-column label="F1值" width="120">
                  <template #default="scope">
                    {{ (scope.row.f1 * 100).toFixed(2) }}%
                  </template>
                </el-table-column>
                <el-table-column prop="support" label="样本数" width="100" />
              </el-table>
            </div>

            <div class="eval-section">
              <h4>混淆矩阵</h4>
              <div class="confusion-matrix">
                <table>
                  <thead>
                    <tr>
                      <th></th>
                      <th v-for="label in evalResult.metrics.confusion_matrix.labels" :key="label">
                        {{ sentimentLabelMap[label] || label }}
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="(row, i) in evalResult.metrics.confusion_matrix.matrix" :key="i">
                      <td class="row-label">{{ sentimentLabelMap[evalResult.metrics.confusion_matrix.labels[i]] }}</td>
                      <td v-for="(cell, j) in row" :key="j" :class="getCellClass(cell, i, j)">
                        {{ cell }}
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>

              <h4 style="margin-top: 24px;">评估信息</h4>
              <div class="eval-info">
                <p><strong>评估时间:</strong> {{ evalResult.evaluation_info.evaluated_at }}</p>
                <p><strong>耗时:</strong> {{ evalResult.evaluation_info.duration_seconds }}秒</p>
                <p><strong>处理速度:</strong> {{ evalResult.evaluation_info.samples_per_second }} 样本/秒</p>
                <p><strong>错误样本数:</strong> {{ evalResult.total_errors }} / {{ evalResult.metrics.total_samples }}</p>
              </div>
            </div>
          </div>

          <div v-if="evalResult.error_samples && evalResult.error_samples.length > 0" style="margin-top: 24px;">
            <h4>错误样本示例（前10条）</h4>
            <el-table :data="evalResult.error_samples" stripe max-height="300">
              <el-table-column prop="index" label="#" width="60" />
              <el-table-column prop="text" label="文本" min-width="200" />
              <el-table-column label="真实标签" width="100">
                <template #default="scope">
                  <el-tag :type="getTagType(scope.row.true_label)">
                    {{ sentimentLabelMap[scope.row.true_label] }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column label="预测标签" width="100">
                <template #default="scope">
                  <el-tag :type="getTagType(scope.row.pred_label)">
                    {{ sentimentLabelMap[scope.row.pred_label] }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column label="置信度" width="100">
                <template #default="scope">
                  {{ scope.row.confidence ? (scope.row.confidence * 100).toFixed(1) + '%' : '-' }}
                </template>
              </el-table-column>
            </el-table>
          </div>
        </div>

        <div v-else class="empty-note">
          <p>点击"开始评估"按钮，对 PaddleNLP 情感分析模型进行性能评估。</p>
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

const filters = reactive({
  hours: 72,
  source_type: "",
  keyword: "",
  top_k: 20,
});

const visualization = reactive({
  wordcloud: [],
  ranking: [],
  trend: [],
  source_distribution: [],
  sentiment_distribution: [],
  records: [],
});

const recordsTotal = ref(0);
const recordsPager = reactive({ page: 1, size: 20 });
const vizLoading = ref(false);
const batchSentimentLoading = ref(false);

const nlpStatus = reactive({
  available: false,
  reason: "",
  sentiment_ready: false,
  classification_ready: false,
});

const nlpInput = ref("这次突发事件在社交平台快速传播，引发了大量负面讨论。\n平台及时回应后，部分用户反馈有所改善。");
const sentimentRows = ref([]);
const classifyRows = ref([]);
const nlpGuideText = computed(() => {
  if (nlpStatus.available && nlpStatus.classification_ready) {
    return "支持对多段文本执行情感分析与文本分类，可用于风险研判和主题归类。";
  }
  if (nlpStatus.available && !nlpStatus.classification_ready) {
    return "当前以情感分析为主，文本分类能力正在优化，可先使用情感分布与明细结果。";
  }
  return "NLP 服务待就绪，请先检查后端环境后再执行批次分析。";
});

const evalLoading = ref(false);
const datasetInfo = reactive({
  available: false,
  total_samples: 0,
  label_distribution: {},
  description: "",
  version: "",
  created_at: "",
});
const evalResult = reactive({
  success: false,
  message: "",
  metrics: null,
  dataset_info: null,
  evaluation_info: null,
  error_samples: [],
  total_errors: 0,
});

const perClassData = computed(() => {
  if (!evalResult.metrics || !evalResult.metrics.per_class) return [];
  return Object.entries(evalResult.metrics.per_class).map(([label, metrics]) => ({
    label,
    ...metrics,
  }));
});

const keywordCloudStyled = computed(() => {
  const list = (visualization.wordcloud || []).slice().sort((a, b) => (b.value || 0) - (a.value || 0));
  if (!list.length) return [];
  const maxValue = Math.max(...list.map((x) => Number(x.value || 0)));
  const minValue = Math.min(...list.map((x) => Number(x.value || 0)));
  const palette = ["#7cc5ff", "#83f2d1", "#f7c873", "#c9a7ff", "#7aa2ff", "#6ee7f0", "#f8a5c2", "#9be28d"];
  return list.map((item, index) => {
    const value = Number(item.value || 0);
    const ratio = maxValue === minValue ? 1 : (value - minValue) / (maxValue - minValue);
    const fontSize = Math.round(14 + ratio * 24); // 14 ~ 38
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

const baseChartStyle = {
  backgroundColor: "transparent",
  textStyle: { color: "#d8e6ff" },
  grid: { left: 96, right: 20, top: 30, bottom: 40, containLabel: true },
};

const rankingOption = computed(() => ({
  ...baseChartStyle,
  xAxis: {
    type: "value",
    axisLabel: { color: "#9db0ce" },
    splitLine: { lineStyle: { color: "rgba(161,191,255,0.08)" } },
  },
  yAxis: {
    type: "category",
    data: visualization.ranking.map((item) => item.keyword),
    axisLabel: { color: "#eff5ff" },
  },
  series: [
    {
      type: "bar",
      data: visualization.ranking.map((item) => item.score),
      itemStyle: {
        borderRadius: [0, 10, 10, 0],
        color: "#39a0ff",
      },
    },
  ],
}));

const trendOption = computed(() => ({
  ...baseChartStyle,
  tooltip: { trigger: "axis" },
  xAxis: {
    type: "category",
    data: visualization.trend.map((item) => item.time),
    axisLabel: { color: "#9db0ce", rotate: 35 },
  },
  yAxis: {
    type: "value",
    axisLabel: { color: "#9db0ce" },
    splitLine: { lineStyle: { color: "rgba(161,191,255,0.08)" } },
  },
  series: [
    {
      type: "line",
      smooth: true,
      data: visualization.trend.map((item) => item.score),
      symbolSize: 8,
      lineStyle: { width: 3, color: "#79c0ff" },
      areaStyle: { color: "rgba(121, 192, 255, 0.18)" },
      itemStyle: { color: "#21d0b2" },
    },
  ],
}));

const sourceTypeMap = {
  news: "新闻",
  weibo: "微博",
  unknown: "未知",
};

const sentimentLabelMap = {
  positive: "正面",
  negative: "负面",
  neutral: "中性",
  unknown: "未知",
};

const sourceOption = computed(() => ({
  ...baseChartStyle,
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
      radius: ["45%", "72%"],
      data: visualization.source_distribution.map((item) => ({
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

const sentimentOption = computed(() => ({
  ...baseChartStyle,
  tooltip: { 
    trigger: "item",
    formatter: (params) => {
      const name = sentimentLabelMap[params.name] || params.name;
      return `${name}: ${params.value} (${params.percent}%)`;
    }
  },
  series: [
    {
      type: "pie",
      radius: ["45%", "72%"],
      data: (visualization.sentiment_distribution || []).map((item) => ({
        name: sentimentLabelMap[item.name] || item.name,
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
      color: ['#00d9ff', '#ff6b9d', '#c4b5fd', '#94a3b8'],
    },
  ],
}));

const sentimentStats = computed(() => {
  const dist = visualization.sentiment_distribution || [];
  const total = dist.reduce((sum, item) => sum + (item.value || 0), 0);
  
  const findCount = (label) => {
    const item = dist.find(d => d.name === label);
    return item ? item.value : 0;
  };
  
  const positive = findCount('positive');
  const negative = findCount('negative');
  const neutral = findCount('neutral');
  
  return {
    total,
    positive: {
      count: positive,
      percent: total > 0 ? ((positive / total) * 100).toFixed(1) : 0
    },
    negative: {
      count: negative,
      percent: total > 0 ? ((negative / total) * 100).toFixed(1) : 0
    },
    neutral: {
      count: neutral,
      percent: total > 0 ? ((neutral / total) * 100).toFixed(1) : 0
    }
  };
});

const sentimentTrend = computed(() => {
  const { positive, negative, neutral } = sentimentStats.value;
  
  if (positive.count > negative.count && positive.count > neutral.count) {
    return '积极向好';
  } else if (negative.count > positive.count && negative.count > neutral.count) {
    return '负面主导';
  } else if (neutral.count > positive.count && neutral.count > negative.count) {
    return '态度中立';
  } else if (positive.count === negative.count && positive.count > 0) {
    return '正负均衡';
  } else {
    return '数据不足';
  }
});

const sentimentTrendClass = computed(() => {
  const trend = sentimentTrend.value;
  if (trend === '积极向好') return 'trend-positive';
  if (trend === '负面主导') return 'trend-negative';
  if (trend === '态度中立') return 'trend-neutral';
  return '';
});

const resetFilters = () => {
  filters.hours = 72;
  filters.source_type = "";
  filters.keyword = "";
  filters.top_k = 20;
  recordsPager.page = 1;
  loadVisualization();
};

const loadVisualization = async () => {
  if (vizLoading.value) return;
  vizLoading.value = true;
  try {
    const { data } = await http.get("/analyze/visualization", {
      params: { ...filters, page: recordsPager.page, size: recordsPager.size },
    });
    Object.assign(visualization, data.data || {});
    recordsTotal.value = data.data?.records_total || 0;
    recordsPager.page = data.data?.records_page || recordsPager.page;
    recordsPager.size = data.data?.records_size || recordsPager.size;
    return true;
  } catch (e) {
    const msg = e.response?.data?.message || e.message || "图表更新失败";
    ElMessage.error(msg);
    return false;
  } finally {
    vizLoading.value = false;
  }
};

const refreshVisualization = async () => {
  const ok = await loadVisualization();
  if (ok) {
    ElMessage.success("图表已更新");
  }
  await loadStatus();
};

const loadStatus = async () => {
  try {
    const { data } = await http.get("/analyze/nlp/status");
    Object.assign(nlpStatus, data.data || {});
  } catch (e) {
    const msg = e.response?.data?.message || e.message || "NLP 状态获取失败";
    ElMessage.warning(msg);
  }
};

const onRecordsPageChange = async (page) => {
  recordsPager.page = page;
  await loadVisualization();
};

const onRecordsSizeChange = async (size) => {
  recordsPager.size = size;
  recordsPager.page = 1;
  await loadVisualization();
};

const buildTexts = () =>
  nlpInput.value
    .split("\n")
    .map((item) => item.trim())
    .filter(Boolean);

const runSentiment = async () => {
  const texts = buildTexts();
  if (!texts.length) {
    ElMessage.warning("请先输入待分析文本");
    return;
  }
  const { data } = await http.post("/analyze/nlp/sentiment", { texts });
  sentimentRows.value = data.data?.items || [];
  if (!data.data?.available) {
    ElMessage.warning(data.data?.message || "情感分析暂不可用");
  }
};

const runClassify = async () => {
  const texts = buildTexts();
  if (!texts.length) {
    ElMessage.warning("请先输入待分析文本");
    return;
  }
  const { data } = await http.post("/analyze/nlp/classify", { texts });
  classifyRows.value = data.data?.items || [];
  if (!data.data?.available) {
    ElMessage.warning(data.data?.message || "文本分类暂不可用");
  }
};

const runBatchSentiment = async () => {
  if (batchSentimentLoading.value) return;
  batchSentimentLoading.value = true;
  try {
    const { data } = await http.post("/process/nlp/sentiment/run", { limit: 300, only_missing: true }, { timeout: 600000 });
    if (data.code !== 0) {
      ElMessage.error(data.message || "批次情感分析失败");
      return;
    }
    const msg = data.data?.message || "ok";
    ElMessage.success(`批次情感分析完成（${msg}）`);
    await loadVisualization();
  } catch (e) {
    const msg = e.response?.data?.message || e.message || "批次情感分析失败";
    ElMessage.error(msg);
  } finally {
    batchSentimentLoading.value = false;
  }
};

const loadDatasetInfo = async () => {
  try {
    const { data } = await http.get("/analyze/nlp/dataset/info");
    Object.assign(datasetInfo, data.data || {});
    if (datasetInfo.available) {
      ElMessage.success(`数据集已加载，共 ${datasetInfo.total_samples} 个样本`);
    } else {
      ElMessage.warning("测试数据集未找到");
    }
  } catch (e) {
    const msg = e.response?.data?.message || e.message || "数据集信息获取失败";
    ElMessage.error(msg);
  }
};

const runEvaluation = async () => {
  if (evalLoading.value) return;
  evalLoading.value = true;
  try {
    ElMessage.info("开始评估模型性能，请稍候...");
    const { data } = await http.get("/analyze/nlp/evaluate", { timeout: 300000 });
    const result = data.data || {};

    if (result.success) {
      Object.assign(evalResult, result);
      ElMessage.success(`评估完成！准确率: ${(result.metrics.accuracy * 100).toFixed(2)}%`);
    } else {
      ElMessage.error(result.message || "评估失败");
    }
  } catch (e) {
    const msg = e.response?.data?.message || e.message || "评估失败";
    ElMessage.error(msg);
  } finally {
    evalLoading.value = false;
  }
};

const getTagType = (label) => {
  if (label === "positive") return "success";
  if (label === "negative") return "danger";
  if (label === "neutral") return "info";
  return "";
};

const getCellClass = (cell, i, j) => {
  if (i === j) return "diagonal";
  if (cell > 0) return "error";
  return "";
};

onMounted(async () => {
  await Promise.all([loadVisualization(), loadStatus(), loadDatasetInfo()]);
});
</script>
