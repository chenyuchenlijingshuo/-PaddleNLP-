<template>
  <section class="view-shell">
    <div class="section-title">
      <div>
        <p class="eyebrow">处理</p>
        <h3>预处理与融合</h3>
        <p>执行处理并查看结果。</p>
      </div>
      <el-tag effect="dark" type="warning">融合</el-tag>
    </div>

    <div class="panel-stack">
      <div class="metric-grid">
        <div class="metric-card"><span>记录</span><strong>{{ fused.length }}</strong></div>
        <div class="metric-card"><span>操作</span><strong>预处理 + 融合</strong></div>
        <div class="metric-card"><span>内容</span><strong>融合结果</strong></div>
      </div>

      <div class="glass-panel">
        <div class="section-title"><div><p class="mini-label">操作</p><h3>处理流程</h3></div></div>
        <div class="toolbar">
          <el-button type="primary" :loading="preLoading" @click="pre">执行预处理</el-button>
          <el-button type="success" :loading="fusionLoading" @click="fusion">执行融合</el-button>
          <el-button :loading="loadLoading" @click="refreshData">刷新数据</el-button>
          <el-button 
            v-if="isAdmin" 
            type="warning" 
            :loading="exportLoading" 
            @click="exportData"
            class="export-btn"
          >
            <span class="btn-icon">📥</span>
            导出数据
          </el-button>
        </div>
        <p class="panel-note">预处理后再执行融合。</p>
      </div>

      <div class="glass-panel fusion-config-panel">
        <div class="section-title">
          <div>
            <p class="mini-label">配置</p>
            <h3>融合配置</h3>
          </div>
          <div class="config-header-actions">
            <el-tag v-if="!isAdmin" type="info" size="small" effect="plain">
              <span class="tag-icon">🔒</span> 仅管理员可修改
            </el-tag>
            <el-tag v-else type="success" size="small" effect="plain">
              <span class="tag-icon">✏️</span> 可修改
            </el-tag>
          </div>
        </div>
        
        <div class="fusion-config-grid">
          <div class="config-card">
            <div class="config-card-header">
              <div class="config-icon">⏱️</div>
              <div class="config-title">
                <h4>时间窗口</h4>
                <p>筛选最近N分钟的数据进行融合</p>
              </div>
            </div>
            <div class="config-card-body">
              <el-input-number 
                v-model="fusionConfig.time_window_minutes" 
                :min="5" 
                :max="480" 
                :disabled="!isAdmin"
                :step="5"
                size="large"
                class="config-input"
              />
              <span class="config-unit">分钟</span>
            </div>
          </div>

          <div class="config-card">
            <div class="config-card-header">
              <div class="config-icon">📰</div>
              <div class="config-title">
                <h4>新闻权重</h4>
                <p>新闻数据在融合分值中的权重系数</p>
              </div>
            </div>
            <div class="config-card-body">
              <el-input-number 
                v-model="fusionConfig.weight_news" 
                :min="0.1" 
                :max="3.0" 
                :step="0.1"
                :precision="1"
                :disabled="!isAdmin"
                size="large"
                class="config-input"
              />
              <span class="config-unit">倍</span>
            </div>
          </div>

          <div class="config-card">
            <div class="config-card-header">
              <div class="config-icon">💬</div>
              <div class="config-title">
                <h4>微博权重</h4>
                <p>微博数据在融合分值中的权重系数</p>
              </div>
            </div>
            <div class="config-card-body">
              <el-input-number 
                v-model="fusionConfig.weight_weibo" 
                :min="0.1" 
                :max="3.0" 
                :step="0.1"
                :precision="1"
                :disabled="!isAdmin"
                size="large"
                class="config-input"
              />
              <span class="config-unit">倍</span>
            </div>
          </div>
        </div>

        <div class="config-footer">
          <div class="formula-box">
            <div class="formula-label">📊 融合分值计算公式</div>
            <div class="formula-equation">
              <span class="formula-var">融合分值</span>
              <span class="formula-op">=</span>
              <span class="formula-var">新闻数量</span>
              <span class="formula-op">×</span>
              <span class="formula-val">{{ fusionConfig.weight_news }}</span>
              <span class="formula-op">+</span>
              <span class="formula-var">微博数量</span>
              <span class="formula-op">×</span>
              <span class="formula-val">{{ fusionConfig.weight_weibo }}</span>
            </div>
          </div>
          
          <div class="config-actions" v-if="isAdmin">
            <el-button 
              type="primary" 
              :loading="saveConfigLoading" 
              @click="saveConfig"
              size="large"
              class="save-btn"
            >
              <span class="btn-icon">💾</span>
              保存配置
            </el-button>
            <el-button 
              @click="resetConfig"
              size="large"
              class="reset-btn"
            >
              <span class="btn-icon">🔄</span>
              恢复默认
            </el-button>
          </div>
        </div>
      </div>

      <div class="glass-panel">
        <div class="section-title"><div><p class="mini-label">结果</p><h3>融合结果列表</h3></div></div>
        <div class="table-shell">
          <el-table :data="fused" stripe height="460">
            <el-table-column prop="id" label="ID" width="72" />
            <el-table-column prop="keyword" label="关键词" min-width="180" />
            <el-table-column prop="fused_score" label="融合分值" width="140" />
            <el-table-column prop="window_start" label="窗口开始" min-width="180" />
          </el-table>
        </div>
        <div class="pager-bar" v-if="fusedTotal">
          <el-pagination
            layout="prev, pager, next, sizes, total"
            :page-size="pager.size"
            :page-sizes="[10, 20, 50, 100, 200]"
            :total="fusedTotal"
            :current-page="pager.page"
            @size-change="onSizeChange"
            @current-change="onPageChange"
          />
        </div>
        <p v-if="!fused.length" class="empty-note">暂无结果。</p>
      </div>
    </div>
    <BackToTop />
  </section>
</template>

<script setup>
import { ref, computed, onMounted } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import http from "../api/http";
import BackToTop from "../components/BackToTop.vue";

const fused = ref([]);
const fusedTotal = ref(0);
const pager = ref({ page: 1, size: 20 });
const loadLoading = ref(false);
const preLoading = ref(false);
const fusionLoading = ref(false);
const exportLoading = ref(false);
const currentUserRole = ref(null);
const fusionConfig = ref({
  time_window_minutes: 60,
  weight_news: 1.0,
  weight_weibo: 0.8
});
const saveConfigLoading = ref(false);

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

const loadFusionConfig = async () => {
  try {
    const { data } = await http.get("/process/fusion/config");
    if (data.data) {
      fusionConfig.value = {
        time_window_minutes: data.data.time_window_minutes || 60,
        weight_news: data.data.weight_news || 1.0,
        weight_weibo: data.data.weight_weibo || 0.8
      };
    }
  } catch (error) {
    console.error('获取融合配置失败:', error);
  }
};

const saveConfig = async () => {
  if (saveConfigLoading.value) return;
  
  try {
    await ElMessageBox.confirm(
      '确定要保存融合配置吗？新的配置将立即生效。',
      '保存确认',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'info',
      }
    );
    
    saveConfigLoading.value = true;
    
    await http.put("/process/fusion/config", fusionConfig.value);
    ElMessage.success("融合配置已保存");
  } catch (e) {
    if (e !== 'cancel' && e !== 'close') {
      const msg = e.response?.data?.message || e.message || "保存失败";
      ElMessage.error(msg);
    }
  } finally {
    saveConfigLoading.value = false;
  }
};

const resetConfig = async () => {
  try {
    await ElMessageBox.confirm(
      '确定要恢复默认配置吗？\n\n默认配置：\n- 时间窗口：60分钟\n- 新闻权重：1.0\n- 微博权重：0.8',
      '恢复默认',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning',
      }
    );
    
    fusionConfig.value = {
      time_window_minutes: 60,
      weight_news: 1.0,
      weight_weibo: 0.8
    };
    
    if (isAdmin.value) {
      await http.put("/process/fusion/config", fusionConfig.value);
      ElMessage.success("已恢复默认配置");
    }
  } catch (e) {
    if (e !== 'cancel' && e !== 'close') {
      const msg = e.response?.data?.message || e.message || "恢复失败";
      ElMessage.error(msg);
    }
  }
};

const load = async ({ notify = false } = {}) => {
  if (loadLoading.value) return;
  loadLoading.value = true;
  try {
    const { data } = await http.get("/process/fused", { params: pager.value });
    fused.value = data.data?.items || [];
    fusedTotal.value = data.data?.total || 0;
    if (notify) {
      ElMessage.success("数据刷新成功");
    }
  } catch (e) {
    const msg = e.response?.data?.message || e.message || "刷新失败";
    ElMessage.error(msg);
  } finally {
    loadLoading.value = false;
  }
};
const pre = async () => {
  if (preLoading.value) return;
  preLoading.value = true;
  try {
    await http.post("/process/preprocess/run");
    ElMessage.success("预处理完成");
  } catch (e) {
    const msg = e.response?.data?.message || e.message || "预处理失败";
    ElMessage.error(msg);
  } finally {
    preLoading.value = false;
  }
};
const fusion = async () => {
  if (fusionLoading.value) return;
  fusionLoading.value = true;
  try {
    await http.post("/process/fusion/run");
    ElMessage.success("融合完成");
    pager.value.page = 1;
    await load();
  } catch (e) {
    const msg = e.response?.data?.message || e.message || "融合失败";
    ElMessage.error(msg);
  } finally {
    fusionLoading.value = false;
  }
};

const refreshData = async () => {
  await load({ notify: true });
};

const exportData = async () => {
  if (exportLoading.value) return;
  
  try {
    await ElMessageBox.confirm(
      '确定要导出融合数据吗？\n\n将导出所有融合结果数据为CSV文件。',
      '导出确认',
      {
        confirmButtonText: '确定导出',
        cancelButtonText: '取消',
        type: 'info',
      }
    );
    
    exportLoading.value = true;
    
    const response = await http.get('/process/fused/export.csv', {
      responseType: 'blob'
    });
    
    const blob = new Blob([response.data], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    const url = window.URL.createObjectURL(blob);
    
    const now = new Date();
    const timestamp = `${now.getFullYear()}${String(now.getMonth() + 1).padStart(2, '0')}${String(now.getDate()).padStart(2, '0')}_${String(now.getHours()).padStart(2, '0')}${String(now.getMinutes()).padStart(2, '0')}${String(now.getSeconds()).padStart(2, '0')}`;
    const filename = `fused_data_${timestamp}.csv`;
    
    link.setAttribute('href', url);
    link.setAttribute('download', filename);
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    
    ElMessage.success('数据导出成功');
  } catch (e) {
    if (e !== 'cancel' && e !== 'close') {
      const msg = e.response?.data?.message || e.message || "导出失败";
      ElMessage.error(msg);
    }
  } finally {
    exportLoading.value = false;
  }
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

const initialize = async () => {
  await loadCurrentUser();
  await loadFusionConfig();
  await load();
};

initialize();
</script>

<style scoped>
.fusion-config-panel {
  position: relative;
  overflow: visible;
}

.config-header-actions {
  display: flex;
  gap: 10px;
  align-items: center;
}

.tag-icon {
  margin-right: 4px;
}

.fusion-config-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 20px;
  margin: 20px 0;
}

.config-card {
  background: linear-gradient(135deg, 
    rgba(121, 192, 255, 0.05) 0%, 
    rgba(33, 208, 178, 0.03) 100%);
  border: 1px solid rgba(121, 192, 255, 0.15);
  border-radius: 16px;
  padding: 20px;
  transition: all 0.3s ease;
  position: relative;
  overflow: hidden;
}

.config-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 2px;
  background: linear-gradient(90deg, 
    rgba(121, 192, 255, 0.5) 0%, 
    rgba(33, 208, 178, 0.5) 100%);
  opacity: 0;
  transition: opacity 0.3s ease;
}

.config-card:hover {
  border-color: rgba(121, 192, 255, 0.3);
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(121, 192, 255, 0.15);
}

.config-card:hover::before {
  opacity: 1;
}

.config-card-header {
  display: flex;
  align-items: flex-start;
  gap: 15px;
  margin-bottom: 20px;
}

.config-icon {
  width: 48px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, 
    rgba(121, 192, 255, 0.15) 0%, 
    rgba(33, 208, 178, 0.15) 100%);
  border-radius: 12px;
  font-size: 24px;
  flex-shrink: 0;
}

.config-title h4 {
  margin: 0 0 6px 0;
  font-size: 16px;
  font-weight: 600;
  color: var(--text);
}

.config-title p {
  margin: 0;
  font-size: 13px;
  color: var(--text-soft);
  line-height: 1.5;
}

.config-card-body {
  display: flex;
  align-items: center;
  gap: 12px;
}

.config-input {
  flex: 1;
}

.config-unit {
  font-size: 14px;
  color: var(--text-soft);
  font-weight: 500;
  min-width: 35px;
}

.config-footer {
  margin-top: 25px;
  padding-top: 20px;
  border-top: 1px solid rgba(121, 192, 255, 0.12);
}

.formula-box {
  background: linear-gradient(135deg, 
    rgba(33, 208, 178, 0.08) 0%, 
    rgba(121, 192, 255, 0.08) 100%);
  border: 1px solid rgba(33, 208, 178, 0.2);
  border-radius: 12px;
  padding: 16px 20px;
  margin-bottom: 20px;
}

.formula-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--accent-strong);
  margin-bottom: 12px;
}

.formula-equation {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  font-family: 'Courier New', monospace;
}

.formula-var {
  color: var(--text);
  font-weight: 500;
  font-size: 14px;
}

.formula-op {
  color: var(--accent);
  font-weight: 600;
  font-size: 16px;
}

.formula-val {
  background: rgba(121, 192, 255, 0.15);
  color: var(--accent);
  padding: 2px 8px;
  border-radius: 6px;
  font-weight: 600;
  font-size: 14px;
}

.config-actions {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.save-btn,
.reset-btn {
  flex: 1;
  min-width: 140px;
  height: 44px;
  font-weight: 600;
  border-radius: 12px;
  transition: all 0.3s ease;
}

.save-btn {
  background: linear-gradient(135deg, #79c0ff 0%, #21d0b2 100%);
  border: none;
}

.save-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(121, 192, 255, 0.4);
}

.reset-btn {
  background: transparent;
  border: 1px solid rgba(121, 192, 255, 0.3);
  color: var(--text-soft);
}

.reset-btn:hover {
  border-color: rgba(121, 192, 255, 0.5);
  color: var(--text);
  background: rgba(121, 192, 255, 0.05);
}

.btn-icon {
  margin-right: 6px;
}

.export-btn {
  background: linear-gradient(135deg, #ff8b6a 0%, #ff6b6b 100%);
  border: none;
  color: white;
  font-weight: 600;
  transition: all 0.3s ease;
}

.export-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(255, 107, 107, 0.4);
}

:deep(.el-input-number) {
  width: 100%;
}

:deep(.el-input-number .el-input__wrapper) {
  background: rgba(10, 23, 40, 0.6);
  border: 1px solid rgba(121, 192, 255, 0.2);
  box-shadow: none;
  border-radius: 10px;
  padding: 8px 12px;
}

:deep(.el-input-number .el-input__wrapper:hover) {
  border-color: rgba(121, 192, 255, 0.4);
}

:deep(.el-input-number .el-input__wrapper.is-focus) {
  border-color: var(--accent);
  box-shadow: 0 0 0 2px rgba(121, 192, 255, 0.1);
}

:deep(.el-input-number .el-input__inner) {
  color: var(--text);
  font-weight: 500;
}

:deep(.el-input-number__decrease),
:deep(.el-input-number__increase) {
  background: transparent;
  border: none;
  color: var(--text-soft);
}

:deep(.el-input-number__decrease:hover),
:deep(.el-input-number__increase:hover) {
  color: var(--accent);
}

:deep(.el-input-number.is-disabled .el-input__wrapper) {
  background: rgba(10, 23, 40, 0.3);
  border-color: rgba(121, 192, 255, 0.1);
}

:deep(.el-input-number.is-disabled .el-input__inner) {
  color: var(--text-faint);
}

@media (max-width: 768px) {
  .fusion-config-grid {
    grid-template-columns: 1fr;
  }
  
  .config-actions {
    flex-direction: column;
  }
  
  .save-btn,
  .reset-btn {
    width: 100%;
  }
  
  .formula-equation {
    font-size: 12px;
  }
}
</style>
