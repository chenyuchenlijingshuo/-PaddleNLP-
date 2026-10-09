<template>
  <section class="view-shell">
    <div class="section-title">
      <div>
        <p class="eyebrow">用户</p>
        <h3>用户与角色管理</h3>
        <p>查看系统用户。</p>
      </div>
      <el-tag effect="dark" type="info">管理员</el-tag>
    </div>

    <div class="panel-stack">
      <div class="metric-grid metric-grid-quad">
        <div class="metric-card"><span>账户</span><strong>{{ total }}</strong></div>
        <div class="metric-card"><span>管理员</span><strong>{{ adminCount }}</strong></div>
        <div class="metric-card"><span>普通用户</span><strong>{{ userCount }}</strong></div>
        <div class="metric-card"><span>查看者</span><strong>{{ viewerCount }}</strong></div>
      </div>

      <div class="glass-panel">
        <div class="section-title">
          <div><p class="mini-label">列表</p><h3>系统用户</h3></div>
          <div class="toolbar">
            <el-button v-if="isAdmin" type="success" @click="openCreateDialog">新增用户</el-button>
            <el-button type="primary" :loading="loading" @click="refreshUsers">刷新</el-button>
          </div>
        </div>

        <div class="table-shell">
          <el-table :data="rows" stripe height="460">
            <el-table-column prop="id" label="ID" width="72" />
            <el-table-column prop="username" label="用户名" min-width="180" />
            <el-table-column prop="display_name" label="显示名" min-width="180" />
            <el-table-column prop="role" label="角色" width="120" />
            <el-table-column label="操作" min-width="220">
              <template #default="{ row }">
                <el-button 
                  size="small" 
                  @click="openEditDialog(row)"
                  v-if="isAdmin || isCurrentUser(row)"
                >
                  编辑
                </el-button>
                <el-button
                  v-if="isAdmin"
                  size="small"
                  type="danger"
                  plain
                  :disabled="isCurrentUser(row)"
                  @click="removeUser(row)"
                >
                  删除
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
        <div class="pager-bar" v-if="total">
          <el-pagination
            layout="prev, pager, next, sizes, total"
            :page-size="pager.size"
            :page-sizes="[10, 20, 50, 100, 200]"
            :total="total"
            :current-page="pager.page"
            @size-change="onSizeChange"
            @current-change="onPageChange"
          />
        </div>
        <p v-if="!rows.length" class="empty-note">暂无用户。</p>
      </div>
    </div>

    <el-dialog
      v-model="dialogVisible"
      class="user-manage-dialog"
      :title="dialogMode === 'create' ? '新增用户' : '编辑用户'"
      width="520px"
    >
      <el-form :model="dialogForm" label-position="top" class="user-form">
        <el-form-item label="用户名" required>
          <el-input 
            v-model="dialogForm.username" 
            :disabled="dialogMode === 'edit'" 
            placeholder="请输入用户名（必填）"
            clearable
          />
        </el-form-item>
        <el-form-item label="显示名">
          <el-input 
            v-model="dialogForm.display_name" 
            placeholder="请输入显示名（可选）"
            clearable
          />
        </el-form-item>
        <el-form-item label="角色" required v-if="isAdmin">
          <el-select v-model="dialogForm.role" placeholder="请选择角色" style="width: 100%">
            <el-option label="管理员" value="admin">
              <div class="role-option">
                <span class="role-label">管理员</span>
                <span class="role-desc">拥有所有权限</span>
              </div>
            </el-option>
            <el-option label="普通用户" value="user">
              <div class="role-option">
                <span class="role-label">普通用户</span>
                <span class="role-desc">可采集、处理、分析</span>
              </div>
            </el-option>
            <el-option label="查看者" value="viewer">
              <div class="role-option">
                <span class="role-label">查看者</span>
                <span class="role-desc">仅查看数据</span>
              </div>
            </el-option>
          </el-select>
        </el-form-item>
        <el-form-item :label="dialogMode === 'create' ? '密码' : '重置密码（留空则不修改）'" :required="dialogMode === 'create'">
          <el-input 
            v-model="dialogForm.password" 
            type="password" 
            show-password 
            :placeholder="dialogMode === 'create' ? '至少 6 位，包含字母和数字' : '留空则不修改密码'"
            clearable
          />
          <div class="form-hint" v-if="dialogMode === 'create'">
            密码至少 6 位，必须包含字母和数字
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <div class="dialog-footer">
          <el-button @click="dialogVisible = false">取消</el-button>
          <el-button type="primary" :loading="submitLoading" @click="submitDialog">
            {{ dialogMode === "create" ? "创建" : "保存" }}
          </el-button>
        </div>
      </template>
    </el-dialog>
    <BackToTop />
  </section>
</template>

<script setup>
import { computed, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import http from "../api/http";
import BackToTop from "../components/BackToTop.vue";

const rows = ref([]);
const total = ref(0);
const pager = ref({ page: 1, size: 20 });
const loading = ref(false);
const currentUserId = ref(null);
const dialogVisible = ref(false);
const dialogMode = ref("create");
const submitLoading = ref(false);
const editingId = ref(null);
const dialogForm = ref({ username: "", display_name: "", role: "user", password: "" });
const normalizeRole = (role) => String(role || "").trim().toLowerCase();
const adminCount = computed(() => rows.value.filter((item) => normalizeRole(item.role) === "admin").length);
const userCount = computed(() => rows.value.filter((item) => normalizeRole(item.role) === "user").length);
const viewerCount = computed(() => rows.value.filter((item) => normalizeRole(item.role) === "viewer").length);

const currentUserRole = ref(null);

const loadMe = async () => {
  try {
    const { data } = await http.get("/auth/me");
    currentUserId.value = data.data?.id || null;
    currentUserRole.value = data.data?.role || null;
  } catch {
    currentUserId.value = null;
    currentUserRole.value = null;
  }
};

const isAdmin = computed(() => currentUserRole.value === "admin");
const isViewer = computed(() => currentUserRole.value === "viewer");
const isUser = computed(() => currentUserRole.value === "user");

const load = async ({ notify = false } = {}) => {
  if (loading.value) return;
  loading.value = true;
  try {
    const { data } = await http.get("/users", { params: pager.value });
    rows.value = data.data?.items || [];
    total.value = data.data?.total || 0;
    if (notify) {
      ElMessage.success("用户列表已刷新");
    }
  } catch (e) {
    const msg = e.response?.data?.message || e.message || "加载用户失败";
    ElMessage.error(msg);
  } finally {
    loading.value = false;
  }
};

const refreshUsers = async () => {
  await load({ notify: true });
};

const isCurrentUser = (row) => Number(row?.id) === Number(currentUserId.value);

const openCreateDialog = () => {
  dialogMode.value = "create";
  editingId.value = null;
  dialogForm.value = { username: "", display_name: "", role: "user", password: "" };
  dialogVisible.value = true;
};

const openEditDialog = (row) => {
  dialogMode.value = "edit";
  editingId.value = row.id;
  dialogForm.value = {
    username: row.username || "",
    display_name: row.display_name || "",
    role: normalizeRole(row.role) || "user",
    password: "",
  };
  dialogVisible.value = true;
};

const submitDialog = async () => {
  if (submitLoading.value) return;
  if (!dialogForm.value.username && dialogMode.value === "create") {
    ElMessage.warning("请输入用户名");
    return;
  }
  if (!["admin", "user", "viewer"].includes(normalizeRole(dialogForm.value.role))) {
    ElMessage.warning("请选择合法角色");
    return;
  }
  
  const validatePassword = (password) => {
    if (!password || password.length < 6) {
      return { valid: false, message: "密码长度至少 6 位" };
    }
    const hasLetter = /[a-zA-Z]/.test(password);
    const hasNumber = /[0-9]/.test(password);
    if (!hasLetter || !hasNumber) {
      return { valid: false, message: "密码必须包含字母和数字" };
    }
    return { valid: true };
  };
  
  if (dialogMode.value === "create") {
    const result = validatePassword(dialogForm.value.password);
    if (!result.valid) {
      ElMessage.warning(result.message);
      return;
    }
  }
  
  if (dialogMode.value === "edit" && dialogForm.value.password) {
    const result = validatePassword(dialogForm.value.password);
    if (!result.valid) {
      ElMessage.warning(result.message);
      return;
    }
  }
  
  submitLoading.value = true;
  try {
    if (dialogMode.value === "create") {
      await http.post("/users", {
        username: dialogForm.value.username,
        password: dialogForm.value.password,
        role: dialogForm.value.role,
        display_name: dialogForm.value.display_name,
      });
      ElMessage.success("用户创建成功");
      pager.value.page = 1;
    } else {
      const payload = {
        role: dialogForm.value.role,
        display_name: dialogForm.value.display_name,
      };
      if (dialogForm.value.password) {
        payload.password = dialogForm.value.password;
      }
      await http.put(`/users/${editingId.value}`, payload);
      ElMessage.success("用户更新成功");
    }
    dialogVisible.value = false;
    await load();
  } catch (e) {
    const msg = e.response?.data?.message || e.message || "提交失败";
    ElMessage.error(msg);
  } finally {
    submitLoading.value = false;
  }
};

const removeUser = async (row) => {
  try {
    await ElMessageBox.confirm(`确认删除用户 ${row.username} 吗？`, "删除确认", {
      confirmButtonText: "确认删除",
      cancelButtonText: "取消",
      type: "warning",
      customClass: "user-delete-box",
    });
    await http.delete(`/users/${row.id}`);
    ElMessage.success("用户删除成功");
    if (rows.value.length === 1 && pager.value.page > 1) {
      pager.value.page -= 1;
    }
    await load();
  } catch (e) {
    if (e === "cancel" || e === "close") return;
    const msg = e.response?.data?.message || e.message || "删除失败";
    ElMessage.error(msg);
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
loadMe();
load();
</script>
