# CloudDate — 云端资源监控面板

轻量级、实时的 Ubuntu 服务器资源监控面板，无需登录即可查看。

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-green)
![Docker](https://img.shields.io/badge/Docker-Ready-blue)
![License](https://img.shields.io/badge/License-MIT-yellow)

## ✨ 功能特性

- **📊 实时监控** — CPU、内存、交换空间、网络、磁盘I/O、负载
- **🔄 可调刷新频率** — 0.5s ~ 30s，对数滑块无级调节
- **📋 进程列表** — 按 CPU/内存 占用排序的 Top 进程
- **🐳 Docker 监控** — 容器状态、CPU/内存占用
- **🌡️ 温度传感器** — 硬件温度实时显示
- **💤 智能休眠** — 无人访问时自动停止采集，零资源占用
- **🔔 实时告警** — CPU/内存/磁盘超阈值视觉告警
- **🎨 Glassmorphism UI** — 现代玻璃态设计，响应式布局
- **🐳 Docker 部署** — 一键部署，开箱即用
- **🔐 可选 Token** — 默认开放，部署时可配置访问令牌

## 🚀 快速开始

### Docker 部署（推荐）

```bash
# 克隆项目
git clone <repo-url> clouddate
cd clouddate

# 启动
docker compose up -d

# 访问 http://your-server:5001
```

### 自定义配置

```bash
# 自定义端口和 Token
PORT=8080 TOKEN=my_secret docker compose up -d

# 访问 http://your-server:8080?token=my_secret
```

### 直接运行（开发模式）

```bash
# 安装依赖
pip install -r requirements.txt

# 启动
python -m server.main

# 访问 http://localhost:5001
```

## ⚙️ 环境变量配置

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `PORT` | `5001` | 监听端口 |
| `TOKEN` | _(空)_ | 访问令牌，为空则无需认证 |
| `RING_BUFFER_SIZE` | `3600` | 环形缓冲区大小（数据点数量） |
| `SLEEP_DELAY` | `30` | 无人访问后进入休眠的延迟（秒） |
| `PROCESS_LIMIT` | `50` | 进程列表最大条目数 |
| `ALERT_CPU` | `90` | CPU 告警阈值 (%) |
| `ALERT_MEM` | `90` | 内存告警阈值 (%) |
| `ALERT_SWAP` | `80` | 交换空间告警阈值 (%) |
| `ALERT_DISK` | `90` | 磁盘告警阈值 (%) |

## 📐 架构

```
┌─────────────────────────────────────────────────┐
│                 Browser (ECharts)                │
│            WebSocket ↕ Real-time Data            │
├─────────────────────────────────────────────────┤
│              FastAPI + WebSocket                 │
│  ┌──────────┐  ┌──────────┐  ┌───────────────┐  │
│  │ Fast Loop│  │Slow Loop │  │  Connection   │  │
│  │ CPU/Mem  │  │Proc/Docker│ │  Manager +    │  │
│  │ Net/Disk │  │Disk/Temp │  │  Sleep/Wake   │  │
│  └────┬─────┘  └────┬─────┘  └───────────────┘  │
│       ↓              ↓                           │
│  ┌──────────────────────────┐                    │
│  │    Ring Buffer (Memory)  │                    │
│  └──────────────────────────┘                    │
├─────────────────────────────────────────────────┤
│  /proc  /sys  docker.sock  psutil               │
└─────────────────────────────────────────────────┘
```

## 🔒 安全说明

- 默认模式下**无需登录**，任何能访问端口的人都可查看
- 生产环境建议设置 `TOKEN` 或通过反向代理（Nginx）添加认证
- Docker socket 以只读模式挂载 (`ro`)
- 容器不使用特权模式
- 如不需要 Docker 监控，可移除 `docker.sock` 挂载

## 📁 项目结构

```
CloudDate/
├── server/                     # Python 后端
│   ├── main.py                 # FastAPI 入口
│   ├── config.py               # 配置管理
│   ├── ring_buffer.py          # 环形缓冲区
│   ├── connection_manager.py   # WebSocket 连接管理 + 休眠
│   ├── scheduler.py            # 采集调度器
│   └── collectors/             # 数据采集器
│       ├── cpu.py              # CPU
│       ├── memory.py           # 内存/交换
│       ├── disk.py             # 磁盘
│       ├── network.py          # 网络
│       ├── process.py          # 进程
│       ├── docker_stats.py     # Docker
│       ├── system_info.py      # 系统信息
│       └── temperature.py      # 温度
├── web/                        # 前端静态文件
│   ├── index.html
│   ├── css/style.css
│   └── js/
│       ├── app.js
│       ├── websocket.js
│       ├── charts.js
│       └── utils.js
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

## 📄 License

MIT
