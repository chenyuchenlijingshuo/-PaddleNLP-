# API 概览

- 认证：`/api/auth/register`、`/api/auth/login`、`/api/auth/me`
- 用户：`/api/users`、`/api/users/me`、`/api/users/{id}/role`
- 采集：`/api/collect/rules`、`/api/collect/run/{rule_id}`、`/api/collect/raw`
- 处理：`/api/process/preprocess/run`、`/api/process/fusion/run`、`/api/process/fused`
- 分析：`/api/analyze/tfidf`、`/api/analyze/hot`、`/api/analyze/trend`
- 预警：`/api/alert/rules`、`/api/alert/scan`、`/api/alert/logs`

统一返回：

```json
{
  "code": 0,
  "message": "ok",
  "data": {}
}
```
