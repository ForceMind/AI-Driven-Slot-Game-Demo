# Slot Master Pro

高性能、算法驱动的老虎机引擎，具备先进的概率控制能力。

## 功能特性

- **核心算法**：采用伪随机分布（PRD）算法，基于“C值”动态平衡连胜/连败。
- **奖池系统**：预先计算的结果奖池（超百万组合），实现即时开奖与精准RTP控制。
- **风险管理**：内置安全上限（如单次最大中奖不超过余额的20%）。
- **真实模拟**：支持高速批量模拟（1000+次），完全遵循所有游戏规则、安全上限和概率权重。
- **可配置下注档位**：可通过配置界面自定义有效下注金额（如10、20、50、100等）。
- **分层解锁**：玩家累计投注越多，可解锁更高波动性的奖池。
- **现代技术栈**：后端采用 Python FastAPI，前端采用 Vue 3 + Tailwind CSS。
- **移动端优化**：响应式UI布局，桌面与移动端均可流畅体验。

## 快速启动

### Windows
双击 `start_windows.bat` 即可同时启动后端和前端。

### Linux / Mac
运行启动脚本：
```bash
chmod +x start_linux_mac.sh
./start_linux_mac.sh
```

## 手动部署

### 后端
```bash
cd backend
# 可选：创建虚拟环境
# python -m venv venv
# source venv/bin/activate  # Linux/Mac
# .\venv\Scripts\activate   # Windows
pip install -r requirements.txt
uvicorn app:app --reload
```
服务地址：http://localhost:8000

### 前端
```bash
cd frontend
npm install
npm run dev
```
前端地址：http://localhost:5173

## 配置说明

游戏规则和数学模型可在 `backend/game_config_v2.json` 文件中调整，或通过游戏内“配置”按钮可视化修改。
- **目标RTP**：全局玩家回报率目标。
- **基础C值**：PRD公式中的C常数。
- **下注档位**：定义允许的下注金额。
- **奖池（Buckets）**：定义不同中奖区间的概率和派彩范围。
