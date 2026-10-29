<template>
  <section class="view-shell">
    <div class="section-title">
      <div>
        <p class="eyebrow">采集</p>
        <h3>采集规则与原始数据</h3>
        <p>选择来源后填写对应内容。</p>
      </div>
      <el-tag effect="dark" type="success">规则</el-tag>
    </div>

    <div class="panel-stack">
      <div class="metric-grid">
        <div class="metric-card"><span>规则</span><strong>{{ rulesTotal }}</strong></div>
        <div class="metric-card"><span>原始数据</span><strong>{{ rawTotal }}</strong></div>
        <div class="metric-card"><span>来源</span><strong>{{ sourceLabel }}</strong></div>
      </div>

      <div class="glass-panel">
        <div class="section-title">
          <div>
            <p class="mini-label">设置</p>
            <h3>新建规则</h3>
          </div>
        </div>

        <div class="toolbar">
          <el-select v-model="rule.source_type" placeholder="来源类型">
            <el-option label="新闻" value="news" />
            <el-option label="微博" value="weibo" />
          </el-select>
          <el-input v-model="rule.name" placeholder="规则名称" />
          <el-input
            v-model="rule.keywords"
            class="wide-input"
            :placeholder="keywordPlaceholder"
          />
          <el-input
            v-if="rule.source_type === 'weibo'"
            v-model="rule.topic_keywords"
            class="wide-input"
            placeholder="主题关键词，多个用逗号分隔，如：苹果,iPhone,折叠屏"
          />
          <el-input-number v-model="rule.max_count" :min="1" :max="500" />
          <el-date-picker
            v-model="timeRange"
            type="datetimerange"
            range-separator="至"
            start-placeholder="开始时间"
            end-placeholder="结束时间"
            value-format="YYYY-MM-DDTHH:mm:ss"
          />
          <el-button type="primary" @click="createRule">创建</el-button>
          <el-button type="success" @click="createAndRunRule">开始采集</el-button>
          <el-button @click="() => listRules(true)">刷新规则</el-button>
          <el-button @click="() => listRaw(true)">刷新数据</el-button>
        </div>

        <p class="panel-note">{{ formHint }}</p>
      </div>

      <div class="split-grid">
        <div class="glass-panel">
          <div class="section-title">
            <div>
              <p class="mini-label">规则</p>
              <h3>规则列表</h3>
            </div>
          </div>
          <div class="table-shell">
            <el-table :data="rules" stripe height="420" :row-class-name="getRowClassName">
              <el-table-column prop="id" label="ID" width="72" />
              <el-table-column prop="name" label="规则名称" min-width="140" />
              <el-table-column prop="source_type" label="来源" width="100" />
              <el-table-column prop="keywords" label="内容" min-width="220" />
              <el-table-column prop="topic_keywords" label="主题词" min-width="180" />
              <el-table-column prop="time_start" label="开始时间" min-width="160" />
              <el-table-column prop="time_end" label="结束时间" min-width="160" />
              <el-table-column label="状态" width="100">
                <template #default="scope">
                  <el-tag :type="scope.row.enabled ? 'success' : 'info'" size="small">
                    {{ scope.row.enabled ? '启用' : '禁用' }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column label="操作" width="250">
                <template #default="scope">
                  <el-button
                    size="small"
                    type="primary"
                    :loading="runningRuleId === scope.row.id"
                    :disabled="runningRuleId != null && runningRuleId !== scope.row.id || !scope.row.enabled"
                    @click="run(scope.row)"
                  >
                    执行
                  </el-button>
                  <el-button
                    size="small"
                    :type="scope.row.enabled ? 'warning' : 'success'"
                    @click="toggleRule(scope.row)"
                  >
                    {{ scope.row.enabled ? '禁用' : '启用' }}
                  </el-button>
                  <el-button
                    v-if="isAdmin"
                    size="small"
                    type="danger"
                    plain
                    @click="deleteRule(scope.row)"
                  >
                    删除
                  </el-button>
                </template>
              </el-table-column>
            </el-table>
          </div>
          <div class="pager-bar" v-if="rulesTotal">
            <el-pagination
              layout="prev, pager, next, sizes, total"
              :page-size="rulesPager.size"
              :page-sizes="[10, 20, 50, 100, 200]"
              :total="rulesTotal"
              :current-page="rulesPager.page"
              @size-change="onRulesSizeChange"
              @current-change="onRulesPageChange"
            />
          </div>
          <p v-if="!rules.length" class="empty-note">暂无规则。</p>
        </div>

        <div class="glass-panel">
          <div class="section-title">
            <div>
              <p class="mini-label">数据</p>
              <h3>原始数据</h3>
            </div>
          </div>
          <div class="table-shell">
            <el-table :data="raw" stripe height="420">
              <el-table-column prop="id" label="ID" width="72" />
              <el-table-column prop="title" label="标题" min-width="220" />
              <el-table-column prop="source_type" label="来源" width="100" />
              <el-table-column prop="published_at" label="发布时间" min-width="160" />
            </el-table>
          </div>
          <div class="pager-bar" v-if="rawTotal">
            <el-pagination
              layout="prev, pager, next, sizes, total"
              :page-size="rawPager.size"
              :page-sizes="[10, 20, 50, 100, 200]"
              :total="rawTotal"
              :current-page="rawPager.page"
              @size-change="onRawSizeChange"
              @current-change="onRawPageChange"
            />
          </div>
          <p v-if="!raw.length" class="empty-note">暂无数据。</p>
        </div>
      </div>
    </div>
    <BackToTop />
  </section>
</template>

<script setup>
import { computed, ref, onMounted } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import http from "../api/http";
import BackToTop from "../components/BackToTop.vue";

const rule = ref({ name: "", keywords: "", topic_keywords: "", source_type: "news", max_count: 30 });
const timeRange = ref([]);
const rules = ref([]);
const rulesTotal = ref(0);
const rulesPager = ref({ page: 1, size: 20 });
const raw = ref([]);
const rawTotal = ref(0);
const rawPager = ref({ page: 1, size: 20 });
const runningRuleId = ref(null);
const currentUserRole = ref(null);

const isAdmin = computed(() => currentUserRole.value === "admin");

const loadCurrentUser = async () => {
  try {
    const { data } = await http.get("/auth/me");
    currentUserRole.value = data.data?.role || null;
  } catch (error) {
    console.error('获取用户信息失败:', error);
    currentUserRole.value = null;
  }
};

const sourceLabel = computed(() => (rule.value.source_type === "weibo" ? "微博" : "新闻"));
const keywordPlaceholder = computed(() =>
  rule.value.source_type === "weibo"
    ? "微博用户ID，多个用逗号分隔"
    : "关键词，多个用逗号分隔"
);
const formHint = computed(() =>
  rule.value.source_type === "weibo"
    ? "微博来源填写用户ID；主题关键词用于采集后筛选，只保留标题或正文命中的微博。"
    : "新闻来源填写关键词。"
);

const validateRule = () => {
  if (!rule.value.name.trim()) {
    ElMessage.error("请填写规则名称");
    return false;
  }
  if (!rule.value.keywords.trim()) {
    ElMessage.error(rule.value.source_type === "weibo" ? "请填写微博用户ID" : "请填写关键词");
    return false;
  }
  if (rule.value.source_type === "weibo") {
    const invalid = rule.value.keywords
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean)
      .some((item) => !/^\d+$/.test(item));
    if (invalid) {
      ElMessage.error("微博用户ID只能填写数字");
      return false;
    }
    if (!rule.value.topic_keywords.trim()) {
      ElMessage.error("请填写主题关键词，用于筛掉不相关微博");
      return false;
    }
  }
  return true;
};

const listRules = async (showTip = false) => {
  try {
    const { data } = await http.get("/collect/rules", { params: rulesPager.value });
    rules.value = data.data?.items || [];
    rulesTotal.value = data.data?.total || 0;
    if (showTip) ElMessage.success("规则列表已刷新");
  } catch (error) {
    console.error('获取规则列表失败:', error);
    const msg = error.response?.data?.message || error.message || "获取规则失败";
    ElMessage.error(msg);
  }
};

const listRaw = async (showTip = false) => {
  try {
    const { data } = await http.get("/collect/raw", { params: rawPager.value });
    raw.value = data.data?.items || [];
    rawTotal.value = data.data?.total || 0;
    if (showTip) ElMessage.success("数据已刷新");
  } catch (error) {
    console.error('获取原始数据失败:', error);
    const msg = error.response?.data?.message || error.message || "获取数据失败";
    ElMessage.error(msg);
  }
};

const onRawPageChange = async (page) => {
  rawPager.value.page = page;
  await listRaw();
};

const onRawSizeChange = async (size) => {
  rawPager.value.size = size;
  rawPager.value.page = 1;
  await listRaw();
};

const onRulesPageChange = async (page) => {
  rulesPager.value.page = page;
  await listRules();
};

const onRulesSizeChange = async (size) => {
  rulesPager.value.size = size;
  rulesPager.value.page = 1;
  await listRules();
};

const resetForm = () => {
  rule.value = { name: "", keywords: "", topic_keywords: "", source_type: rule.value.source_type, max_count: 30 };
  timeRange.value = [];
};

const buildPayload = () => ({
  ...rule.value,
  time_start: timeRange.value?.[0] || null,
  time_end: timeRange.value?.[1] || null,
});

const createRule = async () => {
  if (!validateRule()) return null;
  try {
    const { data } = await http.post("/collect/rules", buildPayload());
    ElMessage.success("创建成功");
    await listRules();
    resetForm();
    return data.data?.id || null;
  } catch (e) {
    const msg = e.response?.data?.message || e.message || "创建失败";
    ElMessage.error(msg);
    return null;
  }
};

const createAndRunRule = async () => {
  const ruleId = await createRule();
  if (!ruleId) return;
  await run(ruleId);
};

const run = async (row) => {
  const id = row?.id;
  if (!id) return;
  if (runningRuleId.value) return;
  runningRuleId.value = id;
  try {
    ElMessage.info(row.source_type === "weibo" ? "正在执行微博采集，请稍候…" : "正在执行采集，请稍候…");
    const { data: res } = await http.post(`/collect/run/${id}`, {}, { timeout: 1200000 });
    const inserted = res?.data?.inserted ?? 0;
    const message = res?.data?.message || "";
    if (inserted > 0) {
      ElMessage.success(`采集完成，新增 ${inserted} 条数据`);
    } else if (message.includes("未找到")) {
      ElMessage.warning(message);
    } else {
      ElMessage.warning("采集完成，但未获取到新数据（可能已存在重复数据）");
    }
    rawPager.value.page = 1;
    await listRaw();
  } catch (e) {
    const msg = e.response?.data?.message || e.message || "采集失败";
    ElMessage.error(msg);
  } finally {
    runningRuleId.value = null;
  }
};

const toggleRule = async (row) => {
  const id = row?.id;
  if (!id) return;
  
  try {
    const { data } = await http.put(`/collect/rules/${id}/toggle`);
    
    const status = data.data?.enabled ? '启用' : '禁用';
    ElMessage.success(`规则已${status}`);
    
    await listRules();
  } catch (e) {
    const msg = e.response?.data?.message || e.message || "操作失败";
    ElMessage.error(msg);
  }
};

const deleteRule = async (row) => {
  const id = row?.id;
  if (!id) return;
  
  try {
    await ElMessageBox.confirm(
      '确定要删除该采集规则吗？删除后将无法恢复！\n\n建议：如果只是暂时不需要该规则，可以使用"禁用"功能。',
      '删除确认',
      {
        confirmButtonText: '确定删除',
        cancelButtonText: '取消',
        type: 'warning',
        distinguishCancelAndClose: true,
      }
    );
    
    await http.delete(`/collect/rules/${id}`);
    ElMessage.success('规则已删除');
    
    await listRules();
  } catch (e) {
    if (e !== 'cancel' && e !== 'close') {
      const msg = e.response?.data?.message || e.message || "删除失败";
      ElMessage.error(msg);
    }
  }
};

const getRowClassName = ({ row }) => {
  return row.enabled ? '' : 'disabled-rule-row';
};

const initialize = async () => {
  await loadCurrentUser();
  
  try {
    await listRules();
  } catch (error) {
    console.error('初始化规则列表失败:', error);
  }
  try {
    await listRaw();
  } catch (error) {
    console.error('初始化原始数据失败:', error);
  }
};

initialize();
</script>

<style scoped>
.disabled-rule-row {
  opacity: 0.6;
  background-color: #f5f5f5 !important;
}

.disabled-rule-row:hover > td {
  background-color: #f0f0f0 !important;
}
</style>