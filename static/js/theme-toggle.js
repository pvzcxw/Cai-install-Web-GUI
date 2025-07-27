// --- START OF FILE static/js/theme-toggle.js (MODIFIED for Shutdown) ---
document.addEventListener('DOMContentLoaded', () => {
    const themeToggleBtn = document.getElementById('themeToggleBtn');
    const shutdownBtn = document.getElementById('shutdownBtn');

    // --- Theme Toggle Logic ---
    if (themeToggleBtn) {
        const body = document.body;
        const themeKey = 'cai-install-theme-preference';
        const icon = themeToggleBtn.querySelector('.material-icons');

        const updateIcon = (theme) => {
            if (theme === 'dark') {
                icon.textContent = 'light_mode';
                themeToggleBtn.setAttribute('title', '切换到亮色模式');
            } else {
                icon.textContent = 'dark_mode';
                themeToggleBtn.setAttribute('title', '切换到暗色模式');
            }
        };

        const applyTheme = (theme) => {
            if (theme === 'dark') {
                body.classList.add('dark-theme');
            } else {
                body.classList.remove('dark-theme');
            }
            updateIcon(theme);
        };

        const currentTheme = localStorage.getItem(themeKey) || 'light';
        applyTheme(currentTheme);

        themeToggleBtn.addEventListener('click', () => {
            const isDark = body.classList.toggle('dark-theme');
            const newTheme = isDark ? 'dark' : 'light';
            
            localStorage.setItem(themeKey, newTheme);
            updateIcon(newTheme);
        });
    }

    // --- Shutdown Logic ---
    if (shutdownBtn) {
        shutdownBtn.addEventListener('click', () => {
            if (confirm('您确定要关闭应用吗？这将同时关闭网页和后台程序。')) {
                // Inform the user
                document.body.innerHTML = `
                    <div style="display:flex; flex-direction:column; justify-content:center; align-items:center; height:100vh; font-family:sans-serif; background-color:#1c1b1f; color:#e6e1e5;">
                        <h1>正在关闭应用...</h1>
                        <p>您可以安全地关闭此浏览器标签页。</p>
                    </div>`;

                // Send shutdown request to the server
                fetch('/api/shutdown', { method: 'POST' })
                    .catch(error => {
                        console.error('无法连接到服务器以执行关闭命令:', error);
                        // Even if fetch fails (e.g., server is already down), the user experience is maintained.
                    });
            }
        });
    }
});