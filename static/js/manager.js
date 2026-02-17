class FileManagerApp {
    constructor() {
        this.elements = {
            loadingOverlay: document.getElementById('loadingOverlay'),
            gridContainer: document.getElementById('fileGrid'),
            noResultsMessage: document.getElementById('noResultsMessage'),
            tabButtons: document.querySelectorAll('.tab-button'),
            searchInput: document.getElementById('searchInput'),
            refreshBtn: document.getElementById('refreshBtn'),
            deleteBtn: document.getElementById('deleteBtn'),
            selectAllCheckbox: document.getElementById('selectAllCheckbox'),
            statusText: document.getElementById('statusText'),
            shutdownBtn: document.getElementById('shutdownBtn'),
            snackbar: document.getElementById('snackbar'),
            snackbarMessage: document.getElementById('snackbarMessage'),
            snackbarClose: document.getElementById('snackbarClose'),
            contextMenu: document.getElementById('contextMenu'),
            advancedBtn: document.getElementById('advancedBtn'),
            advancedMenu: document.getElementById('advancedMenu'),
            editorModal: document.getElementById('editorModal'),
            closeEditorModal: document.getElementById('closeEditorModal'),
            editorTitle: document.getElementById('editorTitle'),
            editorTextarea: document.getElementById('editorTextarea'),
            saveEditorBtn: document.getElementById('saveEditorBtn'),
            editorStatus: document.getElementById('editorStatus'),
        };
        this.fullData = {};
        this.currentTab = 'st';
        this.currentItemForEditor = null;
        this.initialize();
    }

    initialize() {
        this.elements.tabButtons.forEach(btn => btn.addEventListener('click', () => this.switchTab(btn.dataset.tab)));
        this.elements.refreshBtn.addEventListener('click', () => this.fetchFiles());
        this.elements.deleteBtn.addEventListener('click', () => this.deleteSelected());
        this.elements.searchInput.addEventListener('input', () => this.filterGrid());
        this.elements.selectAllCheckbox.addEventListener('change', () => this.toggleSelectAll());
        this.elements.gridContainer.addEventListener('change', e => e.target.classList.contains('card-checkbox') && this.updateSelectionState());
        this.elements.shutdownBtn.addEventListener('click', this.shutdown);
        this.elements.snackbarClose.addEventListener('click', () => this.hideSnackbar());

        // Advanced Menu
        this.elements.advancedBtn.addEventListener('click', e => {
            e.stopPropagation();
            this.elements.advancedMenu.style.display = this.elements.advancedMenu.style.display === 'block' ? 'none' : 'block';
        });
        document.getElementById('forceUnlockAdd').addEventListener('click', () => this.handleForceUnlock('add'));
        document.getElementById('forceUnlockRemove').addEventListener('click', () => this.handleForceUnlock('remove'));
        document.getElementById('openStFolder').addEventListener('click', () => this.openFolder('st'));
        document.getElementById('openGlFolder').addEventListener('click', () => this.openFolder('gl'));

        // Context Menu
        this.elements.gridContainer.addEventListener('contextmenu', e => this.showContextMenu(e));
        
        // Editor Modal
        this.elements.closeEditorModal.addEventListener('click', () => this.hideEditor());
        this.elements.saveEditorBtn.addEventListener('click', () => this.saveFile());

        // Global click listener to hide menus
        window.addEventListener('click', (e) => {
            if (!this.elements.advancedBtn.contains(e.target) && !this.elements.advancedMenu.contains(e.target)) {
                this.elements.advancedMenu.style.display = 'none';
            }
            if (this.elements.contextMenu && !this.elements.contextMenu.contains(e.target)) {
                this.elements.contextMenu.style.display = 'none';
                this.elements.gridContainer.querySelectorAll('.game-card.context-selected').forEach(card => card.classList.remove('context-selected'));
            }
        });

        this.fetchFiles();
    }

    setLoading(isLoading) {
        this.elements.loadingOverlay.classList.toggle('visible', isLoading);
    }

    async fetchFiles() {
        this.setLoading(true);
        this.elements.statusText.textContent = '正在从服务器获取文件列表...';
        try {
            const response = await fetch('/api/manager/files');
            if (!response.ok) throw new Error(`服务器响应错误: ${response.status}`);
            const result = await response.json();
            if (result.success) {
                this.fullData = result.data;
                this.renderGrid();
                this.showSnackbar('文件列表已刷新', 'success');
            } else {
                throw new Error(result.message || '获取文件失败');
            }
        } catch (error) {
            this.showSnackbar(error.message, 'error');
            this.elements.statusText.textContent = `错误: ${error.message}`;
        } finally {
            this.setLoading(false);
        }
    }

    switchTab(tab) {
        this.currentTab = tab;
        this.elements.tabButtons.forEach(btn => btn.classList.toggle('active', btn.dataset.tab === tab));
        this.renderGrid();
    }

    renderGrid() {
        const data = this.fullData[this.currentTab] || [];
        const searchTerm = this.elements.searchInput.value.toLowerCase();
        
        const statusMap = {
            ok: { text: '已入库', class: 'ok' },
            unlocked_only: { text: '仅解锁', class: 'unlocked_only' },
            core_file: { text: '核心文件', class: 'core_file' }
        };

        const filteredData = data.filter(item => 
            (item.filename?.toLowerCase() || '').includes(searchTerm) ||
            (item.appid?.toLowerCase() || '').includes(searchTerm) ||
            (item.game_name?.toLowerCase() || '').includes(searchTerm)
        );

        if (filteredData.length === 0) {
            const message = data.length === 0 ? '此类别下没有文件。' : '没有匹配搜索结果。';
            this.elements.noResultsMessage.textContent = message;
            this.elements.noResultsMessage.style.display = 'block';
            this.elements.gridContainer.innerHTML = '';
        } else {
            this.elements.noResultsMessage.style.display = 'none';
            const html = filteredData.map(item => {
                const statusInfo = statusMap[item.status] || { text: '未知', class: '' };
                const isCoreFile = item.status === 'core_file';
                const hasValidAppID = item.appid && /^\d+$/.test(item.appid);
                const imageUrl = hasValidAppID ? `https://cdn.akamai.steamstatic.com/steam/apps/${item.appid}/header.jpg` : '';
                
                const imageHtml = hasValidAppID 
                    ? `<img src="${imageUrl}" alt="${item.game_name || 'Game Cover'}" loading="lazy" onerror="this.parentElement.innerHTML = '<div class=\\'placeholder\\'><span class=\\'material-icons\\'>hide_image</span></div>';">`
                    : `<div class="placeholder"><span class="material-icons">image</span></div>`;

                return `
                    <div class="game-card" data-item='${JSON.stringify(item)}'>
                        <input type="checkbox" class="card-checkbox" ${isCoreFile ? 'disabled' : ''} title="选择此项">
                        <div class="game-card-header" ${hasValidAppID ? `onclick="window.open('steam://run/${item.appid}')"` : ''} title="启动/安装游戏">
                            ${imageHtml}
                        </div>
                        <div class="game-card-body">
                            <span class="status-badge ${statusInfo.class}">${statusInfo.text}</span>
                            <span class="game-title" title="${item.game_name || 'N/A'}">${item.game_name || 'N/A'}</span>
                            <span class="game-appid">APPID: ${item.appid || 'N/A'}</span>
                            <div class="game-card-actions">
                                <button class="btn btn-icon context-menu-trigger" title="更多操作">
                                    <span class="material-icons">more_vert</span>
                                </button>
                            </div>
                        </div>
                    </div>
                `;
            }).join('');
            this.elements.gridContainer.innerHTML = html;
            
            // Add event listeners for the 'more' button to trigger context menu
            this.elements.gridContainer.querySelectorAll('.context-menu-trigger').forEach(btn => {
                btn.addEventListener('click', e => {
                    e.stopPropagation(); // Prevent card click event
                    const card = e.target.closest('.game-card');
                    const rect = btn.getBoundingClientRect();
                    const mockEvent = new MouseEvent('contextmenu', {
                        bubbles: true, cancelable: true, view: window,
                        clientX: rect.left, clientY: rect.bottom
                    });
                    card.dispatchEvent(mockEvent);
                });
            });
        }
        this.updateSelectionState();
    }


    filterGrid() { this.renderGrid(); }
    
    toggleSelectAll() {
        const isChecked = this.elements.selectAllCheckbox.checked;
        this.elements.gridContainer.querySelectorAll('.card-checkbox:not(:disabled)').forEach(cb => cb.checked = isChecked);
        this.updateSelectionState();
    }
    
    updateSelectionState() {
        const allCheckboxes = this.elements.gridContainer.querySelectorAll('.card-checkbox:not(:disabled)');
        const checkedCheckboxes = this.elements.gridContainer.querySelectorAll('.card-checkbox:checked');
        
        // Update card selected visual state
        this.elements.gridContainer.querySelectorAll('.game-card').forEach(card => {
            const cb = card.querySelector('.card-checkbox');
            if (cb) card.classList.toggle('selected', cb.checked);
        });

        this.elements.deleteBtn.disabled = checkedCheckboxes.length === 0;

        if(checkedCheckboxes.length > 0){
            this.elements.deleteBtn.querySelector('.material-icons').textContent = `delete_sweep`;
            this.elements.deleteBtn.childNodes[2].textContent = ` 删除 (${checkedCheckboxes.length}) 项`;
        } else {
            this.elements.deleteBtn.querySelector('.material-icons').textContent = `delete`;
            this.elements.deleteBtn.childNodes[2].textContent = ` 删除选中`;
        }
        
        this.elements.selectAllCheckbox.checked = allCheckboxes.length > 0 && checkedCheckboxes.length === allCheckboxes.length;
        this.elements.statusText.textContent = `选中 ${checkedCheckboxes.length} / ${allCheckboxes.length} 项`;
    }

    async deleteSelected(items = null) {
        const isSingleDelete = items !== null;
        const itemsToDelete = isSingleDelete ? items : Array.from(this.elements.gridContainer.querySelectorAll('.card-checkbox:checked'))
            .map(cb => JSON.parse(cb.closest('.game-card').dataset.item));

        if (itemsToDelete.length === 0) return;

        if (!confirm(`确定要删除选中的 ${itemsToDelete.length} 个条目吗？\n此操作不可恢复，并将移除相关文件和解锁条目。`)) {
            return;
        }
        
        this.setLoading(true);
        this.elements.statusText.textContent = `正在删除 ${itemsToDelete.length} 个条目...`;
        
        try {
            const response = await fetch('/api/manager/delete', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ type: this.currentTab, items: itemsToDelete })
            });
            const result = await response.json();
            this.showSnackbar(result.message, result.success ? 'success' : 'error');
            await this.fetchFiles();
        } catch (error) {
            this.showSnackbar(`删除失败: ${error.message}`, 'error');
            this.setLoading(false);
        }
    }

    // --- New/Restored Functionality ---

    async openFolder(folderType) {
        try {
            const response = await fetch('/api/manager/open_folder', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ type: folderType })
            });
            const result = await response.json();
            this.showSnackbar(result.message, result.success ? 'info' : 'error');
        } catch (error) { this.showSnackbar(`打开目录失败: ${error.message}`, 'error'); }
    }

    async handleForceUnlock(action) {
        const promptText = action === 'add' ? '请输入要强制解锁的AppID:' : '请输入要移除解锁的AppID:';
        const appid = prompt(promptText);
        if (!appid || !/^\d+$/.test(appid)) {
            if (appid !== null) alert('请输入有效的数字AppID。');
            return;
        }
        // This is a placeholder for the actual API call.
        this.showSnackbar(`正在为AppID ${appid} 执行 '${action}' 操作... (API待实现)`, 'info');
    }

    showContextMenu(e) {
        e.preventDefault();
        const targetCard = e.target.closest('.game-card');
        if (!targetCard || !targetCard.dataset.item) return;

        // Highlight the clicked card for context
        this.elements.gridContainer.querySelectorAll('.game-card.context-selected').forEach(row => row.classList.remove('context-selected'));
        targetCard.classList.add('context-selected');

        const item = JSON.parse(targetCard.dataset.item);
        const menu = this.elements.contextMenu;
        menu.innerHTML = this.buildContextMenuHTML(item);
        menu.style.display = 'block';
        
        // Position the menu
        const menuWidth = menu.offsetWidth;
        const menuHeight = menu.offsetHeight;
        const windowWidth = window.innerWidth;
        const windowHeight = window.innerHeight;
        
        let x = e.clientX;
        let y = e.clientY;
        
        if (x + menuWidth > windowWidth) x -= menuWidth;
        if (y + menuHeight > windowHeight) y -= menuHeight;
        
        menu.style.left = `${x}px`;
        menu.style.top = `${y}px`;

        // Add event listeners to the new menu items
        menu.querySelectorAll('.context-menu-item').forEach(menuItem => {
            if (!menuItem.classList.contains('disabled')) {
                menuItem.addEventListener('click', (event) => {
                    const action = event.currentTarget.dataset.action;
                    if(action) this.handleContextMenuAction(action, item);
                    menu.style.display = 'none';
                });
            }
        });
    }

    buildContextMenuHTML(item) {
        const hasFile = item.filename && !item.filename.includes('缺少');
        const hasAppID = item.appid && /^\d+$/.test(item.appid);
        const isCore = item.status === 'core_file';

        let html = '';
        html += `<div class="context-menu-item ${!hasAppID && 'disabled'}" data-action="run"><span class="material-icons">play_circle</span>运行/安装游戏</div>`;
        html += `<div class="context-menu-item ${!hasFile && 'disabled'}" data-action="edit"><span class="material-icons">edit</span>编辑文件 (${item.filename})</div>`;
        html += `<div class="context-menu-item" data-action="copy_appid"><span class="material-icons">content_copy</span>复制 AppID</div>`;
        html += '<div class="dropdown-divider"></div>';
        html += `<div class="context-menu-item ${isCore && 'disabled'}" data-action="delete"><span class="material-icons">delete</span>删除此条目</div>`;
        return html;
    }

    handleContextMenuAction(action, item) {
        switch (action) {
            case 'run':
                if (item.appid && /^\d+$/.test(item.appid)) window.open(`steam://run/${item.appid}`);
                break;
            case 'edit':
                this.showEditor(item);
                break;
            case 'delete':
                this.deleteSelected([item]);
                break;
            case 'copy_appid':
                navigator.clipboard.writeText(item.appid).then(() => {
                    this.showSnackbar(`AppID ${item.appid} 已复制到剪贴板`, 'success');
                });
                break;
        }
    }
    
    // --- Editor Methods ---
    async showEditor(item) {
        if (!item || !item.filename || item.filename.includes('缺少')) return;
        this.currentItemForEditor = item;
        this.elements.editorTitle.textContent = `编辑 - ${item.filename}`;
        this.elements.editorTextarea.value = '正在加载文件内容...';
        this.elements.editorTextarea.disabled = true;
        this.elements.saveEditorBtn.disabled = true;
        this.elements.editorModal.classList.add('show');

        // Fetch file content (API endpoint to be created in backend)
        this.showSnackbar('编辑功能需要后端支持来读取和保存文件内容。', 'warning');
        this.elements.editorTextarea.value = `// 后端API 'GET /api/manager/file_content' 尚待实现。\n// 后端API 'POST /api/manager/file_content' 尚待实现。`;

        /* 
        // NOTE: The following code requires backend implementation.
        try {
            const response = await fetch(`/api/manager/file_content?type=${this.currentTab}&filename=${encodeURIComponent(item.filename)}`);
            if (!response.ok) throw new Error('无法加载文件。');
            const data = await response.json();
            if(data.success) {
                this.elements.editorTextarea.value = data.content;
                this.elements.editorTextarea.disabled = false;
                this.elements.saveEditorBtn.disabled = false;
                this.elements.editorStatus.textContent = `${data.content.length} 字符`;
            } else {
                throw new Error(data.message);
            }
        } catch(e) {
            this.elements.editorTextarea.value = `加载失败: ${e.message}`;
            this.elements.editorStatus.textContent = '加载失败';
        }
        */
    }

    hideEditor() {
        this.elements.editorModal.classList.remove('show');
        this.currentItemForEditor = null;
    }

    async saveFile() {
        if (!this.currentItemForEditor) return;
        
        const content = this.elements.editorTextarea.value;
        this.elements.saveEditorBtn.disabled = true;
        this.elements.saveEditorBtn.innerHTML = `<span class="material-icons spin">hourglass_top</span> 保存中...`;
        
        // NOTE: This requires backend implementation
        this.showSnackbar('保存功能需要后端API支持。', 'warning');

        /*
        try {
            const response = await fetch('/api/manager/file_content', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    type: this.currentTab,
                    filename: this.currentItemForEditor.filename,
                    content: content
                })
            });
            const result = await response.json();
            this.showSnackbar(result.message, result.success ? 'success' : 'error');
            if (result.success) {
                this.hideEditor();
            }
        } catch (e) {
            this.showSnackbar(`保存失败: ${e.message}`, 'error');
        } finally {
            this.elements.saveEditorBtn.disabled = false;
            this.elements.saveEditorBtn.innerHTML = `<span class="material-icons">save</span> 保存`;
        }
        */
       
        // Mockup behaviour
        setTimeout(() => {
             this.elements.saveEditorBtn.disabled = false;
             this.elements.saveEditorBtn.innerHTML = `<span class="material-icons">save</span> 保存`;
             this.hideEditor();
        }, 1000);
    }

    // --- Snackbar and Shutdown ---
    showSnackbar(message, type = 'info') {
        this.elements.snackbarMessage.textContent = message;
        this.elements.snackbar.className = `snackbar show ${type}`;
        clearTimeout(this.snackbarTimeout);
        this.snackbarTimeout = setTimeout(() => this.hideSnackbar(), 5000);
    }
    hideSnackbar() { this.elements.snackbar.classList.remove('show'); }
    async shutdown() {
        if (!confirm('确定要关闭Cai Install Web GUI吗？')) return;
        try {
            const response = await fetch('/api/shutdown', { method: 'POST' });
            const data = await response.json();
            if (data.success) {
                document.body.innerHTML = "<h1>正在关闭，您可以安全地关闭此窗口...</h1>";
                setTimeout(() => window.close(), 1500);
            }
        } catch (error) { alert('请求关闭失败，请手动关闭程序。'); }
    }
}

document.addEventListener('DOMContentLoaded', () => {
    new FileManagerApp();
});