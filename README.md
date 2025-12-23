# AI-Driven Slot Game Demo / AI 驱动的老虎机游戏演示

[English Version Below](#how-to-run-ai-driven-slot-game-english)

## 🎮 如何运行 (中文说明)

本项目是一个由 LLM (大语言模型) 驱动后端逻辑的老虎机游戏演示。

### 1. 后端设置 (Python)

请确保已安装 Python 3.9+。

1. 进入 `backend` 目录：
   ```bash
   cd backend
   ```

2. 安装依赖：
   ```bash
   pip install -r requirements.txt
   ```

3. 启动 FastAPI 服务器：
   ```bash
   uvicorn app:app --reload --port 8000
   ```
   服务器将运行在 `http://localhost:8000`。

### 2. 前端设置 (Vue 3)

请确保已安装 Node.js (v18+)。

1. 进入 `frontend` 目录：
   ```bash
   cd frontend
   ```

2. 安装依赖：
   ```bash
   npm install
   ```

3. 启动开发服务器：
   ```bash
   npm run dev
   ```
   应用通常会运行在 `http://localhost:5173`。

### 3. 游戏配置

在浏览器中打开前端页面。点击 "Config" (配置) 按钮设置你的 AI 提供商。

#### 选项 A: OpenAI / DeepSeek (云端 API)
- **Provider:** 选择 "OpenAI Compatible" 或 "DeepSeek"
- **Base URL:** 输入 API 地址 (例如 `https://api.openai.com/v1` 或 `https://api.deepseek.com`)
- **API Key:** 输入你的 API 密钥
- **Model:** 输入模型名称 (例如 `gpt-4o`, `deepseek-chat`)

#### 选项 B: Ollama (本地运行)
- **Provider:** 选择 "Ollama"
- **Base URL:** `http://localhost:11434`
- **Model:** 输入已下载的模型名称 (例如 `llama3`, `mistral`)

## 4. 后端 API 文档

后端启动后，可以在浏览器访问交互式 API 文档 (Swagger UI)：
- 地址: `http://localhost:8000/docs`
- 你可以在此查看所有 API 接口的详细定义和测试请求。

## 🚀 一键启动脚本

为了方便运行，项目根目录提供了自动启动脚本：

### Windows 用户
双击运行根目录下的 `start_windows.bat`。它会自动：
1. 检查环境。
2. 打开两个命令行窗口分别启动后端和前端。

### Linux / Mac 用户
在终端运行：
```bash
chmod +x start_linux_mac.sh
./start_linux_mac.sh
```

## 5. 常见问题排查

- **LLM Error / Matrix Error:** 如果日志显示 `matrix` 错误，通常是因为模型没有返回正确的 JSON 格式。
  - 请尝试切换 "Provider" 为对应的厂商（例如 DeepSeek），这会自动设置正确的 Prompt 格式。
  - 检查 "Config" -> "Prompt Engineering" 中的提示词是否被意外修改。
- **CORS 错误:** 确保后端正在 8000 端口运行。
- **CSV 日志:** 游戏历史记录会自动保存到 `backend/game_data.csv` 文件中。

---

<a name="how-to-run-ai-driven-slot-game-english"></a>
# How to Run AI-Driven Slot Game (English)

## 1. Backend Setup (Python)

Ensure you have Python 3.9+ installed.

1. Navigate to the `backend` directory:
   ```bash
   cd backend
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the FastAPI server:
   ```bash
   uvicorn app:app --reload --port 8000
   ```
   Server will run at `http://localhost:8000`.

## 2. Frontend Setup (Vue 3)

Ensure you have Node.js (v18+) installed.

1. Navigate to the `frontend` directory:
   ```bash
   cd frontend
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

3. Run the development server:
   ```bash
   npm run dev
   ```
   App will typically run at `http://localhost:5173`.

## 3. Configuration

Open the Frontend in your browser. Click "Config" to set up your AI Provider.

### Option A: OpenAI / DeepSeek (Cloud)
- **Provider:** OpenAI Compatible
- **Base URL:** `https://api.openai.com/v1` (or your provider's URL, e.g. `https://api.deepseek.com`)
- **API Key:** Your API Key
- **Model:** `gpt-4o`, `deepseek-chat`, etc.

### Option B: Ollama (Local)
- **Provider:** Ollama
- **Base URL:** `http://localhost:11434`
- **Model:** `llama3`, `mistral`, etc. (Ensure you have pulled the model via `ollama pull modelname`)

## 4. Troubleshooting

- **CORS Error:** Ensure backend is running on port 8000. The frontend expects `http://localhost:8000/spin`.
- **LLM Error:** Check the "Debug Log" panel on the right side of the game. It shows the raw response or error from the backend.
- **CSV Logs:** Game history is saved to `backend/game_data.csv`.
