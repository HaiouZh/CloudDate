"""
CloudDate — Main Entry Point
FastAPI application with WebSocket endpoint and static file serving.
"""

import asyncio
import json
import logging
import os
import sys
from pathlib import Path

import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

from server.config import config
from server.ring_buffer import MetricsStore
from server.connection_manager import ConnectionManager
from server.scheduler import Scheduler
from server.collectors.system_info import collect_system_info


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("clouddate")

# Global instances
store = MetricsStore(config.RING_BUFFER_SIZE)
manager = ConnectionManager(sleep_delay=config.SLEEP_DELAY)
scheduler = Scheduler(store, manager)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler for startup and shutdown."""
    # Startup
    logger.info(f"CloudDate starting on port {config.PORT}")
    logger.info(f"Token protection: {'enabled' if config.TOKEN else 'disabled'}")
    logger.info(f"Ring buffer size: {config.RING_BUFFER_SIZE}")
    logger.info(f"Sleep delay: {config.SLEEP_DELAY}s")
    await scheduler.start()
    yield
    # Shutdown
    await scheduler.stop()
    logger.info("CloudDate stopped")


# Create app
app = FastAPI(
    title="CloudDate",
    description="Ubuntu Cloud Resource Monitor",
    version="1.0.0",
    lifespan=lifespan,
)


def _check_token(token: str | None) -> bool:
    """Validate access token if configured."""
    if not config.TOKEN:
        return True
    return token == config.TOKEN


# --- REST API ---

@app.get("/api/config")
async def get_config(token: str | None = Query(None)):
    """Return current server configuration."""
    if not _check_token(token):
        raise HTTPException(status_code=403, detail="Invalid token")
    return {
        "min_fast_interval": config.MIN_FAST_INTERVAL,
        "min_slow_interval": config.MIN_SLOW_INTERVAL,
        "max_interval": config.MAX_INTERVAL,
        "default_interval": config.DEFAULT_INTERVAL,
        "buffer_size": config.RING_BUFFER_SIZE,
        "alerts": {
            "cpu": config.ALERT_CPU_PERCENT,
            "memory": config.ALERT_MEMORY_PERCENT,
            "swap": config.ALERT_SWAP_PERCENT,
            "disk": config.ALERT_DISK_PERCENT,
        },
    }


@app.get("/api/history/{metric_type}")
async def get_history(metric_type: str, n: int = 60, token: str | None = Query(None)):
    """Get historical data points from ring buffer."""
    if not _check_token(token):
        raise HTTPException(status_code=403, detail="Invalid token")

    if metric_type == "fast":
        return store.fast_metrics.get_latest(n)
    elif metric_type == "slow":
        return store.slow_metrics.get_latest(n)
    else:
        raise HTTPException(status_code=400, detail="Invalid metric type. Use 'fast' or 'slow'.")


# --- WebSocket ---

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str | None = Query(None)):
    """
    Main WebSocket endpoint for real-time metrics streaming.

    Client messages:
    - {"type": "set_interval", "value": 2.0}
    - {"type": "pause"}
    - {"type": "resume"}

    Server messages:
    - {"type": "system_info", ...}
    - {"type": "metrics", ...}
    - {"type": "slow_metrics", ...}
    """
    # Token check
    if not _check_token(token):
        await websocket.close(code=4003, reason="Invalid token")
        return

    conn_id = await manager.connect(websocket)

    try:
        # Send system info on connect
        sys_info = await asyncio.get_event_loop().run_in_executor(None, collect_system_info)
        await manager.send_to(conn_id, {
            "type": "system_info",
            **sys_info,
        })

        # Send recent history so the client can populate charts immediately
        fast_history = store.fast_metrics.get_latest(120)
        if fast_history:
            await manager.send_to(conn_id, {
                "type": "history",
                "data": fast_history,
            })

        # Listen for client commands
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                msg_type = msg.get("type", "")

                if msg_type == "set_interval":
                    value = float(msg.get("value", config.DEFAULT_INTERVAL))
                    # Clamp to valid range
                    value = max(config.MIN_FAST_INTERVAL, min(config.MAX_INTERVAL, value))
                    manager.set_interval(conn_id, value)
                    await manager.send_to(conn_id, {
                        "type": "interval_set",
                        "value": value,
                    })

                elif msg_type == "pause":
                    manager.set_paused(conn_id, True)
                    await manager.send_to(conn_id, {"type": "paused"})

                elif msg_type == "resume":
                    manager.set_paused(conn_id, False)
                    await manager.send_to(conn_id, {"type": "resumed"})

                elif msg_type == "ping":
                    await manager.send_to(conn_id, {"type": "pong"})

            except (json.JSONDecodeError, ValueError) as e:
                await manager.send_to(conn_id, {
                    "type": "error",
                    "message": str(e),
                })

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WebSocket error for {conn_id}: {e}")
    finally:
        await manager.disconnect(conn_id)


# --- Static Files ---

# Determine web directory path
_web_dir = Path(__file__).parent.parent / "web"


# Token login page template
_TOKEN_PAGE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>CloudDate — Access</title>
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>📊</text></svg>">
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Inter',sans-serif;background:#0a0a1a;color:rgba(255,255,255,0.92);
min-height:100vh;display:flex;align-items:center;justify-content:center;overflow:hidden}
body::before{content:'';position:fixed;width:500px;height:500px;border-radius:50%;
background:#6c5ce7;filter:blur(120px);opacity:0.12;top:-100px;left:-80px;animation:f 20s ease-in-out infinite}
body::after{content:'';position:fixed;width:400px;height:400px;border-radius:50%;
background:#00cec9;filter:blur(120px);opacity:0.12;bottom:-80px;right:-60px;animation:f 20s ease-in-out infinite reverse}
@keyframes f{0%,100%{transform:translate(0,0)}50%{transform:translate(60px,40px)}}
.card{position:relative;z-index:1;background:rgba(255,255,255,0.04);backdrop-filter:blur(20px);
-webkit-backdrop-filter:blur(20px);border:1px solid rgba(255,255,255,0.08);border-radius:20px;
padding:48px 40px;width:min(420px,90vw);box-shadow:0 16px 64px rgba(0,0,0,0.4);text-align:center}
.logo{font-size:2rem;font-weight:700;background:linear-gradient(135deg,#6c5ce7,#00cec9);
-webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:6px}
.subtitle{font-size:0.8rem;color:rgba(255,255,255,0.35);letter-spacing:1.5px;text-transform:uppercase;margin-bottom:32px}
.icon-lock{font-size:2.5rem;margin-bottom:16px}
.msg{font-size:0.9rem;color:rgba(255,255,255,0.5);margin-bottom:24px;line-height:1.6}
.input-wrap{position:relative;margin-bottom:20px}
input[type=password]{width:100%;padding:14px 18px;background:rgba(255,255,255,0.06);
border:1px solid rgba(255,255,255,0.1);border-radius:12px;color:#fff;font-family:'Inter',sans-serif;
font-size:0.95rem;outline:none;transition:border-color 0.25s}
input[type=password]:focus{border-color:rgba(108,92,231,0.6);box-shadow:0 0 16px rgba(108,92,231,0.15)}
input[type=password]::placeholder{color:rgba(255,255,255,0.25)}
button{width:100%;padding:14px;background:linear-gradient(135deg,#6c5ce7,#5a4bd1);
border:none;border-radius:12px;color:#fff;font-family:'Inter',sans-serif;font-size:0.95rem;
font-weight:600;cursor:pointer;transition:all 0.25s;letter-spacing:0.5px}
button:hover{transform:translateY(-1px);box-shadow:0 8px 24px rgba(108,92,231,0.35)}
button:active{transform:translateY(0)}
.error{color:#e17055;font-size:0.82rem;margin-top:12px;display:none}
.remember{display:flex;align-items:center;gap:8px;margin-bottom:20px;font-size:0.82rem;color:rgba(255,255,255,0.45)}
.remember input{accent-color:#6c5ce7}
</style>
</head>
<body>
<div class="card">
<div class="logo">CloudDate</div>
<div class="subtitle">Server Resource Monitor</div>
<div class="icon-lock">🔐</div>
<div class="msg">This dashboard requires an access token.<br>Please enter your token to continue.</div>
<form id="token-form">
<div class="input-wrap">
<input type="password" id="token-input" placeholder="Enter access token..." autocomplete="off" autofocus>
</div>
<label class="remember"><input type="checkbox" id="remember" checked> Remember on this device</label>
<button type="submit">Access Dashboard</button>
<div class="error" id="error-msg">Invalid token. Please try again.</div>
</form>
</div>
<script>
const form=document.getElementById('token-form');
const input=document.getElementById('token-input');
const err=document.getElementById('error-msg');
const remember=document.getElementById('remember');
// Check localStorage for saved token
const saved=localStorage.getItem('clouddate_token');
if(saved){input.value=saved;form.dispatchEvent(new Event('submit'))}
form.addEventListener('submit',async(e)=>{
    e.preventDefault();
    const token=input.value.trim();
    if(!token)return;
    try{
        const r=await fetch('/api/config?token='+encodeURIComponent(token));
        if(r.ok){
            if(remember.checked)localStorage.setItem('clouddate_token',token);
            window.location.href='/?token='+encodeURIComponent(token);
        }else{
            err.style.display='block';input.style.borderColor='#e17055';
            setTimeout(()=>{err.style.display='none';input.style.borderColor=''},3000);
        }
    }catch{err.style.display='block'}
});
</script>
</body></html>"""


@app.get("/")
async def serve_index(token: str | None = Query(None)):
    """Serve the main HTML page or token login page."""
    if not _check_token(token):
        from fastapi.responses import HTMLResponse
        return HTMLResponse(_TOKEN_PAGE)
    return FileResponse(_web_dir / "index.html")


# Mount static assets
app.mount("/css", StaticFiles(directory=_web_dir / "css"), name="css")
app.mount("/js", StaticFiles(directory=_web_dir / "js"), name="js")


# --- Entry Point ---

def main():
    """Run the application."""
    uvicorn.run(
        "server.main:app",
        host=config.HOST,
        port=config.PORT,
        log_level="info",
        access_log=False,
    )


if __name__ == "__main__":
    main()
