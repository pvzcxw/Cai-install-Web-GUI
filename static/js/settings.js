// --- START OF FILE static/js/settings.js (MODIFIED WITH CUSTOM REPOS AND AUTO-UPDATE) ---
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
            showConsoleOnStartup: document.getElementById('showConsoleOnStartup'),
            forceUnlockerRadios: document.querySelectorAll('input[name="forceUnlocker"]'),
            // NEW: 自定义清单库相关元素
            checkUpdatesBtn: document.getElementById('checkUpdatesBtn'),
            addGithubRepoBtn: document.getElementById('addGithubRepoBtn'),
            addZipRepoBtn: document.getElementById('addZipRepoBtn'),
            githubReposList: document.getElementById('githubReposList'),
            zipReposList: document.getElementById('zipReposList'),
            // 模态框元素
            addRepoModal: document.getElementById('addRepoModal'),
            repoModalTitle: document.getElementById('repoModalTitle'),
            repoName: document.getElementById('repoName'),
            repoPath: document.getElementById('repoPath'),
            repoUrl: document.getElementById('repoUrl'),
            repoPathGroup: document.getElementById('repoPathGroup'),
            repoUrlGroup: document.getElementById('repoUrlGroup'),
            cancelRepoBtn: document.getElementById('cancelRepoBtn'),
            saveRepoBtn: document.getElementById('saveRepoBtn'),
            // 更新相关模态框
            updateModal: document.getElementById('updateModal'),
            updateInfo: document.getElementById('updateInfo'),
            updateChangelog: document.getElementById('updateChangelog'),
            downloadUpdateBtn: document.getElementById('downloadUpdateBtn'),
            laterUpdateBtn: document.getElementById('laterUpdateBtn'),
            ignoreUpdateBtn: document.getElementById('ignoreUpdateBtn'),
        };
        
        this.currentRepoType = 'github'; // 'github' or 'zip'
        this.customRepos = { github: [], zip: [] };
        
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

        // NEW: 自定义清单库事件监听器
        this.elements.checkUpdatesBtn.addEventListener('click', () => this.checkForUpdates());
        this.elements.addGithubRepoBtn.addEventListener('click', () => this.showAddRepoModal('github'));
        this.elements.addZipRepoBtn.addEventListener('click', () => this.showAddRepoModal('zip'));
        
        // 模态框事件监听器
        this.elements.saveRepoBtn.addEventListener('click', () => this.saveRepo());
        this.elements.cancelRepoBtn.addEventListener('click', () => this.hideAddRepoModal());
        
        // 更新模态框事件监听器
        this.elements.laterUpdateBtn.addEventListener('click', () => this.hideUpdateModal());
        this.elements.downloadUpdateBtn.addEventListener('click', () => this.downloadUpdate());
        this.elements.ignoreUpdateBtn.addEventListener('click', () => this.ignoreUpdate());
        
        // 点击模态框背景关闭
        this.elements.addRepoModal.addEventListener('click', (e) => {
            if (e.target === this.elements.addRepoModal) this.hideAddRepoModal();
        });
        this.elements.updateModal.addEventListener('click', (e) => {
            if (e.target === this.elements.updateModal) this.hideUpdateModal();
        });
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

    // NEW: 检查更新功能
    async checkForUpdates() {
        const btn = this.elements.checkUpdatesBtn;
        const originalContent = btn.innerHTML;
        
        btn.disabled = true;
        btn.innerHTML = '<span class="material-icons spin">hourglass_top</span> 检查中...';
        
        try {
            const response = await fetch('/api/check_updates', { method: 'POST' });
            const data = await response.json();
            
            if (data.success) {
                if (data.has_update) {
                    this.showUpdateModal(data.update_info);
                } else {
                    this.showSnackbar('当前已是最新版本！', 'success');
                }
            } else {
                this.showSnackbar(`检查更新失败: ${data.message}`, 'error');
            }
        } catch (error) {
            this.showSnackbar(`检查更新时出错: ${error.message}`, 'error');
        } finally {
            setTimeout(() => {
                btn.disabled = false;
                btn.innerHTML = originalContent;
            }, 1000);
        }
    }

    // NEW: 显示更新模态框
    showUpdateModal(updateInfo) {
        // 生成更新信息
        const infoHtml = `
            <div class="update-info-item">
                <span class="update-info-label">当前版本:</span>
                <span class="update-info-value version">${updateInfo.current_version}</span>
            </div>
            <div class="update-info-item">
                <span class="update-info-label">最新版本:</span>
                <span class="update-info-value version">${updateInfo.latest_version}</span>
            </div>
            <div class="update-info-item">
                <span class="update-info-label">发布时间:</span>
                <span class="update-info-value">${new Date(updateInfo.published_at).toLocaleString('zh-CN')}</span>
            </div>
        `;
        this.elements.updateInfo.innerHTML = infoHtml;
        
        // 生成更新日志
        this.elements.updateChangelog.textContent = updateInfo.release_body || '暂无更新日志';
        
        // 保存更新信息到模态框
        this.elements.updateModal.dataset.updateUrl = updateInfo.release_url;
        this.elements.updateModal.dataset.latestVersion = updateInfo.latest_version;
        
        this.elements.updateModal.classList.add('show');
    }

    hideUpdateModal() {
        this.elements.updateModal.classList.remove('show');
    }

    downloadUpdate() {
        const updateUrl = this.elements.updateModal.dataset.updateUrl;
        if (updateUrl) {
            window.open(updateUrl, '_blank');
            this.hideUpdateModal();
        }
    }

    ignoreUpdate() {
        const latestVersion = this.elements.updateModal.dataset.latestVersion;
        if (latestVersion) {
            // 这里可以保存忽略的版本信息到本地存储
            localStorage.setItem('ignoredVersion', latestVersion);
            this.showSnackbar(`已忽略版本 ${latestVersion}`, 'info');
        }
        this.hideUpdateModal();
    }

    // NEW: 显示添加仓库模态框
    showAddRepoModal(type) {
        this.currentRepoType = type;
        
        if (type === 'github') {
            this.elements.repoModalTitle.textContent = '添加GitHub仓库';
            this.elements.repoPathGroup.style.display = 'block';
            this.elements.repoUrlGroup.style.display = 'none';
            this.elements.repoPath.placeholder = '例如：username/repository';
        } else {
            this.elements.repoModalTitle.textContent = '添加ZIP清单库';
            this.elements.repoPathGroup.style.display = 'none';
            this.elements.repoUrlGroup.style.display = 'block';
            this.elements.repoUrl.placeholder = '例如：https://example.com/download/{app_id}.zip';
        }
        
        // 清空表单
        this.elements.repoName.value = '';
        this.elements.repoPath.value = '';
        this.elements.repoUrl.value = '';
        
        this.elements.addRepoModal.classList.add('show');
        this.elements.repoName.focus();
    }

    hideAddRepoModal() {
        this.elements.addRepoModal.classList.remove('show');
    }

    // NEW: 保存仓库
    saveRepo() {
        const name = this.elements.repoName.value.trim();
        
        if (!name) {
            this.showSnackbar('请输入显示名称', 'error');
            return;
        }
        
        let repoData;
        if (this.currentRepoType === 'github') {
            const path = this.elements.repoPath.value.trim();
            if (!path) {
                this.showSnackbar('请输入仓库路径', 'error');
                return;
            }
            if (!path.includes('/')) {
                this.showSnackbar('GitHub仓库路径格式应为：用户名/仓库名', 'error');
                return;
            }
            repoData = { name, repo: path };
        } else {
            const url = this.elements.repoUrl.value.trim();
            if (!url) {
                this.showSnackbar('请输入下载URL', 'error');
                return;
            }
            if (!url.includes('{app_id}')) {
                this.showSnackbar('URL必须包含{app_id}占位符', 'error');
                return;
            }
            repoData = { name, url };
        }
        
        // 检查是否重复
        const existingRepos = this.customRepos[this.currentRepoType];
        const isDuplicate = existingRepos.some(repo => 
            repo.name === name || 
            (this.currentRepoType === 'github' && repo.repo === repoData.repo) ||
            (this.currentRepoType === 'zip' && repo.url === repoData.url)
        );
        
        if (isDuplicate) {
            this.showSnackbar('仓库已存在', 'error');
            return;
        }
        
        // 添加到列表
        this.customRepos[this.currentRepoType].push(repoData);
        this.renderReposList();
        this.hideAddRepoModal();
        this.showSnackbar(`成功添加${this.currentRepoType === 'github' ? 'GitHub仓库' : 'ZIP清单库'}`, 'success');
        
        // FIXED: 添加保存配置调用
        this.saveConfig().then(() => {
            console.log('自定义仓库配置已保存到服务器');
        }).catch(error => {
            console.error('保存自定义仓库配置失败:', error);
            this.showSnackbar('保存配置失败，请重试', 'error');
        });
    }

    // NEW: 删除仓库
    removeRepo(type, index) {
        if (confirm('确定要删除这个仓库吗？')) {
            this.customRepos[type].splice(index, 1);
            this.renderReposList();
            this.showSnackbar('仓库已删除', 'success');
            
            // FIXED: 添加保存配置调用
            this.saveConfig().then(() => {
                console.log('删除仓库后配置已保存到服务器');
            }).catch(error => {
                console.error('保存删除仓库配置失败:', error);
                this.showSnackbar('保存配置失败，请重试', 'error');
            });
        }
    }

    // NEW: 渲染仓库列表
    renderReposList() {
        // 渲染GitHub仓库列表
        this.renderReposListByType('github', this.elements.githubReposList);
        // 渲染ZIP仓库列表
        this.renderReposListByType('zip', this.elements.zipReposList);
    }

    renderReposListByType(type, container) {
        const repos = this.customRepos[type];
        
        if (repos.length === 0) {
            container.innerHTML = `
                <div class="empty-repos">
                    <span class="material-icons">folder_open</span>
                    <p>暂无${type === 'github' ? 'GitHub仓库' : 'ZIP清单库'}</p>
                </div>
            `;
            return;
        }
        
        container.innerHTML = repos.map((repo, index) => `
            <div class="repo-item" data-repo-type="${type}" data-repo-index="${index}">
                <div class="repo-info">
                    <div class="repo-name">${repo.name}</div>
                    <div class="repo-path">${type === 'github' ? repo.repo : repo.url}</div>
                </div>
                <div class="repo-actions">
                    <button class="btn-icon repo-delete-btn" title="删除">
                        <span class="material-icons">delete</span>
                    </button>
                </div>
            </div>
        `).join('');

        // FIXED: 为每个删除按钮添加事件监听器，而不是使用onclick属性
        container.querySelectorAll('.repo-delete-btn').forEach((btn) => {
            btn.addEventListener('click', (event) => {
                event.stopPropagation(); // 防止事件冒泡
                
                // 从按钮的父级元素获取数据属性
                const repoItem = btn.closest('.repo-item');
                const repoType = repoItem.dataset.repoType;
                const repoIndex = parseInt(repoItem.dataset.repoIndex, 10);
                
                console.log(`删除仓库: ${repoType}[${repoIndex}]`);
                this.removeRepo(repoType, repoIndex);
            });
        });
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

                // 加载强制解锁工具设置
                const forceUnlockerValue = data.config.force_unlocker_type || 'auto';
                this.elements.forceUnlockerRadios.forEach(radio => {
                    radio.checked = radio.value === forceUnlockerValue;
                });

                // NEW: 加载自定义清单库配置
                this.customRepos = data.config.custom_repos || { github: [], zip: [] };
                this.renderReposList();

                this.validateSteamPath(data.config.steam_path_is_auto || false);
            } else {
                this.showSnackbar(`加载配置失败: ${data.message}`, 'error');
            }
        } catch (error) {
            this.showSnackbar(`连接服务器时出错: ${error.message}`, 'error');
        }
    }

    async saveConfig() {
        // 获取强制解锁工具设置
        const selectedUnlockerRadio = document.querySelector('input[name="forceUnlocker"]:checked');
        const forceUnlockerValue = selectedUnlockerRadio ? selectedUnlockerRadio.value : 'auto';

        const config = {
            github_token: this.elements.githubToken.value.trim(),
            steam_path: this.elements.steamPath.value.trim(),
            debug_mode: this.elements.debugMode.checked,
            logging_files: this.elements.loggingFiles.checked,
            show_console_on_startup: this.elements.showConsoleOnStartup.checked,
            force_unlocker_type: forceUnlockerValue,
            // NEW: 保存自定义清单库配置
            custom_repos: this.customRepos,
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

// 创建全局实例以便在HTML中调用
let settingsManager;

document.addEventListener('DOMContentLoaded', () => {
    settingsManager = new SettingsManager();
});