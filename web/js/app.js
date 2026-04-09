/**
 * CloudDate — Main Application
 * Connects WebSocket, updates charts, tables, and UI components.
 */

let ws, chartManager;
let isPaused = false;
let currentInterval = 2.0;
let uptimeStart = 0;
let uptimeTimer = null;
let _allServices = [];  // cached for filtering
let _svcFilter = 'all';
let _svcSearch = '';

document.addEventListener('DOMContentLoaded', () => {
    chartManager = new ChartManager();
    chartManager.init();
    initControls();
    connectWebSocket();
    startUptimeTicker();
});

function connectWebSocket() {
    ws = new CloudDateWebSocket({
        onMetrics: handleMetrics,
        onSlowMetrics: handleSlowMetrics,
        onSystemInfo: handleSystemInfo,
        onHistory: handleHistory,
        onStatus: handleStatus,
        onAlert: handleAlerts,
    });
    ws.connect();
}

// -------- Data Handlers --------

function handleMetrics(data) {
    // Update stat cards
    updateStatCard('cpu-value', `${data.cpu.total}%`, data.cpu.total);
    updateStatCard('mem-value', `${data.memory.percent}%`, data.memory.percent);
    updateStatCard('swap-value', `${data.swap.percent}%`, data.swap.percent);

    // Memory detail
    const memDetail = document.getElementById('mem-detail');
    if (memDetail) {
        memDetail.textContent = `${Utils.formatBytes(data.memory.used)} / ${Utils.formatBytes(data.memory.total)}`;
    }
    const swapDetail = document.getElementById('swap-detail');
    if (swapDetail) {
        swapDetail.textContent = `${Utils.formatBytes(data.swap.used)} / ${Utils.formatBytes(data.swap.total)}`;
    }

    // Load average
    const loadEl = document.getElementById('load-value');
    if (loadEl && data.cpu.load_avg) {
        loadEl.textContent = data.cpu.load_avg.map(v => v.toFixed(2)).join('  ');
    }

    // Network aggregate
    let rxTotal = 0, txTotal = 0;
    if (data.network) {
        Object.values(data.network).forEach(iface => {
            rxTotal += iface.rx_rate || 0;
            txTotal += iface.tx_rate || 0;
        });
    }
    const netDown = document.getElementById('net-down-value');
    const netUp = document.getElementById('net-up-value');
    if (netDown) netDown.textContent = Utils.formatRate(rxTotal);
    if (netUp) netUp.textContent = Utils.formatRate(txTotal);

    // Disk IO
    const diskRead = document.getElementById('disk-read-value');
    const diskWrite = document.getElementById('disk-write-value');
    if (diskRead) diskRead.textContent = Utils.formatRate(data.disk_io?.read_rate || 0);
    if (diskWrite) diskWrite.textContent = Utils.formatRate(data.disk_io?.write_rate || 0);

    // Update charts
    chartManager.updateFastMetrics(data);
}

function handleSlowMetrics(data) {
    if (data.processes) updateProcessTable(data.processes);
    if (data.docker) updateDockerTable(data.docker);
    if (data.disks) updateDiskBars(data.disks);
    if (data.temperatures) updateTemperatures(data.temperatures);
    if (data.services !== undefined) updateServicesTable(data.services);
}

function handleSystemInfo(data) {
    document.getElementById('sys-hostname').textContent = data.hostname || '-';
    document.getElementById('sys-os').textContent = data.os || '-';
    document.getElementById('sys-kernel').textContent = data.kernel || '-';
    document.getElementById('sys-arch').textContent = data.arch || '-';
    document.getElementById('sys-cpu-model').textContent = data.cpu_model || '-';
    document.getElementById('sys-cpu-cores').textContent = `${data.cpu_cores_physical || 0}P / ${data.cpu_cores_logical || 0}L`;
    document.getElementById('sys-memory').textContent = Utils.formatBytes(data.total_memory || 0);
    document.getElementById('sys-swap').textContent = Utils.formatBytes(data.total_swap || 0);

    // Setup uptime ticker
    uptimeStart = data.uptime || 0;
    updateUptime();
}

function handleHistory(data) {
    chartManager.loadHistory(data);
}

function handleStatus(status, detail) {
    const statusDot = document.getElementById('status-dot');
    const statusText = document.getElementById('status-text');

    if (status === 'connected') {
        statusDot.className = 'status-dot connected';
        statusText.textContent = 'Connected';
    } else if (status === 'disconnected') {
        statusDot.className = 'status-dot disconnected';
        statusText.textContent = 'Reconnecting...';
    } else if (status === 'error') {
        statusDot.className = 'status-dot error';
        statusText.textContent = 'Connection Error';
    } else if (status === 'paused') {
        statusText.textContent = 'Paused';
    } else if (status === 'resumed') {
        statusText.textContent = 'Connected';
    }
}

function handleAlerts(alerts) {
    alerts.forEach(alert => {
        let cardId = null;
        if (alert.type === 'cpu') cardId = 'card-cpu';
        else if (alert.type === 'memory') cardId = 'card-mem';
        else if (alert.type === 'swap') cardId = 'card-swap';

        if (cardId) {
            const card = document.getElementById(cardId);
            if (card) {
                card.classList.add('alert-flash');
                setTimeout(() => card.classList.remove('alert-flash'), 2000);
            }
        }
    });
}

// -------- UI Update Functions --------

function updateStatCard(id, text, pct) {
    const el = document.getElementById(id);
    if (el) {
        el.textContent = text;
        el.style.color = Utils.lerpColor(pct);
    }
}

function updateProcessTable(processes) {
    const tbody = document.getElementById('process-tbody');
    if (!tbody) return;

    let html = '';
    processes.forEach(p => {
        const cpuColor = Utils.lerpColor(p.cpu);
        const memColor = Utils.lerpColor(p.mem * 5); // Scale for visibility
        html += `<tr>
            <td>${p.pid}</td>
            <td class="proc-name" title="${p.name}">${p.name}</td>
            <td style="color:${cpuColor};font-weight:600">${p.cpu}%</td>
            <td style="color:${memColor}">${p.mem}%</td>
            <td class="col-user">${p.user}</td>
            <td class="col-status"><span class="proc-status proc-${p.status}">${p.status}</span></td>
        </tr>`;
    });
    tbody.innerHTML = html;
}

function updateDockerTable(containers) {
    const tbody = document.getElementById('docker-tbody');
    const emptyMsg = document.getElementById('docker-empty');
    if (!tbody) return;

    if (containers.length === 0) {
        tbody.innerHTML = '';
        if (emptyMsg) emptyMsg.style.display = 'block';
        return;
    }

    if (emptyMsg) emptyMsg.style.display = 'none';

    let html = '';
    containers.forEach(c => {
        const statusColor = Utils.getDockerStatusColor(c.status);
        const uptime = Utils.formatDockerCreated(c.created);
        html += `<tr>
            <td class="docker-name" title="${c.name}">${c.name}</td>
            <td class="docker-image" title="${c.image}">${c.image}</td>
            <td><span class="docker-status" style="color:${statusColor}">● ${c.status}</span></td>
            <td>${c.cpu}%</td>
            <td>${c.mem}%</td>
            <td>${uptime}</td>
        </tr>`;
    });
    tbody.innerHTML = html;
}

function updateDiskBars(disks) {
    const container = document.getElementById('disk-bars');
    if (!container) return;

    let html = '';
    disks.forEach(d => {
        const color = Utils.lerpColor(d.percent);
        const isAlert = d.percent >= 90;
        html += `<div class="disk-item${isAlert ? ' disk-alert' : ''}">
            <div class="disk-header">
                <span class="disk-mount" title="${d.mount}">${d.mount}</span>
                <span class="disk-usage">${Utils.formatBytes(d.used)} / ${Utils.formatBytes(d.total)}</span>
            </div>
            <div class="disk-bar-track">
                <div class="disk-bar-fill" style="width:${d.percent}%;background:${color}"></div>
            </div>
            <div class="disk-percent">${d.percent}%</div>
        </div>`;
    });
    container.innerHTML = html;
}

function updateTemperatures(temps) {
    const container = document.getElementById('temp-container');
    if (!container) return;

    if (temps.length === 0) {
        container.innerHTML = '<div class="temp-empty">No sensors detected</div>';
        return;
    }

    let html = '';
    temps.forEach(t => {
        const maxTemp = t.critical || t.high || 100;
        const pct = Math.min(100, (t.current / maxTemp) * 100);
        const color = Utils.lerpColor(pct);
        html += `<div class="temp-item">
            <div class="temp-label">${t.label}</div>
            <div class="temp-value" style="color:${color}">${t.current}°C</div>
            ${t.high ? `<div class="temp-limit">High: ${t.high}°C</div>` : ''}
        </div>`;
    });
    container.innerHTML = html;
}

// -------- Services --------

function updateServicesTable(services) {
    const tbody = document.getElementById('services-tbody');
    const emptyMsg = document.getElementById('services-empty');
    const countsEl = document.getElementById('service-counts');
    if (!tbody) return;

    _allServices = services;

    if (services.length === 0) {
        tbody.innerHTML = '';
        if (emptyMsg) emptyMsg.style.display = 'block';
        if (countsEl) countsEl.textContent = '';
        return;
    }

    if (emptyMsg) emptyMsg.style.display = 'none';

    // Counts
    const running = services.filter(s => s.sub === 'running').length;
    const failed = services.filter(s => s.active === 'failed').length;
    if (countsEl) {
        let countHtml = `<span class="svc-count-running">${running} running</span>`;
        if (failed > 0) countHtml += ` <span class="svc-count-failed">${failed} failed</span>`;
        countsEl.innerHTML = countHtml;
    }

    renderFilteredServices();
}

function renderFilteredServices() {
    const tbody = document.getElementById('services-tbody');
    if (!tbody) return;

    let filtered = _allServices;

    // Apply tab filter
    if (_svcFilter === 'running') {
        filtered = filtered.filter(s => s.sub === 'running');
    } else if (_svcFilter === 'failed') {
        filtered = filtered.filter(s => s.active === 'failed');
    } else if (_svcFilter === 'inactive') {
        filtered = filtered.filter(s => s.active === 'inactive');
    }

    // Apply search
    if (_svcSearch) {
        const q = _svcSearch.toLowerCase();
        filtered = filtered.filter(s =>
            s.name.toLowerCase().includes(q) ||
            s.description.toLowerCase().includes(q)
        );
    }

    let html = '';
    filtered.forEach(s => {
        const activeColor = s.active === 'active' ? 'var(--accent-green)'
            : s.active === 'failed' ? 'var(--accent-coral)'
            : 'var(--text-muted)';
        const subBadge = s.sub === 'running' ? 'svc-running'
            : s.sub === 'exited' ? 'svc-exited'
            : s.sub === 'failed' ? 'svc-failed'
            : s.sub === 'dead' ? 'svc-dead'
            : 'svc-other';
        html += `<tr>
            <td class="svc-name" title="${s.name}">${s.name.replace('.service', '')}</td>
            <td style="color:${activeColor};font-weight:500">● ${s.active}</td>
            <td><span class="svc-badge ${subBadge}">${s.sub}</span></td>
            <td class="col-svc-desc svc-desc" title="${s.description}">${s.description}</td>
        </tr>`;
    });

    if (filtered.length === 0) {
        html = `<tr><td colspan="4" style="text-align:center;color:var(--text-muted);padding:20px">No matching services</td></tr>`;
    }

    tbody.innerHTML = html;
}

// -------- Controls --------

function initControls() {
    const slider = document.getElementById('interval-slider');
    const display = document.getElementById('interval-display');
    const pauseBtn = document.getElementById('btn-pause');

    if (slider) {
        // Logarithmic slider: 0.5s to 30s
        slider.addEventListener('input', () => {
            const raw = parseFloat(slider.value);
            // Map slider 0-100 to log(0.5) to log(30)
            const minLog = Math.log(0.5);
            const maxLog = Math.log(30);
            const value = Math.exp(minLog + (raw / 100) * (maxLog - minLog));
            currentInterval = Math.round(value * 10) / 10;

            if (display) display.textContent = `${currentInterval}s`;
            if (ws) ws.setInterval(currentInterval);
        });

        // Set initial position
        const initLog = (Math.log(currentInterval) - Math.log(0.5)) / (Math.log(30) - Math.log(0.5)) * 100;
        slider.value = initLog;
        if (display) display.textContent = `${currentInterval}s`;
    }

    if (pauseBtn) {
        pauseBtn.addEventListener('click', () => {
            isPaused = !isPaused;
            if (isPaused) {
                ws.pause();
                pauseBtn.innerHTML = '<span class="icon">▶</span> Resume';
                pauseBtn.classList.add('paused');
            } else {
                ws.resume();
                pauseBtn.innerHTML = '<span class="icon">⏸</span> Pause';
                pauseBtn.classList.remove('paused');
            }
        });
    }

    // Service filter tabs
    const tabContainer = document.getElementById('service-tabs');
    if (tabContainer) {
        tabContainer.addEventListener('click', (e) => {
            const btn = e.target.closest('.svc-tab');
            if (!btn) return;
            tabContainer.querySelectorAll('.svc-tab').forEach(t => t.classList.remove('active'));
            btn.classList.add('active');
            _svcFilter = btn.dataset.filter;
            renderFilteredServices();
        });
    }

    // Service search
    const svcSearch = document.getElementById('service-search');
    if (svcSearch) {
        svcSearch.addEventListener('input', Utils.debounce(() => {
            _svcSearch = svcSearch.value.trim();
            renderFilteredServices();
        }, 200));
    }
}

// -------- Uptime Ticker --------

function startUptimeTicker() {
    uptimeTimer = setInterval(() => {
        uptimeStart += 1;
        updateUptime();
    }, 1000);
}

function updateUptime() {
    const el = document.getElementById('sys-uptime');
    if (el) el.textContent = Utils.formatUptime(uptimeStart);
}
