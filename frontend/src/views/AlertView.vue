<template>
  <section class="view-shell">
    <div class="section-title">
      <div>
        <p class="eyebrow">预警</p>
        <h3>预警规则与日志</h3>
        <p>创建规则并查看记录。</p>
      </div>
      <el-tag effect="dark" type="danger">两级预警</el-tag>
    </div>

    <div class="panel-stack">
      <div class="metric-grid metric-grid-quad">
        <div class="metric-card"><span>日志</span><strong>{{ logs.length }}</strong></div>
        <div class="metric-card"><span>规则</span><strong>{{ rules.length }}</strong></div>
        <div class="metric-card"><span>类型</span><strong>{{ rule.metric_type === 'threshold' ? '阈值预警' : '敏感词预警' }}</strong></div>
        <div class="metric-card"><span>扫描</span><strong>可执行</strong></div>
      </div>

      <div class="glass-panel">
        <div class="section-title"><div><p class="mini-label">设置</p><h3>新建规则</h3></div></div>
        <div class="toolbar">
          <el-input v-model="rule.name" placeholder="规则名称" />
          <el-select v-model="rule.metric_type" placeholder="规则类型">
            <el-option label="阈值预警" value="threshold" />
            <el-option label="敏感词预警" value="sensitive" />
          </el-select>
          <el-input-number v-model="rule.level1_threshold" :min="0" placeholder="一级阈值" />
          <el-input-number v-model="rule.level2_threshold" :min="0" placeholder="二级阈值" />
          <el-input v-model="rule.sensitive_words" class="wide-input" placeholder="敏感词，逗号分隔" />
          <el-button type="primary" :loading="createLoading" @click="createRule">创建</el-button>
          <el-button type="danger" plain :loading="scanLoading" @click="scan">扫描</el-button>
          <el-button :loading="loadLoading" @click="refreshLogs">刷新日志</el-button>
        </div>
        <p class="panel-note">提示：一级阈值为轻度预警，二级阈值为重度预警。数值达到一级阈值触发一级预警，达到二级阈值触发二级预警。</p>
      </div>

      <div class="glass-panel">
        <div class="section-title"><div><p class="mini-label">规则</p><h3>已创建规则</h3></div></div>
        <div class="table-shell">
          <el-table :data="rules" stripe height="260">
            <el-table-column prop="id" label="ID" width="72" />
            <el-table-column prop="name" label="规则名称" min-width="140" />
            <el-table-column prop="metric_type" label="类型" width="100">
              <template #default="scope">
                {{ scope.row.metric_type === 'threshold' ? '阈值预警' : '敏感词预警' }}
              </template>
            </el-table-column>
            <el-table-column label="一级阈值" width="100">
              <template #default="scope">
                {{ scope.row.level1_threshold || '-' }}
              </template>
            </el-table-column>
            <el-table-column label="二级阈值" width="100">
              <template #default="scope">
                {{ scope.row.level2_threshold || '-' }}
              </template>
            </el-table-column>
            <el-table-column prop="enabled" label="状态" width="90">
              <template #default="{ row }">
                <el-tag size="small" :type="row.enabled ? 'success' : 'info'">
                  {{ row.enabled ? "启用" : "停用" }}
                </el-tag>
              </template>
            </el-table-column>
          </el-table>
        </div>
        <p v-if="!rules.length" class="empty-note">暂无规则，请先创建。</p>
      </div>

      <div class="glass-panel">
        <div class="section-title"><div><p class="mini-label">日志</p><h3>预警记录</h3></div></div>
        <div class="table-shell">
          <el-table :data="logs" stripe height="460">
            <el-table-column prop="id" label="ID" width="72" />
            <el-table-column label="级别" width="100">
              <template #default="scope">
                <el-tag :type="scope.row.level === 2 ? 'danger' : 'warning'" size="small">
                  {{ scope.row.level === 2 ? '二级预警' : '一级预警' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="message" label="消息" min-width="260" />
            <el-table-column prop="triggered_at" label="触发时间" min-width="180" />
          </el-table>
        </div>
        <div class="pager-bar" v-if="logsTotal">
          <el-pagination
            layout="prev, pager, next, sizes, total"
            :page-size="pager.size"
            :page-sizes="[10, 20, 50, 100, 200]"
            :total="logsTotal"
            :current-page="pager.page"
            @size-change="onSizeChange"
            @current-change="onPageChange"
          />
        </div>
        <p v-if="!logs.length" class="empty-note">暂无记录。</p>
      </div>
    </div>
    <BackToTop />
  </section>
</template>

<script setup>
import { ref } from "vue";
import { ElMessage } from "element-plus";
import http from "../api/http";
import BackToTop from "../components/BackToTop.vue";

const rule = ref({ 
  name: "", 
  metric_type: "threshold", 
  level1_threshold: 10, 
  level2_threshold: 50, 
  sensitive_words: "暴力,谣言" 
});
const rules = ref([]);
const logs = ref([]);
const logsTotal = ref(0);
const pager = ref({ page: 1, size: 20 });
const createLoading = ref(false);
const scanLoading = ref(false);
const loadLoading = ref(false);
const rulesLoading = ref(false);
const DASHBOARD_CACHE_KEY = "dashboard_overview_cache_v1";

const syncDashboardWarningsCache = async () => {
  try {
    const { data } = await http.get("/dashboard/overview");
    const overview = data.data || {};
    localStorage.setItem(DASHBOARD_CACHE_KEY, JSON.stringify(overview));
  } catch {
    // keep alert workflow stable even if dashboard sync fails
  }
};

const loadRules = async () => {
  if (rulesLoading.value) return;
  rulesLoading.value = true;
  try {
    const { data } = await http.get("/alert/rules");
    rules.value = data.data || [];
  } catch (e) {
    const msg = e.response?.data?.message || e.message || "规则加载失败";
    ElMessage.error(msg);
  } finally {
    rulesLoading.value = false;
  }
};

const createRule = async () => {
  if (createLoading.value) return;
  createLoading.value = true;
  try {
    await http.post("/alert/rules", rule.value);
    ElMessage.success("创建成功");
    await loadRules();
  } catch (e) {
    const msg = e.response?.data?.message || e.message || "创建失败";
    ElMessage.error(msg);
  } finally {
    createLoading.value = false;
  }
};
const scan = async () => {
  if (scanLoading.value) return;
  scanLoading.value = true;
  try {
    await http.post("/alert/scan");
    pager.value.page = 1;
    await load();
    await syncDashboardWarningsCache();
    ElMessage.success("扫描完成");
  } catch (e) {
    const msg = e.response?.data?.message || e.message || "扫描失败";
    ElMessage.error(msg);
  } finally {
    scanLoading.value = false;
  }
};
const load = async ({ notify = false } = {}) => {
  if (loadLoading.value) return;
  loadLoading.value = true;
  try {
    const { data } = await http.get("/alert/logs", { params: pager.value });
    logs.value = data.data?.items || [];
    logsTotal.value = data.data?.total || 0;
    if (notify) {
      ElMessage.success("日志已刷新");
    }
  } catch (e) {
    const msg = e.response?.data?.message || e.message || "日志加载失败";
    ElMessage.error(msg);
  } finally {
    loadLoading.value = false;
  }
};

const refreshLogs = async () => {
  await load({ notify: true });
};

const onPageChange = async (page) => {
  pager.value.page = page;
  await load();
};

const onSizeChange = async (size) => {
  pager.value.size = size;
  pager.value.page = 1;
  await load();
};
loadRules();
load();
</script>
