<template>
  <section class="view-shell auth-page">
    <div class="auth-background">
      <div class="auth-bg-gradient"></div>
      <div class="auth-orb auth-orb-1"></div>
      <div class="auth-orb auth-orb-2"></div>
      <div class="auth-orb auth-orb-3"></div>
      <div class="auth-particles">
        <div class="particle" v-for="i in 20" :key="i"></div>
      </div>
    </div>
    
    <div class="section-title">
      <div>
        <p class="eyebrow">账号中心</p>
        <h3>{{ isRegister ? "创建账号并接入系统" : "登录与注册" }}</h3>
        <p>完成登录后即可进入舆情采集、处理、分析与预警模块。</p>
      </div>
      <el-tag :type="me ? 'success' : 'info'" effect="dark">
        {{ me ? `已登录：${me.username}` : "账号入口" }}
      </el-tag>
    </div>

    <div class="auth-grid">
      <div class="glass-panel auth-hero">
        <div class="auth-title">
          <p class="eyebrow">信息</p>
          <h3>统一身份入口</h3>
          <p class="auth-copy">
            支持管理员、普通用户和只读用户进入系统。管理员可配置规则、执行融合与预警，普通用户可进行数据采集与分析查看。
          </p>
        </div>

        <div class="auth-status-card">
          <div class="status-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="10"/>
              <path d="M12 6v6l4 2"/>
            </svg>
          </div>
          <div class="status-info">
            <span class="status-label">当前状态</span>
            <strong class="status-value">{{ me ? `${me.username} (${me.role})` : "未登录" }}</strong>
          </div>
        </div>

        <div class="auth-feature-list">
          <div class="auth-feature">
            <div class="feature-icon">📊</div>
            <div class="feature-content">
              <strong>采集监测</strong>
              <p>按规则抓取新闻与微博数据，并记录执行日志。</p>
            </div>
          </div>
          <div class="auth-feature">
            <div class="feature-icon">📈</div>
            <div class="feature-content">
              <strong>分析可视化</strong>
              <p>支持热点排行、趋势图、来源分布与 PaddleNLP 文本分析。</p>
            </div>
          </div>
          <div class="auth-feature">
            <div class="feature-icon">🔔</div>
            <div class="feature-content">
              <strong>预警联动</strong>
              <p>根据阈值与敏感词规则生成日志并在首页展示提醒。</p>
            </div>
          </div>
        </div>
      </div>

      <div class="auth-form-card glass-panel">
        <div class="auth-switch">
          <button type="button" class="auth-switch-btn" :class="{ active: !isRegister }" @click="setMode(false)">
            登录
          </button>
          <button type="button" class="auth-switch-btn" :class="{ active: isRegister }" @click="setMode(true)">
            注册
          </button>
        </div>

        <div class="auth-form-head">
          <p class="mini-label">表单</p>
          <h3>{{ isRegister ? "创建新用户" : "欢迎回来" }}</h3>
          <p class="auth-hint">
            {{ isRegister ? "请选择角色并填写注册信息。" : "请输入用户名与密码进入系统。" }}
          </p>
        </div>

        <el-form :model="form" label-position="top">
          <div class="form-grid">
            <el-form-item class="full-span" label="用户名">
              <el-input v-model="form.username" placeholder="请输入用户名" />
            </el-form-item>
            <el-form-item v-if="isRegister" class="full-span" label="显示名称">
              <el-input v-model="form.display_name" placeholder="用于页面展示，可留空自动使用用户名" />
            </el-form-item>
            <el-form-item v-if="isRegister" class="full-span" label="角色" required>
              <el-select v-model="form.role" placeholder="请选择角色" style="width: 100%">
                <el-option label="普通用户" value="user">
                  <div class="role-option">
                    <span class="role-label">普通用户</span>
                    <span class="role-desc">可采集、处理、分析数据</span>
                  </div>
                </el-option>
                <el-option label="查看者" value="viewer">
                  <div class="role-option">
                    <span class="role-label">查看者</span>
                    <span class="role-desc">仅查看数据，无操作权限</span>
                  </div>
                </el-option>
              </el-select>
            </el-form-item>
            <el-form-item class="full-span" label="密码">
              <el-input 
                v-model="form.password" 
                type="password" 
                show-password 
                :placeholder="isRegister ? '至少 6 位，必须包含字母和数字' : '请输入密码'" 
              />
            </el-form-item>
            <el-form-item v-if="isRegister" class="full-span" label="确认密码">
              <el-input v-model="confirmPassword" type="password" show-password placeholder="请再次输入密码" />
            </el-form-item>
          </div>

          <div class="auth-actions">
            <el-button type="primary" @click="submitAuth">
              {{ isRegister ? "立即注册" : "立即登录" }}
            </el-button>
          </div>
        </el-form>

        <div class="auth-status">
          <span class="auth-status-dot" :class="{ online: !!me }"></span>
          <span>{{ me ? `当前已登录为 ${me.username}（${me.role}）` : "当前未登录，请输入账号密码进入系统。" }}</span>
        </div>
        <p class="auth-hint">注册时可选择普通用户或查看者角色，管理员账号由系统预设。</p>
      </div>
    </div>
  </section>
</template>

<script setup>
import { onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import http from "../api/http";

const form = ref({ username: "admin", password: "admin123456", display_name: "", role: "user" });
const isRegister = ref(false);
const confirmPassword = ref("");
const me = ref(null);

const notifyAuthChanged = () => {
  window.dispatchEvent(new Event("auth-changed"));
};

const fetchMe = async () => {
  const token = localStorage.getItem("token");
  if (!token) {
    me.value = null;
    return;
  }
  try {
    const { data } = await http.get("/auth/me");
    me.value = data.data || null;
  } catch {
    localStorage.removeItem("token");
    me.value = null;
    notifyAuthChanged();
  }
};

const login = async () => {
  try {
    const { data } = await http.post("/auth/login", form.value);
    if (data.code !== 0 || !data.data?.access_token) {
      ElMessage.error(data.message || "登录失败");
      return;
    }
    localStorage.setItem("token", data.data.access_token);
    me.value = data.data.user;
    notifyAuthChanged();
    ElMessage.success("登录成功");
  } catch (e) {
    const msg = e.response?.data?.message || e.message || "登录失败";
    ElMessage.error(msg);
  }
};

const register = async () => {
  if (form.value.password.length < 6) {
    ElMessage.warning("密码长度至少为 6 位");
    return;
  }
  const hasLetter = /[a-zA-Z]/.test(form.value.password);
  const hasNumber = /[0-9]/.test(form.value.password);
  if (!hasLetter || !hasNumber) {
    ElMessage.warning("密码必须包含字母和数字");
    return;
  }
  if (form.value.password !== confirmPassword.value) {
    ElMessage.warning("两次输入的密码不一致");
    return;
  }
  if (!form.value.role) {
    ElMessage.warning("请选择角色");
    return;
  }
  try {
    const { data } = await http.post("/auth/register", form.value);
    if (data.code !== 0) {
      ElMessage.error(data.message || "注册失败");
      return;
    }
    ElMessage.success("注册成功");
    isRegister.value = false;
    confirmPassword.value = "";
  } catch (e) {
    const msg = e.response?.data?.message || e.message || "注册失败";
    ElMessage.error(msg);
  }
};

const setMode = (registerMode) => {
  isRegister.value = registerMode;
  confirmPassword.value = "";
  if (registerMode) {
    form.value = { username: "", password: "", display_name: "", role: "user" };
  } else {
    form.value = { username: "admin", password: "admin123456", display_name: "", role: "user" };
  }
};

const submitAuth = async () => {
  if (!form.value.username || !form.value.password) {
    ElMessage.warning("请输入用户名和密码");
    return;
  }
  if (isRegister.value) {
    await register();
    return;
  }
  await login();
};

onMounted(fetchMe);
</script>
