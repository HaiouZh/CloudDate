/**
 * CloudDate — Utility Functions
 * Formatting, conversion, and helper utilities.
 */

const Utils = {
    /**
     * Format bytes to human readable string.
     */
    formatBytes(bytes, decimals = 1) {
        if (bytes === 0 || bytes == null) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(Math.abs(bytes)) / Math.log(k));
        const idx = Math.min(i, sizes.length - 1);
        return (bytes / Math.pow(k, idx)).toFixed(decimals) + ' ' + sizes[idx];
    },

    /**
     * Format bytes per second to human readable rate string.
     */
    formatRate(bytesPerSec) {
        if (bytesPerSec === 0 || bytesPerSec == null) return '0 B/s';
        const k = 1024;
        const sizes = ['B/s', 'KB/s', 'MB/s', 'GB/s'];
        const i = Math.floor(Math.log(Math.abs(bytesPerSec)) / Math.log(k));
        const idx = Math.min(i, sizes.length - 1);
        return (bytesPerSec / Math.pow(k, idx)).toFixed(1) + ' ' + sizes[idx];
    },

    /**
     * Format seconds to human readable uptime string.
     */
    formatUptime(seconds) {
        if (!seconds || seconds < 0) return '0s';
        const d = Math.floor(seconds / 86400);
        const h = Math.floor((seconds % 86400) / 3600);
        const m = Math.floor((seconds % 3600) / 60);
        const s = Math.floor(seconds % 60);

        const parts = [];
        if (d > 0) parts.push(`${d}d`);
        if (h > 0) parts.push(`${h}h`);
        if (m > 0) parts.push(`${m}m`);
        if (parts.length === 0) parts.push(`${s}s`);
        return parts.join(' ');
    },

    /**
     * Format timestamp to HH:MM:SS.
     */
    formatTime(timestamp) {
        const d = new Date(timestamp * 1000);
        return d.toLocaleTimeString('en-US', { hour12: false });
    },

    /**
     * Format timestamp to short time for chart axis.
     */
    formatChartTime(timestamp) {
        const d = new Date(timestamp * 1000);
        const h = String(d.getHours()).padStart(2, '0');
        const m = String(d.getMinutes()).padStart(2, '0');
        const s = String(d.getSeconds()).padStart(2, '0');
        return `${h}:${m}:${s}`;
    },

    /**
     * Get color for a percentage value (green → yellow → red).
     */
    getPercentColor(pct) {
        if (pct >= 90) return '#ff4757';
        if (pct >= 70) return '#ffa502';
        if (pct >= 50) return '#ffdd59';
        return '#2ed573';
    },

    /**
     * Lerp between two colors based on percentage.
     */
    lerpColor(pct) {
        const hue = ((100 - pct) * 1.2);  // 120=green, 0=red
        return `hsl(${hue}, 80%, 55%)`;
    },

    /**
     * Get Docker status badge color.
     */
    getDockerStatusColor(status) {
        switch (status) {
            case 'running': return '#2ed573';
            case 'paused': return '#ffa502';
            case 'exited': return '#ff4757';
            case 'restarting': return '#5352ed';
            default: return '#747d8c';
        }
    },

    /**
     * Parse Docker created time to relative string.
     */
    formatDockerCreated(created) {
        if (!created) return 'unknown';
        try {
            const d = new Date(created);
            const now = new Date();
            const diff = (now - d) / 1000;
            return this.formatUptime(diff);
        } catch {
            return created;
        }
    },

    /**
     * Debounce a function.
     */
    debounce(fn, delay) {
        let timer;
        return (...args) => {
            clearTimeout(timer);
            timer = setTimeout(() => fn(...args), delay);
        };
    },

    /**
     * Generate a smooth gradient for ECharts area charts.
     */
    areaGradient(echarts, colorTop, colorBottom) {
        return new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: colorTop },
            { offset: 1, color: colorBottom },
        ]);
    }
};
