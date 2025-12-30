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
sudo apt-get install -y python3 python3-pip python3-venv nodejs npm nginx git

# 2. 后端准备
echo ">>> 设置后端环境..."
cd $BACKEND_DIR

# 创建虚拟环境
if [ ! -d "venv" ]; then
    echo ">>> 创建 Python 虚拟环境..."
    python3 -m venv venv
fi

# 安装 Python 依赖
echo ">>> 安装 Python 依赖..."
source venv/bin/activate
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

sudo bash -c "cat > $NGINX_CONFIG" <<EOL
server {
    listen 80;
    server_name $DOMAIN_NAME;

    # 前端静态文件
    location / {
        root $FRONTEND_DIR/dist;
        index index.html;
        try_files \$uri \$uri/ /index.html;
    }

    # 后端 API 代理（将 /api/ 前缀转发到后端）
    location /api/ {
        # 将 /api/xxx -> http://127.0.0.1:8000/xxx
        proxy_pass http://127.0.0.1:8000/;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
    }
}
EOL

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

echo ">>> 等待后端服务启动 (10秒)..."
sleep 10
if curl -s http://127.0.0.1:8000/docs > /dev/null; then
    echo ">>> 后端服务启动成功！"
else
    echo ">>> 警告: 后端服务似乎未正常响应。请检查日志："
    echo ">>> sudo journalctl -u $SERVICE_NAME -n 50"
fi

echo ">>> 部署完成！"
echo ">>> 后端已在 8000 端口运行（systemd 服务: $SERVICE_NAME）"
echo ">>> 前端由 Nginx 提供，监听 80 端口" 
echo ">>> 后端 API 通过 /api/ 前缀代理访问"

