#!/bin/bash

# AI 驱动老虎机演示 - Ubuntu 部署脚本
# 本脚本会设置运行环境、安装依赖、构建前端，并为生产环境配置 Nginx 与 Systemd。

set -e

# 配置项
APP_DIR=$(pwd)
BACKEND_DIR="$APP_DIR/backend"
FRONTEND_DIR="$APP_DIR/frontend"
USER_NAME=$(whoami)
SERVICE_NAME="slot-game-backend"
DOMAIN_NAME="localhost" # 如需替换为您的域名或 IP，请修改此项

echo ">>> 开始部署 Slot Master Pro..."
echo ">>> 项目目录: $APP_DIR"

# 1. 系统更新与依赖安装
echo ">>> 更新系统并安装依赖..."
sudo apt-get update
# 注意：如果使用 NodeSource 源，nodejs 包已包含 npm。如果使用 Ubuntu 默认源，可能需要单独安装 npm。
# 为了避免 "Conflicts: npm" 错误，这里先尝试不显式安装 npm。
sudo apt-get install -y python3 python3-pip python3-venv nodejs nginx git

# 检查 npm 是否安装成功，如果没有则尝试单独安装
if ! command -v npm &> /dev/null; then
    echo ">>> 未检测到 npm，尝试单独安装..."
    sudo apt-get install -y npm
fi

# 尝试拉取最新代码
if [ -d ".git" ]; then
    echo ">>> 检测到 Git 仓库，尝试拉取最新代码..."
    git pull || echo ">>> 警告: git pull 失败，继续使用当前代码部署..."
else
    echo ">>> 未检测到 Git 仓库，跳过代码更新..."
fi

# 2. 后端准备
echo ">>> 设置后端环境..."
cd $BACKEND_DIR

# 创建虚拟环境
# 检查是否存在不兼容的 venv (例如从 Windows 复制过来的)
if [ -d "venv" ] && [ ! -f "venv/bin/activate" ]; then
    echo ">>> 检测到损坏或不兼容的虚拟环境 (可能是 Windows 残留)，正在重建..."
    rm -rf venv
fi

if [ ! -d "venv" ]; then
    echo ">>> 创建 Python 虚拟环境..."
    python3 -m venv venv || { echo ">>> [错误] 创建虚拟环境失败，请尝试运行: sudo apt-get install python3-venv"; exit 1; }
fi

# 安装 Python 依赖
echo ">>> 安装 Python 依赖..."
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
else
    echo ">>> [错误] 无法找到 venv/bin/activate，虚拟环境创建可能失败。"
    exit 1
fi

pip install --upgrade pip
pip install -r requirements.txt
# 确保 uvicorn 已安装
pip install uvicorn
deactivate

# 检查配置文件
if [ ! -f "game_config_v2.json" ]; then
    if [ -f "game_config.json" ]; then
        echo ">>> 复制 game_config.json 到 game_config_v2.json..."
        cp game_config.json game_config_v2.json
    else
        echo ">>> 警告: 未找到 game_config_v2.json 或 game_config.json，后端可能无法启动！"
    fi
fi

# 3. 前端准备
echo ">>> 设置前端项目..."
cd $FRONTEND_DIR

# 安装 Node 依赖
echo ">>> 安装 Node.js 依赖..."
# 如果需要更高版本的 node，请提前在服务器上安装对应版本
npm install

# 清理旧构建
echo ">>> 清理旧构建..."
rm -rf dist

# 构建前端
echo ">>> 构建 Vue.js 应用（生产）..."
npm run build

# 4. 为后端配置 Systemd 服务
echo ">>> 配置 Systemd 后端服务..."
SERVICE_FILE="/etc/systemd/system/$SERVICE_NAME.service"

sudo bash -c "cat > $SERVICE_FILE" <<EOL
[Unit]
Description=Slot Game Backend API
After=network.target

[Service]
User=$USER_NAME
Group=$USER_NAME
WorkingDirectory=$BACKEND_DIR
Environment="PATH=$BACKEND_DIR/venv/bin"
ExecStart=$BACKEND_DIR/venv/bin/uvicorn app:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
EOL

echo ">>> 重新加载 Systemd 配置并启动服务..."
sudo systemctl daemon-reload
sudo systemctl enable $SERVICE_NAME
sudo systemctl restart $SERVICE_NAME

# 5. Nginx 配置
echo ">>> 配置 Nginx 以提供前端并代理后端 API..."
NGINX_CONFIG="/etc/nginx/sites-available/slot-game"

# 使用 cat 写入配置
# 注意：为了防止 Windows 换行符 (\r) 导致 Nginx 配置错误 (如 location /api/^M)，
# 我们会在写入后使用 sed 清理文件。
sudo bash -c "cat > $NGINX_CONFIG" <<EOL
server {
    listen 80 default_server;
    server_name _;

    # 前端静态文件
    location / {
        root $FRONTEND_DIR/dist;
        index index.html;
        try_files \$uri \$uri/ /index.html;
    }

    # 后端 API 代理
    # 使用 ^~ 提高优先级，确保 /api/ 开头的请求一定被此块处理
    location ^~ /api/ {
        proxy_pass http://127.0.0.1:8000/;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        
        # 增加超时设置，防止长轮询或慢请求断开
        proxy_connect_timeout 60s;
        proxy_read_timeout 60s;
    }
}
EOL

# 清理可能存在的 Windows 换行符 (\r)
echo ">>> 清理 Nginx 配置文件中的 Windows 换行符..."
sudo sed -i 's/\r$//' $NGINX_CONFIG

# 启用站点配置
if [ ! -f "/etc/nginx/sites-enabled/slot-game" ]; then
    sudo ln -s $NGINX_CONFIG /etc/nginx/sites-enabled/
fi

# 移除默认站点（如存在）
if [ -f "/etc/nginx/sites-enabled/default" ]; then
    sudo rm /etc/nginx/sites-enabled/default
fi

echo ">>> 重启 Nginx..."
sudo systemctl restart nginx

echo ">>> 等待后端服务启动 (最多等待 60 秒)..."
# 循环检查端口，每 2 秒检查一次，最多 30 次
PORT_READY=false
for i in {1..30}; do
    if ss -tuln | grep :8000 > /dev/null; then
        PORT_READY=true
        echo -e "\n>>> 后端端口 8000 已就绪！"
        break
    fi
    echo -n "."
    sleep 2
done

if [ "$PORT_READY" = false ]; then
    echo -e "\n>>> [错误] 等待超时，端口 8000 未监听！后端服务可能启动失败或启动过慢。"
    echo ">>> 正在获取服务日志..."
    sudo journalctl -u $SERVICE_NAME -n 20 --no-pager
    exit 1
fi

# 检查本地直接访问后端
echo ">>> [检查] 尝试直接访问后端 API (http://127.0.0.1:8000/config)..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/config)
if [ "$HTTP_CODE" == "200" ]; then
    echo ">>> [成功] 后端直接访问正常 (HTTP 200)"
else
    echo ">>> [错误] 后端直接访问失败 (HTTP $HTTP_CODE)"
    sudo journalctl -u $SERVICE_NAME -n 20 --no-pager
    exit 1
fi

# 检查 Nginx 代理访问
echo ">>> [检查] 尝试通过 Nginx 访问 API (http://localhost/api/config)..."
PROXY_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost/api/config)
if [ "$PROXY_CODE" == "200" ]; then
    echo ">>> [成功] Nginx 代理访问正常 (HTTP 200)"
else
    echo ">>> [错误] Nginx 代理访问失败 (HTTP $PROXY_CODE)"
    echo ">>> 这可能是 Nginx 配置问题或后端问题。"
    echo ">>> 检查 Nginx 状态..."
    sudo systemctl status nginx --no-pager
    echo ">>> 检查 Nginx 错误日志..."
    sudo tail -n 20 /var/log/nginx/error.log
fi

# 关于 PM2 的提示
if command -v pm2 >/dev/null 2>&1; then
    echo ">>> [提示] 检测到已安装 PM2。"
    echo ">>> 本部署脚本使用 Systemd ($SERVICE_NAME) 管理服务，而非 PM2。"
    echo ">>> 如果您之前使用 PM2 启动过服务，请确保已停止，以免端口冲突。"
    pm2 status || true
else
    echo ">>> [提示] 未检测到 PM2 (本脚本使用 Systemd 管理服务，无需 PM2)。"
fi

echo ">>> 部署脚本执行完毕！"
echo ">>> 后端日志查看命令: sudo journalctl -u $SERVICE_NAME -f"


