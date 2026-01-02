
# AI 驱动拉霸游戏（Node.js 版本）

本项目是原 Python/FastAPI 拉霸游戏的 Node.js/Express 后端重写版本。

## 运行环境要求

- Node.js（建议 v16 及以上）
- npm（通常随 Node.js 一起安装）

## 项目结构

- `backend/`：Node.js Express 服务端及核心游戏逻辑
- `frontend/`：Vue 3 + Vite 前端应用

## 安装与启动

### 1. 启动后端

打开终端，进入 `backend` 目录：

```bash
cd backend
npm install
node src/app.js
```

服务端将启动于 **http://localhost:3000**

### 2. 启动前端

另开一个终端，进入 `frontend` 目录：

```bash
cd frontend
npm install
npm run dev
```

前端将启动于 **http://localhost:5173**（或类似端口）

## 功能亮点

- **双轴模拟图表**：可视化余额（左轴）与 RTP（右轴）变化
- **PRD 算法**：伪随机分布，兼顾公平与可控性
- **可配置**：支持 UI 调整 RTP、波动率（C 值）、最大中奖倍数等参数
- **移动端优化**：触控友好，响应式布局
