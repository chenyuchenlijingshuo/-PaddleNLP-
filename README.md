# 基于 PaddleNLP 框架的舆情分析系统（Flask + Vue + MySQL）

## 1. 项目结构

- `backend/` 后端 API 与任务调度
- `frontend/` Vue3 可视化页面
- `database/schema.sql` 数据库初始化脚本
- `docs/api.md` 接口清单

## 2. 后端启动

```bash
cd backend
pip install -r requirements.txt
copy .env.example .env
python app.py
```

默认地址：`http://127.0.0.1:5000/api/health`

**首次登录**：数据库中没有任何用户时，启动后端会自动创建管理员账号（可在 `backend/.env` 中配置）：

- 默认用户名：`admin`
- 默认密码：`admin123456`

若你曾用错误密码多次尝试，请确认使用上述密码；也可在前端点击「注册」创建普通用户后再登录。

## 3. 前端启动

```bash
cd frontend
npm install
npm run dev
```

默认地址：`http://127.0.0.1:5173`

## 4. 角色权限

- `admin`：系统配置、规则管理、全量数据管理
- `user`：分析查看、采集执行、权限内数据操作
- `viewer`：只读查看分析结果

## 5. 流程说明

1. 配置采集规则并执行采集
2. 对原始数据做清洗、分词与去重
3. 按关键词与时间窗执行加权融合
4. 进行 TF-IDF、热点排行、趋势分析
5. 按阈值与敏感词规则生成两级预警
