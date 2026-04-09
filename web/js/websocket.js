/**
 * CloudDate — WebSocket Client
 * Handles connection, reconnection, and message routing.
 */

class CloudDateWebSocket {
    constructor(options = {}) {
        this.url = options.url || this._buildUrl();
        this.onMetrics = options.onMetrics || (() => {});
        this.onSlowMetrics = options.onSlowMetrics || (() => {});
        this.onSystemInfo = options.onSystemInfo || (() => {});
        this.onHistory = options.onHistory || (() => {});
        this.onStatus = options.onStatus || (() => {});
        this.onAlert = options.onAlert || (() => {});

        this.ws = null;
        this.reconnectDelay = 1000;
        this.maxReconnectDelay = 30000;
        this.connected = false;
        this._shouldReconnect = true;
    }

    _buildUrl() {
        const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
        const params = new URLSearchParams(location.search);
        const token = params.get('token');
        let url = `${proto}//${location.host}/ws`;
        if (token) url += `?token=${token}`;
        return url;
    }

    connect() {
        this._shouldReconnect = true;
        this._doConnect();
    }

    _doConnect() {
        if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
            return;
        }

        try {
            this.ws = new WebSocket(this.url);
        } catch (e) {
            this._scheduleReconnect();
            return;
        }

        this.ws.onopen = () => {
            this.connected = true;
            this.reconnectDelay = 1000;
            this.onStatus('connected');
        };

        this.ws.onclose = () => {
            this.connected = false;
            this.onStatus('disconnected');
            if (this._shouldReconnect) {
                this._scheduleReconnect();
            }
        };

        this.ws.onerror = () => {
            this.connected = false;
            this.onStatus('error');
        };

        this.ws.onmessage = (event) => {
            try {
                const msg = JSON.parse(event.data);
                this._handleMessage(msg);
            } catch (e) {
                console.error('Failed to parse message:', e);
            }
        };
    }

    _handleMessage(msg) {
        switch (msg.type) {
            case 'metrics':
                this.onMetrics(msg);
                if (msg.alerts && msg.alerts.length > 0) {
                    this.onAlert(msg.alerts);
                }
                break;
            case 'slow_metrics':
                this.onSlowMetrics(msg);
                if (msg.disk_alerts && msg.disk_alerts.length > 0) {
                    this.onAlert(msg.disk_alerts);
                }
                break;
            case 'system_info':
                this.onSystemInfo(msg);
                break;
            case 'history':
                this.onHistory(msg.data);
                break;
            case 'interval_set':
            case 'paused':
            case 'resumed':
            case 'pong':
                this.onStatus(msg.type, msg);
                break;
            case 'error':
                console.error('Server error:', msg.message);
                break;
        }
    }

    _scheduleReconnect() {
        setTimeout(() => {
            if (this._shouldReconnect) {
                this._doConnect();
            }
        }, this.reconnectDelay);
        this.reconnectDelay = Math.min(this.reconnectDelay * 1.5, this.maxReconnectDelay);
    }

    setInterval(value) {
        this._send({ type: 'set_interval', value });
    }

    pause() {
        this._send({ type: 'pause' });
    }

    resume() {
        this._send({ type: 'resume' });
    }

    ping() {
        this._send({ type: 'ping' });
    }

    _send(data) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify(data));
        }
    }

    disconnect() {
        this._shouldReconnect = false;
        if (this.ws) {
            this.ws.close();
        }
    }
}
