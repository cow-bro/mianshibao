# API 文档

本文件用于沉淀面试宝各模块 API 设计。

## 当前已实现

- `GET /api/v1/health`
- `POST /api/v1/auth/login`
- `POST /api/v1/auth/refresh`

## 认证接口

### `POST /api/v1/auth/login`

请求体:

```json
{
	"username": "demo",
	"password": "password"
}
```

响应数据:

```json
{
	"access_token": "...",
	"refresh_token": "..."
}
```

### `POST /api/v1/auth/refresh`

请求体:

```json
{
	"refresh_token": "..."
}
```
