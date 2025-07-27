// --- START OF FILE static/js/settings.js (FINAL VERSION) ---
class SettingsManager {
    constructor() {
        this.elements = {
            githubToken: document.getElementById('githubToken'),
            steamPath: document.getElementById('steamPath'),
            steamPathStatus: document.getElementById('steamPathStatus'),
            debugMode: document.getElementById('debugMode'),
            loggingFiles: document.getElementById('loggingFiles'),
            saveBtn: document.getElementById('saveConfig'),
            resetBtn: document.getElementById('resetConfig'),
            snackbar: document.getElementById('snackbar'),
            snackbarMessage: document.getElementById('snackbarMessage'),
            snackbarClose: document.getElementById('snackbarClose'),
            toggleTokenBtn: document.getElementById('toggleTokenBtn'),
            tokenVisibilityIcon: document.getElementById('tokenVisibilityIcon'),
            toggleConsoleBtn: document.getElementById('toggleConsoleBtn'),
            // 新增: 启动时显示控制台的复选框
            showConsoleOnStartup: document.getElementById('showConsoleOnStartup'),
            // **** 新增: 强制解锁工具的单选框 ****
            forceUnlockerRadios: document.querySelectorAll('input[name="forceUnlocker"]'),
        };
        this.initialize();
    }

    initialize() {
        this.loadConfig();
        this.elements.saveBtn.addEventListener('click', () => this.saveConfig());
        this.elements.resetBtn.addEventListener('click', () => this.resetConfig());
        this.elements.snackbarClose.addEventListener('click', () => this.hideSnackbar());
        this.elements.steamPath.addEventListener('input', () => this.validateSteamPath(false));
        this.elements.toggleTokenBtn.addEventListener('click', () => this.toggleTokenVisibility());
        
        if (this.elements.toggleConsoleBtn) {
            this.elements.toggleConsoleBtn.addEventListener('click', () => this.toggleConsole());
        }
    }

    async toggleConsole() {
        try {
            const response = await fetch('/api/console/toggle', { method: 'POST' });
            const data = await response.json();
            this.showSnackbar(data.message, data.success ? 'success' : 'error');
        } catch (error) {
            this.showSnackbar(`请求切换控制台时出错: ${error.message}`, 'error');
        }
    }

    toggleTokenVisibility() {
        const tokenInput = this.elements.githubToken;
        const icon = this.elements.tokenVisibilityIcon;

        if (tokenInput.type === 'password') {
            tokenInput.type = 'text';
            icon.textContent = 'visibility_off';
            tokenInput.classList.add('token-visible');
        } else {
            tokenInput.type = 'password';
            icon.textContent = 'visibility';
            tokenInput.classList.remove('token-visible');
        }
    }
    
    validateSteamPath(isAuto) {
        const path = this.elements.steamPath.value.trim();
        const statusEl = this.elements.steamPathStatus;
        const iconEl = statusEl.querySelector('.status-icon');
        const textEl = statusEl.querySelector('.status-text');

        if (!path) {
            statusEl.style.display = 'none';
            return;
        }

        statusEl.style.display = 'flex';

        if (isAuto) {
            statusEl.className = 'status-indicator success';
            iconEl.textContent = 'check_circle';
            textEl.textContent = '已自动识别Steam路径';
        } else {
            if (path.toLowerCase().includes('steam')) {
                statusEl.className = 'status-indicator success';
                iconEl.textContent = 'task_alt';
                textEl.textContent = '看起来路径正确';
            } else {
                statusEl.className = 'status-indicator warning';
                iconEl.textContent = 'warning';
                textEl.textContent = '路径可能不正确，请确认';
            }
        }
    }

    async loadConfig() {
        try {
            const response = await fetch('/api/config/detailed');
            if (!response.ok) throw new Error(`Server responded with ${response.status}`);
            const data = await response.json();
            if (data.success) {
                this.elements.githubToken.value = data.config.github_token || '';
                this.elements.steamPath.value = data.config.steam_path || '';
                this.elements.debugMode.checked = data.config.debug_mode || false;
                this.elements.loggingFiles.checked = data.config.logging_files !== false;
                this.elements.showConsoleOnStartup.checked = data.config.show_console_on_startup || false;

                // **** 新增: 加载强制解锁工具设置 ****
                const forceUnlockerValue = data.config.force_unlocker_type || 'auto';
                this.elements.forceUnlockerRadios.forEach(radio => {
                    radio.checked = radio.value === forceUnlockerValue;
                });
                // **********************************

                this.validateSteamPath(data.config.steam_path_is_auto || false);
            } else {
                this.showSnackbar(`加载配置失败: ${data.message}`, 'error');
            }
        } catch (error) {
            this.showSnackbar(`连接服务器时出错: ${error.message}`, 'error');
        }
    }

    async saveConfig() {
        // **** 新增: 获取强制解锁工具设置 ****
        const selectedUnlockerRadio = document.querySelector('input[name="forceUnlocker"]:checked');
        const forceUnlockerValue = selectedUnlockerRadio ? selectedUnlockerRadio.value : 'auto';
        // **********************************

        const config = {
            github_token: this.elements.githubToken.value.trim(),
            steam_path: this.elements.steamPath.value.trim(),
            debug_mode: this.elements.debugMode.checked,
            logging_files: this.elements.loggingFiles.checked,
            show_console_on_startup: this.elements.showConsoleOnStartup.checked,
            // **** 新增: 保存新选项的状态 ****
            force_unlocker_type: forceUnlockerValue,
        };

        try {
            const response = await fetch('/api/config/update', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(config),
            });
            if (!response.ok) throw new Error(`Server responded with ${response.status}`);
            const data = await response.json();
            if (data.success) {
                await this.loadConfig();
            }
            this.showSnackbar(data.message, data.success ? 'success' : 'error');
        } catch (error) {
            this.showSnackbar(`保存配置时出错: ${error.message}`, 'error');
        }
    }

    async resetConfig() {
        if (!confirm('您确定要将所有设置重置为默认值吗？此操作不可恢复。')) {
            return;
        }
        try {
            const response = await fetch('/api/config/reset', { method: 'POST' });
            if (!response.ok) throw new Error(`Server responded with ${response.status}`);
            const data = await response.json();
            if (data.success) {
                this.loadConfig();
            }
            this.showSnackbar(data.message, data.success ? 'success' : 'error');
        } catch (error) {
            this.showSnackbar(`重置配置时出错: ${error.message}`, 'error');
        }
    }
    
    showSnackbar(message, type = 'info') {
        this.elements.snackbarMessage.textContent = message;
        this.elements.snackbar.className = `snackbar ${type} show`;
        if (this.snackbarTimeout) clearTimeout(this.snackbarTimeout);
        this.snackbarTimeout = setTimeout(() => this.hideSnackbar(), 4000);
    }

    hideSnackbar() {
        this.elements.snackbar.classList.remove('show');
    }
}

document.addEventListener('DOMContentLoaded', () => {
    new SettingsManager();
});