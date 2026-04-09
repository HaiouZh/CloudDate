/**
 * CloudDate — ECharts Manager
 * Manages all chart instances with real-time update support.
 * Designed for high-frequency updates (0.5s+) with smooth animations.
 */

const MAX_POINTS = 120; // Maximum data points on each chart

// Color palette — modern, vibrant
const COLORS = {
    primary: '#6c5ce7',
    secondary: '#a29bfe',
    accent: '#00cec9',
    success: '#00b894',
    warning: '#fdcb6e',
    danger: '#e17055',
    info: '#74b9ff',

    cpu: '#6c5ce7',
    cpuGradientTop: 'rgba(108,92,231,0.4)',
    cpuGradientBot: 'rgba(108,92,231,0.02)',

    memory: '#e17055',
    memGradientTop: 'rgba(225,112,85,0.4)',
    memGradientBot: 'rgba(225,112,85,0.02)',

    swap: '#fdcb6e',
    swapGradientTop: 'rgba(253,203,110,0.4)',
    swapGradientBot: 'rgba(253,203,110,0.02)',

    netRx: '#00cec9',
    netRxGradientTop: 'rgba(0,206,201,0.4)',
    netRxGradientBot: 'rgba(0,206,201,0.02)',
    netTx: '#6c5ce7',
    netTxGradientTop: 'rgba(108,92,231,0.4)',
    netTxGradientBot: 'rgba(108,92,231,0.02)',

    diskRead: '#00b894',
    diskReadGradientTop: 'rgba(0,184,148,0.4)',
    diskReadGradientBot: 'rgba(0,184,148,0.02)',
    diskWrite: '#e17055',
    diskWriteGradientTop: 'rgba(225,112,85,0.4)',
    diskWriteGradientBot: 'rgba(225,112,85,0.02)',

    load1: '#6c5ce7',
    load5: '#a29bfe',
    load15: '#dfe6e9',

    coreColors: [
        '#6c5ce7','#e17055','#00cec9','#fdcb6e',
        '#a29bfe','#ff7675','#55efc4','#ffeaa7',
        '#74b9ff','#fab1a0','#81ecec','#dfe6e9',
        '#636e72','#b2bec3','#fd79a8','#e84393',
    ],
};

// Shared chart options template
const baseChartOption = {
    animation: false,
    grid: {
        top: 10, right: 15, bottom: 24, left: 50,
        containLabel: false,
    },
    xAxis: {
        type: 'category',
        boundaryGap: false,
        axisLine: { lineStyle: { color: 'rgba(255,255,255,0.1)' } },
        axisLabel: { color: 'rgba(255,255,255,0.4)', fontSize: 10 },
        axisTick: { show: false },
        data: [],
    },
    yAxis: {
        type: 'value',
        min: 0,
        max: 100,
        splitNumber: 4,
        axisLine: { show: false },
        axisLabel: { color: 'rgba(255,255,255,0.4)', fontSize: 10, formatter: '{value}%' },
        splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } },
    },
    tooltip: {
        trigger: 'axis',
        backgroundColor: 'rgba(20,20,40,0.9)',
        borderColor: 'rgba(255,255,255,0.1)',
        textStyle: { color: '#fff', fontSize: 12 },
        axisPointer: { lineStyle: { color: 'rgba(255,255,255,0.2)' } },
    },
};

class ChartManager {
    constructor() {
        this.charts = {};
        this.timeLabels = [];
        this.cpuHistory = [];
        this.memHistory = [];
        this.swapHistory = [];
        this.netRxHistory = [];
        this.netTxHistory = [];
        this.diskReadHistory = [];
        this.diskWriteHistory = [];
        this.loadHistory = { l1: [], l5: [], l15: [] };
        this.coreHistories = [];
        this._resizeHandler = Utils.debounce(() => this.resizeAll(), 200);
        window.addEventListener('resize', this._resizeHandler);
    }

    /**
     * Initialize all chart instances.
     */
    init() {
        this.charts.cpu = echarts.init(document.getElementById('chart-cpu'));
        this.charts.memory = echarts.init(document.getElementById('chart-memory'));
        this.charts.network = echarts.init(document.getElementById('chart-network'));
        this.charts.diskIo = echarts.init(document.getElementById('chart-disk-io'));
        this.charts.load = echarts.init(document.getElementById('chart-load'));
        this.charts.cores = echarts.init(document.getElementById('chart-cores'));

        this._initCpuChart();
        this._initMemoryChart();
        this._initNetworkChart();
        this._initDiskIoChart();
        this._initLoadChart();
        this._initCoresChart();
    }

    _makeSeries(name, color, gradTop, gradBot) {
        return {
            name,
            type: 'line',
            smooth: true,
            symbol: 'none',
            lineStyle: { width: 2, color },
            areaStyle: {
                color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                    { offset: 0, color: gradTop },
                    { offset: 1, color: gradBot },
                ]),
            },
            data: [],
        };
    }

    _initCpuChart() {
        const opt = JSON.parse(JSON.stringify(baseChartOption));
        opt.series = [this._makeSeries('CPU', COLORS.cpu, COLORS.cpuGradientTop, COLORS.cpuGradientBot)];
        opt.tooltip.formatter = (params) => {
            const p = params[0];
            return `${p.axisValue}<br/><span style="color:${COLORS.cpu}">● CPU</span> <b>${p.value}%</b>`;
        };
        this.charts.cpu.setOption(opt);
    }

    _initMemoryChart() {
        const opt = JSON.parse(JSON.stringify(baseChartOption));
        opt.series = [
            this._makeSeries('Memory', COLORS.memory, COLORS.memGradientTop, COLORS.memGradientBot),
            this._makeSeries('Swap', COLORS.swap, COLORS.swapGradientTop, COLORS.swapGradientBot),
        ];
        opt.tooltip.formatter = (params) => {
            let html = params[0].axisValue;
            params.forEach(p => {
                html += `<br/><span style="color:${p.color}">● ${p.seriesName}</span> <b>${p.value}%</b>`;
            });
            return html;
        };
        this.charts.memory.setOption(opt);
    }

    _initNetworkChart() {
        const opt = JSON.parse(JSON.stringify(baseChartOption));
        opt.yAxis.max = null;
        opt.yAxis.axisLabel.formatter = (v) => Utils.formatRate(v);
        opt.series = [
            this._makeSeries('Download', COLORS.netRx, COLORS.netRxGradientTop, COLORS.netRxGradientBot),
            this._makeSeries('Upload', COLORS.netTx, COLORS.netTxGradientTop, COLORS.netTxGradientBot),
        ];
        opt.tooltip.formatter = (params) => {
            let html = params[0].axisValue;
            params.forEach(p => {
                html += `<br/><span style="color:${p.color}">● ${p.seriesName}</span> <b>${Utils.formatRate(p.value)}</b>`;
            });
            return html;
        };
        this.charts.network.setOption(opt);
    }

    _initDiskIoChart() {
        const opt = JSON.parse(JSON.stringify(baseChartOption));
        opt.yAxis.max = null;
        opt.yAxis.axisLabel.formatter = (v) => Utils.formatRate(v);
        opt.series = [
            this._makeSeries('Read', COLORS.diskRead, COLORS.diskReadGradientTop, COLORS.diskReadGradientBot),
            this._makeSeries('Write', COLORS.diskWrite, COLORS.diskWriteGradientTop, COLORS.diskWriteGradientBot),
        ];
        opt.tooltip.formatter = (params) => {
            let html = params[0].axisValue;
            params.forEach(p => {
                html += `<br/><span style="color:${p.color}">● ${p.seriesName}</span> <b>${Utils.formatRate(p.value)}</b>`;
            });
            return html;
        };
        this.charts.diskIo.setOption(opt);
    }

    _initLoadChart() {
        const opt = JSON.parse(JSON.stringify(baseChartOption));
        opt.yAxis.max = null;
        opt.yAxis.axisLabel.formatter = '{value}';
        opt.series = [
            { name: '1m', type: 'line', smooth: true, symbol: 'none', lineStyle: { width: 2, color: COLORS.load1 }, data: [] },
            { name: '5m', type: 'line', smooth: true, symbol: 'none', lineStyle: { width: 2, color: COLORS.load5, type: 'dashed' }, data: [] },
            { name: '15m', type: 'line', smooth: true, symbol: 'none', lineStyle: { width: 1, color: COLORS.load15, type: 'dotted' }, data: [] },
        ];
        opt.tooltip.formatter = (params) => {
            let html = params[0].axisValue;
            params.forEach(p => {
                html += `<br/><span style="color:${p.color}">● ${p.seriesName}</span> <b>${p.value}</b>`;
            });
            return html;
        };
        this.charts.load.setOption(opt);
    }

    _initCoresChart() {
        const opt = JSON.parse(JSON.stringify(baseChartOption));
        opt.series = [];
        opt.grid.right = 60;
        opt.legend = {
            show: true,
            right: 0,
            top: 'middle',
            orient: 'vertical',
            textStyle: { color: 'rgba(255,255,255,0.5)', fontSize: 10 },
            itemWidth: 10, itemHeight: 6,
        };
        this.charts.cores.setOption(opt);
    }

    /**
     * Update charts with new fast metrics data.
     */
    updateFastMetrics(data) {
        const time = Utils.formatChartTime(data.timestamp);

        // Push time label
        this.timeLabels.push(time);
        if (this.timeLabels.length > MAX_POINTS) this.timeLabels.shift();

        // CPU
        this.cpuHistory.push(data.cpu.total);
        if (this.cpuHistory.length > MAX_POINTS) this.cpuHistory.shift();

        // Memory & Swap
        this.memHistory.push(data.memory.percent);
        if (this.memHistory.length > MAX_POINTS) this.memHistory.shift();
        this.swapHistory.push(data.swap.percent);
        if (this.swapHistory.length > MAX_POINTS) this.swapHistory.shift();

        // Network - aggregate all interfaces
        let totalRx = 0, totalTx = 0;
        if (data.network) {
            Object.values(data.network).forEach(iface => {
                totalRx += iface.rx_rate || 0;
                totalTx += iface.tx_rate || 0;
            });
        }
        this.netRxHistory.push(totalRx);
        this.netTxHistory.push(totalTx);
        if (this.netRxHistory.length > MAX_POINTS) this.netRxHistory.shift();
        if (this.netTxHistory.length > MAX_POINTS) this.netTxHistory.shift();

        // Disk IO
        this.diskReadHistory.push(data.disk_io?.read_rate || 0);
        this.diskWriteHistory.push(data.disk_io?.write_rate || 0);
        if (this.diskReadHistory.length > MAX_POINTS) this.diskReadHistory.shift();
        if (this.diskWriteHistory.length > MAX_POINTS) this.diskWriteHistory.shift();

        // Load
        const la = data.cpu.load_avg || [0, 0, 0];
        this.loadHistory.l1.push(la[0]);
        this.loadHistory.l5.push(la[1]);
        this.loadHistory.l15.push(la[2]);
        if (this.loadHistory.l1.length > MAX_POINTS) { this.loadHistory.l1.shift(); this.loadHistory.l5.shift(); this.loadHistory.l15.shift(); }

        // Per-core
        const cores = data.cpu.cores || [];
        while (this.coreHistories.length < cores.length) {
            this.coreHistories.push([]);
        }
        cores.forEach((val, i) => {
            this.coreHistories[i].push(val);
            if (this.coreHistories[i].length > MAX_POINTS) this.coreHistories[i].shift();
        });

        // Batch update all charts
        this._updateCpuChart();
        this._updateMemoryChart();
        this._updateNetworkChart();
        this._updateDiskIoChart();
        this._updateLoadChart();
        this._updateCoresChart(cores.length);
    }

    _updateCpuChart() {
        this.charts.cpu.setOption({
            xAxis: { data: this.timeLabels },
            series: [{ data: this.cpuHistory }],
        });
    }

    _updateMemoryChart() {
        this.charts.memory.setOption({
            xAxis: { data: this.timeLabels },
            series: [{ data: this.memHistory }, { data: this.swapHistory }],
        });
    }

    _updateNetworkChart() {
        this.charts.network.setOption({
            xAxis: { data: this.timeLabels },
            series: [{ data: this.netRxHistory }, { data: this.netTxHistory }],
        });
    }

    _updateDiskIoChart() {
        this.charts.diskIo.setOption({
            xAxis: { data: this.timeLabels },
            series: [{ data: this.diskReadHistory }, { data: this.diskWriteHistory }],
        });
    }

    _updateLoadChart() {
        this.charts.load.setOption({
            xAxis: { data: this.timeLabels },
            series: [
                { data: this.loadHistory.l1 },
                { data: this.loadHistory.l5 },
                { data: this.loadHistory.l15 },
            ],
        });
    }

    _updateCoresChart(coreCount) {
        if (!this._coresInitialized || this._lastCoreCount !== coreCount) {
            const series = [];
            for (let i = 0; i < coreCount; i++) {
                series.push({
                    name: `Core ${i}`,
                    type: 'line',
                    smooth: true,
                    symbol: 'none',
                    lineStyle: { width: 1.5, color: COLORS.coreColors[i % COLORS.coreColors.length] },
                    data: this.coreHistories[i] || [],
                });
            }
            this.charts.cores.setOption({ xAxis: { data: this.timeLabels }, series }, true);
            this._coresInitialized = true;
            this._lastCoreCount = coreCount;
        } else {
            const seriesUpdate = this.coreHistories.slice(0, coreCount).map(h => ({ data: h }));
            this.charts.cores.setOption({ xAxis: { data: this.timeLabels }, series: seriesUpdate });
        }
    }

    /**
     * Load historical data to pre-fill charts.
     */
    loadHistory(historyData) {
        if (!historyData || historyData.length === 0) return;

        historyData.forEach(entry => {
            const data = entry.data;
            const time = Utils.formatChartTime(entry.timestamp);

            this.timeLabels.push(time);
            this.cpuHistory.push(data.cpu?.total || 0);
            this.memHistory.push(data.memory?.percent || 0);
            this.swapHistory.push(data.swap?.percent || 0);

            let totalRx = 0, totalTx = 0;
            if (data.network) {
                Object.values(data.network).forEach(iface => {
                    totalRx += iface.rx_rate || 0;
                    totalTx += iface.tx_rate || 0;
                });
            }
            this.netRxHistory.push(totalRx);
            this.netTxHistory.push(totalTx);

            this.diskReadHistory.push(data.disk_io?.read_rate || 0);
            this.diskWriteHistory.push(data.disk_io?.write_rate || 0);

            const la = data.cpu?.load_avg || [0, 0, 0];
            this.loadHistory.l1.push(la[0]);
            this.loadHistory.l5.push(la[1]);
            this.loadHistory.l15.push(la[2]);

            const cores = data.cpu?.cores || [];
            while (this.coreHistories.length < cores.length) this.coreHistories.push([]);
            cores.forEach((val, i) => this.coreHistories[i].push(val));
        });

        // Trim to MAX_POINTS
        const trim = (arr) => { while (arr.length > MAX_POINTS) arr.shift(); };
        trim(this.timeLabels); trim(this.cpuHistory); trim(this.memHistory);
        trim(this.swapHistory); trim(this.netRxHistory); trim(this.netTxHistory);
        trim(this.diskReadHistory); trim(this.diskWriteHistory);
        trim(this.loadHistory.l1); trim(this.loadHistory.l5); trim(this.loadHistory.l15);
        this.coreHistories.forEach(trim);

        // Update all charts
        this._updateCpuChart();
        this._updateMemoryChart();
        this._updateNetworkChart();
        this._updateDiskIoChart();
        this._updateLoadChart();
        if (this.coreHistories.length > 0) this._updateCoresChart(this.coreHistories.length);
    }

    resizeAll() {
        Object.values(this.charts).forEach(c => c && c.resize());
    }
}
