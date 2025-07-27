// --- START OF FILE static/js/background-manager.js (FIXED) ---

class BackgroundManager {
    constructor() {
        this.elements = {
            overlay: document.getElementById('background-overlay'),
            modal: document.getElementById('backgroundModal'),
            openBtn: document.getElementById('backgroundSettingsBtn'),
            closeBtn: document.getElementById('closeBackgroundModal'),
            selectImageBtn: document.getElementById('selectBgImageBtn'),
            imageInput: document.getElementById('bgImageInput'),
            saveBtn: document.getElementById('saveBgSettingsBtn'),
            resetBtn: document.getElementById('resetBgBtn'),
            blurSlider: document.getElementById('bgBlur'),
            saturationSlider: document.getElementById('bgSaturation'),
            brightnessSlider: document.getElementById('bgBrightness'),
            blurValue: document.getElementById('bgBlurValue'),
            saturationValue: document.getElementById('bgSaturationValue'),
            brightnessValue: document.getElementById('bgBrightnessValue'),
            snackbar: document.getElementById('snackbar'),
            snackbarMessage: document.getElementById('snackbarMessage'),
        };
        
        this.currentImagePath = '';
        this.initialize();
    }

    initialize() {
        if (!this.elements.modal) return;

        this.loadSettings();
        this.addEventListeners();
    }

    addEventListeners() {
        this.elements.openBtn.addEventListener('click', () => this.openModal());
        this.elements.closeBtn.addEventListener('click', () => this.closeModal());
        this.elements.modal.addEventListener('click', (e) => {
            if (e.target === this.elements.modal) {
                this.closeModal();
            }
        });

        this.elements.selectImageBtn.addEventListener('click', () => this.elements.imageInput.click());
        this.elements.imageInput.addEventListener('change', (e) => this.handleFileSelect(e));
        
        this.elements.saveBtn.addEventListener('click', () => this.saveSettings());
        this.elements.resetBtn.addEventListener('click', () => this.resetToDefaults());

        this.elements.blurSlider.addEventListener('input', () => this.updatePreview());
        this.elements.saturationSlider.addEventListener('input', () => this.updatePreview());
        this.elements.brightnessSlider.addEventListener('input', () => this.updatePreview());
    }

    async loadSettings() {
        try {
            const response = await fetch('/api/config/detailed');
            if (!response.ok) throw new Error('Failed to load config');
            const data = await response.json();

            if (data.success) {
                const config = data.config;
                this.currentImagePath = config.background_image_path || '';
                
                this.elements.blurSlider.value = config.background_blur || 0;
                this.elements.saturationSlider.value = config.background_saturation || 100;
                this.elements.brightnessSlider.value = config.background_brightness || 100;

                this.applyStyles();
            }
        } catch (error) {
            console.error('Error loading background settings:', error);
            this.showSnackbar('加载背景设置失败', 'error');
        }
    }

    // **** 这是主要修复点 ****
    applyStyles() {
        const blur = this.elements.blurSlider.value;
        const saturation = this.elements.saturationSlider.value;
        const brightness = this.elements.brightnessSlider.value;

        // 更新滑块旁边的数值显示
        this.elements.blurValue.textContent = `${blur}px`;
        this.elements.saturationValue.textContent = `${saturation}%`;
        this.elements.brightnessValue.textContent = `${brightness}%`;

        if (this.currentImagePath) {
            // 如果有图片路径，则设置背景图片和滤镜
            this.elements.overlay.style.backgroundImage = `url('/${this.currentImagePath}?v=${new Date().getTime()}')`;
            const filterValue = `blur(${blur}px) saturate(${saturation}%) brightness(${brightness}%)`;
            this.elements.overlay.style.filter = filterValue;
            // backdrop-filter 是可选的，但效果更好
            this.elements.overlay.style.backdropFilter = filterValue;
        } else {
            // 如果没有图片路径（即默认状态），则移除背景和所有滤镜
            this.elements.overlay.style.backgroundImage = 'none';
            this.elements.overlay.style.filter = 'none';
            this.elements.overlay.style.backdropFilter = 'none';
        }
    }

    updatePreview() {
        const blur = this.elements.blurSlider.value;
        const saturation = this.elements.saturationSlider.value;
        const brightness = this.elements.brightnessSlider.value;

        this.elements.blurValue.textContent = `${blur}px`;
        this.elements.saturationValue.textContent = `${saturation}%`;
        this.elements.brightnessValue.textContent = `${brightness}%`;

        // 在实时预览时，我们总是应用滤镜
        const filterValue = `blur(${blur}px) saturate(${saturation}%) brightness(${brightness}%)`;
        this.elements.overlay.style.filter = filterValue;
        this.elements.overlay.style.backdropFilter = filterValue;
    }
    // **** 修复结束 ****

    async handleFileSelect(event) {
        const file = event.target.files[0];
        if (!file) return;

        const formData = new FormData();
        formData.append('backgroundFile', file);

        try {
            const response = await fetch('/api/upload_background', {
                method: 'POST',
                body: formData,
            });
            const data = await response.json();
            if (data.success) {
                this.currentImagePath = data.path;
                this.applyStyles();
                this.showSnackbar('图片上传成功！', 'success');
            } else {
                throw new Error(data.message);
            }
        } catch (error) {
            console.error('Error uploading file:', error);
            this.showSnackbar(`上传失败: ${error.message}`, 'error');
        }
    }
    
    async saveSettings() {
        const settings = {
            background_image_path: this.currentImagePath,
            background_blur: parseInt(this.elements.blurSlider.value, 10),
            background_saturation: parseInt(this.elements.saturationSlider.value, 10),
            background_brightness: parseInt(this.elements.brightnessSlider.value, 10),
        };

        try {
            const response = await fetch('/api/config/update', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(settings)
            });
            const data = await response.json();

            if (data.success) {
                this.showSnackbar('背景设置已保存', 'success');
                this.closeModal();
            } else {
                throw new Error(data.message);
            }
        } catch (error) {
            console.error('Error saving settings:', error);
            this.showSnackbar(`保存失败: ${error.message}`, 'error');
        }
    }

    async resetToDefaults() {
        if (!confirm('您确定要移除自定义背景并重置所有效果吗？')) return;

        this.currentImagePath = '';
        this.elements.blurSlider.value = 0;
        this.elements.saturationSlider.value = 100;
        this.elements.brightnessSlider.value = 80;
        
        this.applyStyles();
        await this.saveSettings();
    }

    openModal() {
        this.elements.modal.style.display = 'flex';
        setTimeout(() => this.elements.modal.classList.add('show'), 10);
    }

    closeModal() {
        this.elements.modal.classList.remove('show');
        setTimeout(() => {
            this.elements.modal.style.display = 'none';
            // 关闭时重新加载设置，以撤销任何未保存的更改
            this.loadSettings();
        }, 300);
    }

    showSnackbar(message, type = 'info') {
        const sb = this.elements.snackbar;
        const msg = this.elements.snackbarMessage;
        if (!sb || !msg) return;
        msg.textContent = message;
        sb.className = `snackbar show ${type}`;
        setTimeout(() => sb.classList.remove('show'), 4000);
    }
}

document.addEventListener('DOMContentLoaded', () => {
    new BackgroundManager();
});