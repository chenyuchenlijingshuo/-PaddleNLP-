<template>
  <section class="view-shell">
    <div class="section-title">
      <div>
        <p class="eyebrow">预警</p>
        <h3>iPhone Duo 首销事件 · 舆情预警中心</h3>
        <p>
          基于 Pandas DataFrame / NumPy / 正则匹配 / Matplotlib 图表的预警流水线，
          覆盖首发前 / 首发日 / 首发后 三阶段专项规则。
        </p>
      </div>
      
    </div><div class="header-tags">
        <el-tag effect="dark" type="danger">两级预警</el-tag>
        <el-tag effect="dark" type="warning" v-if="anomalyCount > 0">
          异常规则 {{ anomalyCount }}
        </el-tag>
      </div>

    <div class="panel-stack">
      <div class="metric-grid metric-grid-quad">
         <div class="metric-card">
          <span>今日日志</span>
          <strong>{{ logs.length }}</strong>
        </div>
        <div class="metric-card">
          <span>启用规则</span>
          <strong>{{ enabledCount }}</strong>
        </div>
        <div class="metric-card">
          <span>首发专项</span>
          <strong>{{ campaignCount }}</strong>
        </div>
        <div class="metric-card">
          <span>Matplotlib 图</span>
          <strong>{{ chartCount }}</strong>
        </div>
      </div>

      <!-- iPhone Duo 首发专项概览卡 -->
      <div class="glass-panel launch-campaign-card">
        <div class="section-title">
          <div>
            <p class="mini-label">专项</p>
            <h3>iPhone Duo 首销事件 · 规则分组</h3>
            <p>一键写入默认 5 条规则，覆盖首发前 / 首发日 / 首发后 / 通用敏感词 / 异常检测。</p>
          </div>
          <div class="campaign-actions">
            <el-button type="success" :loading="seedLoading" @click="seedDefaults">
              📋 一键写入默认规则
            </el-button>
            <el-button type="danger" plain :loading="scanLoading" @click="scan">
              🔴 立即扫描
            </el-button>
          </div>
        </div>

        <div class="campaign-grid">
          <div
            v-for="cat in categoryCards"
            :key="cat.key"
            class="campaign-tile"
            :class="cat.key"
          >
            <div class="campaign-tile-icon">{{ cat.icon }}</div>
            <div class="campaign-tile-body">
              <div class="campaign-tile-title">{{ cat.label }}</div>
              <div class="campaign-tile-desc">{{ cat.desc }}</div>
              <div class="campaign-tile-count">
                规则数：<strong>{{ cat.count }}</strong>
                <span v-if="cat.recentLogs" class="recent-chip">
                  近 24h 触发 {{ cat.recentLogs }}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
<!-- 规则创建 / 编辑 -->
      <div class="glass-panel">
         <div class="section-title">
          <div>
            <p class="mini-label">设置</p>
            <h3>{{ editingRule ? "编辑规则" : "新建规则" }}</h3>
          </div>
          <el-button v-if="editingRule" @click="resetForm">取消编辑</el-button>
        </div>
        <el-form :model="rule" label-width="140px" class="rule-form">
          <el-row :gutter="16">
            <el-col :span="8">
              <el-form-item label="规则名称">
                <el-input v-model="rule.name" placeholder="如：iPhone Duo 首发日热度异常" />
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="预警类型">
                <el-select v-model="rule.metric_type" style="width: 100%">
                  <el-option label="阈值预警（threshold）" value="threshold" />
                  <el-option label="敏感词预警（sensitive）" value="sensitive" />
                  <el-option label="异常检测（anomaly · z-score）" value="anomaly" />
                  <el-option label="首发专项（launch_campaign）" value="launch_campaign" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="规则类别">
                <el-select v-model="rule.rule_category" style="width: 100%">
                  <el-option label="通用预警" value="general" />
                  <el-option label="首发前" value="pre_launch" />
                  <el-option label="首发日" value="launch_day" />
                  <el-option label="首发后" value="post_launch" />
                </el-select>
              </el-form-item>
            </el-col>
          </el-row>

          <el-row :gutter="16">
            <el-col :span="6">
              <el-form-item label="阈值 value">
                <el-input-number v-model="rule.threshold_value" :min="0" :precision="2" :step="5" style="width: 100%" />
              </el-form-item>
            </el-col>
            <el-col :span="6">
              <el-form-item label="一级阈值">
                <el-input-number v-model="rule.level1_threshold" :min="0" :precision="2" :step="5" style="width: 100%" />
              </el-form-item>
            </el-col>
            <el-col :span="6">
              <el-form-item label="二级阈值">
                <el-input-number v-model="rule.level2_threshold" :min="0" :precision="2" :step="5" style="width: 100%" />
              </el-form-item>
            </el-col>
            <el-col :span="6" v-if="rule.metric_type === 'anomaly'">
              <el-form-item label="z-score 阈值">
                <el-input-number v-model="rule.zscore_threshold" :min="1" :max="6" :step="0.5" :precision="2" style="width: 100%" />
              </el-form-item>
            </el-col>
            <el-col :span="6" v-if="rule.metric_type === 'anomaly'">
              <el-form-item label="窗口(分钟)">
                <el-input-number v-model="rule.anomaly_window_minutes" :min="15" :max="720" :step="15" style="width: 100%" />
              </el-form-item>
            </el-col>
          </el-row>

          <el-row :gutter="16">
            <el-col :span="8">
              <el-form-item label="敏感词（逗号分隔）">
                <el-input v-model="rule.sensitive_words" placeholder="bug,发热,续航差,黄牛" />
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="负面关键词">
                <el-input v-model="rule.negative_words" placeholder="负面关键词（regex 友好）" />
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="正面关键词">
                <el-input v-model="rule.positive_words" placeholder="用于对比基线" />
              </el-form-item>
            </el-col>
          </el-row>

          <div class="toolbar form-toolbar">
            <el-button type="primary" :loading="createLoading" @click="submitRule">
              {{ editingRule ? "保存修改" : "创建规则" }}
            </el-button>
            <el-button type="danger" plain :loading="scanLoading" @click="scan">扫描</el-button>
            <el-button :loading="logsLoading" @click="refreshLogs">刷新日志</el-button>
            <el-switch v-model="rule.enabled" active-text="启用" inactive-text="停用" class="form-switch" />
          </div>
        </el-form>
      </div>

       <!-- 规则列表 -->
      <div class="glass-panel">
       <div class="section-title">
          <div>
            <p class="mini-label">规则</p>
            <h3>已创建规则（{{ rules.length }}）</h3>
          </div>
        </div>
        <div class="table-shell">
         <el-table :data="rules" stripe height="360">
            <el-table-column prop="id" label="ID" width="72" />
            <el-table-column prop="name" label="规则名称" min-width="220" />
            <el-table-column label="类型" width="140">
              <template #default="{ row }">
                <el-tag :type="metricTypeTag(row.metric_type)" size="small">
                  {{ metricTypeLabel(row.metric_type) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="类别" width="120">
              <template #default="{ row }">
                <el-tag :type="categoryTag(row.rule_category)" size="small" effect="plain">
                  {{ categoryLabel(row.rule_category) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="阈值" width="160">
              <template #default="{ row }">
                <span v-if="row.metric_type === 'anomaly'">
                  z={{ row.zscore_threshold }} / {{ row.anomaly_window_minutes }}min
                </span>
                <span v-else-if="row.metric_type === 'sensitive'">
                  L1={{ row.level1_threshold || "-" }} / L2={{ row.level2_threshold || "-" }}
                </span>
                <span v-else>
                  L1={{ row.level1_threshold || "-" }} / L2={{ row.level2_threshold || "-" }}
                </span>
              </template>
            </el-table-column>
             <el-table-column label="关键词" min-width="200">
              <template #default="{ row }">
                {{ (row.negative_words || row.sensitive_words || "").split(",").slice(0, 4).join(" / ") || "-" }}
              </template>
            </el-table-column>
            <el-table-column label="状态" width="80">
              <template #default="{ row }">
                <el-tag size="small" :type="row.enabled ? 'success' : 'info'">
                  {{ row.enabled ? "启用" : "停用" }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="180">
              <template #default="{ row }">
                <el-button size="small" type="primary" plain @click="editRule(row)">编辑</el-button>
                <el-button size="small" type="success" plain @click="toggleRule(row)">
                  {{ row.enabled ? "停用" : "启用" }}
                </el-button>
                <el-button size="small" type="danger" plain @click="deleteRule(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
        <p v-if="!rules.length" class="empty-note">暂无规则，请先"一键写入默认规则"或手动创建。</p>
      </div>

      <!-- 预警日志（带 category / Matplotlib 图表） -->
      <div class="glass-panel">
        <div class="section-title">
          <div>
            <p class="mini-label">日志</p>
            <h3>预警记录（{{ logsTotal }}）</h3>
          </div>
          <div class="toolbar">
            <el-select v-model="logsFilterCategory" clearable placeholder="按类别筛选" style="width: 180px">
              <el-option label="通用预警" value="general" />
              <el-option label="首发前" value="pre_launch" />
              <el-option label="首发日" value="launch_day" />
              <el-option label="首发后" value="post_launch" />
            </el-select>
          </div>
        </div>
        <div class="table-shell">
          <el-table :data="logs" stripe height="480">
            <el-table-column prop="id" label="ID" width="72" />
            <el-table-column label="级别" width="100">
             <template #default="{ row }">
                <el-tag :type="levelTag(row.level)" size="small">
                  {{ levelLabel(row.level) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="类别" width="110">
              <template #default="{ row }">
                <el-tag :type="categoryTag(row.category)" size="small" effect="plain">
                  {{ categoryLabel(row.category) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="类型" width="110">
              <template #default="{ row }">{{ metricTypeLabel(row.metric_type) }}</template>
            </el-table-column>
            <el-table-column prop="message" label="消息" min-width="320" show-overflow-tooltip />
            <el-table-column label="Matplotlib 图" width="130">
              <template #default="{ row }">
                <el-button
                  v-if="row.chart_path"
                  size="small"
                  type="primary"
                  link
                  @click.stop="openChart(row)"
                >📈 查看</el-button>
                <span v-else class="no-chart">-</span>
              </template>
            </el-table-column>
            <el-table-column prop="triggered_at" label="触发时间" width="180" />
          </el-table>
        </div>
        <div class="pager-bar" v-if="logsTotal">
          <el-pagination
            layout="prev, pager, next, sizes, total"
            :page-size="logsPager.size"
            :page-sizes="[10, 20, 50, 100, 200]"
            :total="logsTotal"
            :current-page="logsPager.page"
            @size-change="onLogsSizeChange"
            @current-change="onLogsPageChange"
          />
        </div>
        <p v-if="!logs.length" class="empty-note">暂无预警记录。</p>
      </div>
    </div>

    <!-- Matplotlib 图表预览弹窗 -->
    <el-dialog v-model="chartDialogVisible" :title="`预警图表 · ${chartDialogRuleName || ''}`" width="720px">
      <div class="chart-dialog-body">
        <img
          v-if="chartDialogUrl"
          :src="chartDialogUrl"
          alt="预警图表"
          class="chart-preview-img"
          @error="onChartLoadError"
        />
        <p v-else class="empty-note">图表加载失败（可能尚未生成或已过期）。</p>
      </div>
    </el-dialog>
    <BackToTop />
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import http from "../api/http";
import BackToTop from "../components/BackToTop.vue";

// —— 新建 / 编辑表单 ——
const editingRuleId = ref(null);
const editingRule = ref(null);
const rule = ref({
  name: "",
  metric_type: "launch_campaign",
  rule_category: "launch_day",
  threshold_value: 15,
  level1_threshold: 15,
  level2_threshold: 40,
  sensitive_words: "",
  negative_words: "",
  positive_words: "",
  anomaly_window_minutes: 30,
  zscore_threshold: 2.5,
  enabled: true,
});

// —— 规则列表 ——
const rules = ref([]);
const rulesLoading = ref(false);

// —— 日志 ——  
const logs = ref([]);
const logsTotal = ref(0);
const logsPager = ref({ page: 1, size: 20 });
const logsFilterCategory = ref("");
const logsLoading = ref(false);

// —— 其它 ——
const createLoading = ref(false);
const scanLoading = ref(false);
const seedLoading = ref(false);
const DASHBOARD_CACHE_KEY = "dashboard_overview_cache_v1";

// —— Matplotlib 图表弹窗 ——
const chartDialogVisible = ref(false);
const chartDialogUrl = ref("");
const chartDialogRuleName = ref("");

// —— 派生统计 ——
const enabledCount = computed(() => rules.value.filter((r) => r.enabled).length);
const campaignCount = computed(() =>
  rules.value.filter((r) => r.metric_type === "launch_campaign" || r.metric_type === "anomaly").length
);
const anomalyCount = computed(() => rules.value.filter((r) => r.metric_type === "anomaly").length);
const chartCount = computed(() => logs.value.filter((l) => l.chart_path).length);

// —— 首发专项分组卡 ——
const categoryCards = computed(() => {
  const map = {
    pre_launch:   { icon: "🔥", label: "首发前",     desc: "黄牛接单 / 价格讨论 / 预热热度" },
    launch_day:   { icon: "🚀", label: "首发日",     desc: "15min 滚动热度异常 / 负面情感集中" },
    post_launch:  { icon: "🔧", label: "首发后",     desc: "BUG / 硬件 / 差评 集中爆发" },
    general:      { icon: "📰", label: "通用敏感词", desc: "负面关键词 / 正则匹配" },
  };
  const recentByCat = { pre_launch: 0, launch_day: 0, post_launch: 0, general: 0 };
  for (const l of logs.value) {
    if (l.chart_path && l.category) recentByCat[l.category] = (recentByCat[l.category] || 0) + 1;
  }
  return Object.entries(map).map(([key, info]) => ({
    key,
    ...info,
    count: rules.value.filter((r) => r.rule_category === key).length,
    recentLogs: recentByCat[key] || 0,
  }));
});

// —— 标签辅助 ——
const metricTypeLabel = (t) =>
  ({ threshold: "阈值预警", sensitive: "敏感词", anomaly: "异常检测", launch_campaign: "首发专项" }[t] || t);
const metricTypeTag = (t) =>
  ({ threshold: "", sensitive: "warning", anomaly: "success", launch_campaign: "danger" }[t] || "");
const categoryLabel = (c) =>
  ({ general: "通用", pre_launch: "首发前", launch_day: "首发日", post_launch: "首发后" }[c] || c);
const categoryTag = (c) =>
  ({ general: "info", pre_launch: "", launch_day: "danger", post_launch: "warning" }[c] || "info");
const levelLabel = (lv) => ({ 0: "信息", 1: "一级轻度", 2: "二级重度" }[lv] || `Lv${lv}`);
const levelTag = (lv) => ({ 0: "info", 1: "warning", 2: "danger" }[lv] || "");

// —— 加载 ——
const loadRules = async () => {
  if (rulesLoading.value) return;
  rulesLoading.value = true;
  try {
    const { data } = await http.get("/alert/rules");
    rules.value = data.data || [];
  } catch (e) {
    ElMessage.error(e.response?.data?.message || "规则加载失败");
  } finally {
    rulesLoading.value = false;
  }
};

const loadLogs = async ({ notify = false } = {}) => {
  if (logsLoading.value) return;
  logsLoading.value = true;
  try {
    const params = { ...logsPager.value };
    if (logsFilterCategory.value) params.category = logsFilterCategory.value;
    const { data } = await http.get("/alert/logs", { params });
    logs.value = data.data?.items || [];
    logsTotal.value = data.data?.total || 0;
    if (notify) ElMessage.success("日志已刷新");
  } catch (e) {
    ElMessage.error(e.response?.data?.message || "日志加载失败");
  } finally {
    logsLoading.value = false;
  }
};

watch(logsFilterCategory, () => {
  logsPager.value.page = 1;
  loadLogs();
});

// —— 规则 CRUD ——
const resetForm = () => {
  editingRuleId.value = null;
  editingRule.value = null;
  rule.value = {
    name: "", metric_type: "launch_campaign", rule_category: "launch_day",
    threshold_value: 15, level1_threshold: 15, level2_threshold: 40,
    sensitive_words: "", negative_words: "", positive_words: "",
    anomaly_window_minutes: 30, zscore_threshold: 2.5, enabled: true,
  };
};

const editRule = (row) => {
  editingRuleId.value = row.id;
  editingRule.value = row;
  rule.value = {
    name: row.name, metric_type: row.metric_type,
    rule_category: row.rule_category || "general",
    threshold_value: row.threshold_value ?? 0,
    level1_threshold: row.level1_threshold ?? 0,
    level2_threshold: row.level2_threshold ?? 0,
    sensitive_words: row.sensitive_words || "",
    negative_words: row.negative_words || "",
    positive_words: row.positive_words || "",
    anomaly_window_minutes: row.anomaly_window_minutes ?? 60,
    zscore_threshold: row.zscore_threshold ?? 2.5,
    enabled: row.enabled ?? true,
  };
};

const submitRule = async () => {
  if (!rule.value.name) return ElMessage.warning("请填写规则名称");
  if (createLoading.value) return;
  createLoading.value = true;
  try {
    if (editingRuleId.value) {
      await http.put(`/alert/rules/${editingRuleId.value}`, rule.value);
      ElMessage.success("规则更新成功");
    } else {
      await http.post("/alert/rules", rule.value);
      ElMessage.success("规则创建成功");
    }
    resetForm();
    await loadRules();
  } catch (e) {
    ElMessage.error(e.response?.data?.message || "保存失败");
  } finally {
    createLoading.value = false;
  }
};

const toggleRule = async (row) => {
  try {
    await http.put(`/alert/rules/${row.id}`, { enabled: !row.enabled });
    ElMessage.success(row.enabled ? "已停用" : "已启用");
    await loadRules();
  } catch (e) {
    ElMessage.error(e.response?.data?.message || "操作失败");
  }
};

const deleteRule = async (row) => {
  await ElMessageBox.confirm(`确认删除规则「${row.name}」吗？`, "删除确认", {
    confirmButtonText: "确认删除", cancelButtonText: "取消", type: "warning",
  });
  await http.delete(`/alert/rules/${row.id}`);
  ElMessage.success("规则已删除");
  if (editingRuleId.value === row.id) resetForm();
  await loadRules();
};

// —— 扫描 ——
const syncDashboardWarningsCache = async () => {
  try {
    const { data } = await http.get("/dashboard/overview");
    localStorage.setItem(DASHBOARD_CACHE_KEY, JSON.stringify(data.data || {}));
  } catch {
    // 忽略
  }
};

const scan = async () => {
  if (scanLoading.value) return;
  scanLoading.value = true;
  try {
    const { data } = await http.post("/alert/scan");
    const triggered = data.data?.triggered ?? 0;
    ElMessage.success(`扫描完成，触发 ${triggered} 条`);
    await syncDashboardWarningsCache();
    await loadRules();
    logsPager.value.page = 1;
    await loadLogs();
  } catch (e) {
    ElMessage.error(e.response?.data?.message || "扫描失败");
  } finally {
    scanLoading.value = false;
  }
};

const refreshLogs = async () => loadLogs({ notify: true });

// —— 分页 ——
const onLogsPageChange = async (p) => { logsPager.value.page = p; await loadLogs(); };
const onLogsSizeChange = async (s) => { logsPager.value.size = s; logsPager.value.page = 1; await loadLogs(); };

// —— 一键写入默认规则 ——
const seedDefaults = async () => {
  if (seedLoading.value) return;
  await ElMessageBox.confirm(
    "是否写入 iPhone Duo 首发默认规则组？（幂等：已存在的同名规则会跳过）",
    "一键写入默认规则",
    { confirmButtonText: "写入", cancelButtonText: "取消", type: "info" }
  );
  seedLoading.value = true;
  try {
    const { data } = await http.post("/alert/seed-defaults");
    const added = data.data?.added ?? 0;
    ElMessage.success(`已写入 ${added} 条默认规则（已存在的跳过）`);
    await loadRules();
  } catch (e) {
    ElMessage.error(e.response?.data?.message || "写入失败");
  } finally {
    seedLoading.value = false;
  }
};

  // —— Matplotlib 图表预览 ——
const openChart = (row) => {
  if (!row.chart_path) return;
  chartDialogRuleName.value = row.message?.slice(0, 40) || `Log#${row.id}`;
  // chart_path 形如 data/alerts/rule1_heat_xxx.png
  chartDialogUrl.value = `${http.defaults.baseURL}/alert/chart/${row.chart_path}?t=${Date.now()}`;
  chartDialogVisible.value = true;
};

const onChartLoadError = () => {
  chartDialogUrl.value = "";
  ElMessage.warning("图表加载失败，可能已过期或 Matplotlib 未生成");
};

// —— 初始化 ——
onMounted(async () => {
  await Promise.all([loadRules(), loadLogs()]);
});
</script>

<style scoped>
.header-tags { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }

/* 首发专项卡片 */
.launch-campaign-card .campaign-actions {
  display: flex; gap: 8px; align-items: center;
}
.campaign-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
  gap: 14px;
  margin-top: 14px;
}
.campaign-tile {
  display: flex; gap: 14px; padding: 14px;
  border-radius: 14px;
  background: linear-gradient(135deg, rgba(121,192,255,0.08), rgba(33,208,178,0.06));
  border: 1px solid rgba(121,192,255,0.18);
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}
.campaign-tile:hover {
  transform: translateY(-2px);
  box-shadow: 0 10px 24px rgba(121,192,255,0.18);
}
.campaign-tile.pre_launch {
  background: linear-gradient(135deg, rgba(255,170,85,0.12), rgba(255,120,60,0.08));
  border-color: rgba(255,170,85,0.32);
}
.campaign-tile.launch_day {
  background: linear-gradient(135deg, rgba(255,107,107,0.14), rgba(255,70,120,0.08));
  border-color: rgba(255,107,107,0.38);
}
.campaign-tile.post_launch {
  background: linear-gradient(135deg, rgba(127,140,255,0.12), rgba(90,110,255,0.06));
  border-color: rgba(127,140,255,0.32);
}
.campaign-tile-icon { font-size: 28px; line-height: 1; width: 42px; text-align: center; }
.campaign-tile-title { font-weight: 600; font-size: 15px; }
.campaign-tile-desc { font-size: 12px; opacity: 0.7; margin: 4px 0 6px; }
.campaign-tile-count { font-size: 12px; opacity: 0.85; }
.campaign-tile-count strong { font-size: 15px; margin: 0 2px; }
.recent-chip {
  margin-left: 8px; padding: 1px 8px; border-radius: 10px;
  font-size: 11px; background: rgba(0,0,0,0.25);
}

/* 规则表单 */
.rule-form { padding: 4px 0; }
.form-toolbar { margin-top: 8px; }
.form-switch { margin-left: auto; }

/* 无图占位 */
.no-chart { opacity: 0.45; font-size: 12px; }

/* 图表弹窗 */
.chart-dialog-body { text-align: center; padding: 8px 4px; }
.chart-preview-img {
  max-width: 100%; max-height: 520px; border-radius: 8px;
  background: #0b1828; padding: 8px;
}
</style>
