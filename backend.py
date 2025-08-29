# --- START OF FILE backend.py (MODIFIED WITH AUTO-UPDATE AND CUSTOM REPOS) ---

import sys
import os
import traceback
import time
import logging
import subprocess
import asyncio
import re
import aiofiles
import colorlog
import httpx
import winreg
import ujson as json
import vdf
import zipfile
import shutil
import struct
import zlib
import io  # For workshop manifest processing
from pathlib import Path
from typing import Tuple, Any, List, Dict, Literal
from urllib.parse import quote

CURRENT_VERSION = "1.6"  # 当前版本号
GITHUB_REPO = "pvzcxw/Cai-install-Web-GUI" 

# --- LOGGING SETUP ---
LOG_FORMAT = '%(log_color)s%(message)s'
LOG_COLORS = {
    'INFO': 'cyan',
    'WARNING': 'yellow',
    'ERROR': 'red',
    'CRITICAL': 'purple',
}

# --- MODIFIED: Added Custom_Repos setting ---
DEFAULT_CONFIG = {
    "Github_Personal_Token": "",
    "Custom_Steam_Path": "",
    "debug_mode": False,
    "logging_files": True,
    "background_image_path": "",
    "background_blur": 0,
    "background_saturation": 100,
    "background_brightness": 80, 
    "show_console_on_startup": False,
    "force_unlocker_type": "auto",
    "Custom_Repos": {
        "github": [],
        "zip": []
    },
    "QA1": "温馨提示: Github_Personal_Token(个人访问令牌)可在Github设置的最底下开发者选项中找到, 详情请看教程。",
    "QA2": "Force_Unlocker: 强制指定解锁工具, 填入 'steamtools' 或 'greenluma'。留空则自动检测。",
    "QA3": "Custom_Repos: 自定义清单库配置。github数组用于添加GitHub仓库，zip数组用于添加ZIP清单库。",
    "QA4": "GitHub仓库格式: {\"name\": \"显示名称\", \"repo\": \"用户名/仓库名\"}",
    "QA5": "ZIP清单库格式: {\"name\": \"显示名称\", \"url\": \"下载URL，用{app_id}作为占位符\"}"
}

class STConverter:
    def __init__(self):
        self.logger = logging.getLogger('STConverter')

    def convert_file(self, st_path: str) -> str:
        try:
            content, _ = self.parse_st_file(st_path)
            return content
        except Exception as e:
            self.logger.error(f'ST文件转换失败: {st_path} - {e}')
            raise

    def parse_st_file(self, st_file_path: str) -> Tuple[str, dict]:
        with open(st_file_path, 'rb') as stfile:
            content = stfile.read()
        if len(content) < 12: raise ValueError("文件头过短")
        header = content[:12]
        xorkey, size, xorkeyverify = struct.unpack('III', header)
        xorkey ^= 0xFFFEA4C8
        xorkey &= 0xFF
        encrypted_data = content[12:12+size]
        if len(encrypted_data) < size: raise ValueError("加密数据小于预期大小")
        data = bytearray(encrypted_data)
        for i in range(len(data)):
            data[i] ^= xorkey
        decompressed_data = zlib.decompress(data)
        lua_content = decompressed_data[512:].decode('utf-8')
        metadata = {'original_xorkey': xorkey, 'size': size, 'xorkeyverify': xorkeyverify}
        return lua_content, metadata

class CaiBackend:
    def __init__(self):
        if getattr(sys, 'frozen', False):
            self.project_root = Path(sys.executable).parent
        elif hasattr(sys, '__nuitka_binary_dir__'):
            self.project_root = Path(sys.__nuitka_binary_dir__)
        else:
            self.project_root = Path(__file__).parent
        self.client: httpx.AsyncClient | None = None
        self.config = {}
        self.steam_path = None
        self.unlocker_type = None
        self.lock = asyncio.Lock()
        self.temp_path = self.project_root / 'temp'
        self.log = self._init_log()

    async def __aenter__(self):
        self.client = httpx.AsyncClient(verify=False, trust_env=True)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.client:
            await self.client.aclose()

    def _init_log(self, level=logging.INFO) -> logging.Logger:
        logger = logging.getLogger(' Cai install')
        logger.setLevel(level)
        if not logger.handlers:
            stream_handler = colorlog.StreamHandler()
            stream_handler.setLevel(level)
            fmt = colorlog.ColoredFormatter(LOG_FORMAT, log_colors=LOG_COLORS)
            stream_handler.setFormatter(fmt)
            logger.addHandler(stream_handler)
        return logger

    def _configure_logger(self):
        if not self.config:
            self.log.warning("无法应用日志配置，因为配置尚未加载。")
            return
        is_debug = self.config.get("debug_mode", False)
        level = logging.DEBUG if is_debug else logging.INFO
        self.log.setLevel(level)
        for handler in self.log.handlers:
            if isinstance(handler, logging.StreamHandler):
                handler.setLevel(level)
        self.log.debug(f"日志等级已设置为: {'DEBUG' if is_debug else 'INFO'}")
        self.log.handlers = [h for h in self.log.handlers if not isinstance(h, logging.FileHandler)]
        if self.config.get("logging_files", True):
            logs_dir = self.project_root / 'logs'
            logs_dir.mkdir(exist_ok=True)
            log_file_path = logs_dir / f'cai-install-gui-{time.strftime("%Y-%m-%d")}.log'
            file_handler = logging.FileHandler(log_file_path, 'a', encoding='utf-8')
            file_handler.setLevel(level)
            file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
            file_handler.setFormatter(file_formatter)
            self.log.addHandler(file_handler)
            self.log.info(f"已启用文件日志，将保存到: {log_file_path}")
        else:
            self.log.info("文件日志已禁用。")

    def _compare_versions(self, v1: str, v2: str) -> int:
        """比较版本号，返回 -1, 0, 1"""
        try:
            import re
            
            def parse_version(v):
                # 分离主版本号和后缀
                match = re.match(r'(\d+(?:\.\d+)*)(.*)', v)
                if not match:
                    return (0, 0, 0), ''
                
                version_nums = match.group(1)
                suffix = match.group(2)
                
                # 解析版本号
                parts = version_nums.split('.')
                # 填充到3位
                while len(parts) < 3:
                    parts.append('0')
                
                # 转换为整数元组
                version_tuple = tuple(int(p) for p in parts[:3])
                
                return version_tuple, suffix
            
            v1_tuple, v1_suffix = parse_version(v1)
            v2_tuple, v2_suffix = parse_version(v2)
            
            # 首先比较主版本号
            if v1_tuple < v2_tuple:
                return -1
            elif v1_tuple > v2_tuple:
                return 1
            
            # 版本号相同，比较后缀
            # 空后缀被认为是正式版本，高于带后缀的版本
            if not v1_suffix and v2_suffix:
                return 1
            elif v1_suffix and not v2_suffix:
                return -1
            elif v1_suffix < v2_suffix:
                return -1
            elif v1_suffix > v2_suffix:
                return 1
            
            return 0
            
        except Exception as e:
            self.log.warning(f"版本比较失败: {e}")
            return 0
    
    async def check_for_updates(self) -> Tuple[bool, Dict]:
        """
        检查是否有新版本可用
        返回: (是否有更新, 版本信息字典)
        """
        try:
            self.log.info("正在检查更新...")
            
            # GitHub API URL
            api_url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
            
            # 获取 GitHub token（如果有的话）
            github_token = self.config.get("Github_Personal_Token", "").strip()
            headers = {'Authorization': f'Bearer {github_token}'} if github_token else {}
            
            # 添加 User-Agent 以避免 API 限制
            headers['User-Agent'] = 'Cai-Install-Updater'
            
            # 发送请求
            response = await self.client.get(api_url, headers=headers, timeout=10)
            
            if response.status_code == 404:
                # 没有发布版本
                self.log.info("未找到发布版本")
                return False, {}
            
            response.raise_for_status()
            release_data = response.json()
            
            # 提取版本信息
            latest_version = release_data.get('tag_name', '').strip()
            if latest_version.startswith('v'):
                latest_version = latest_version[1:]  # 去掉 'v' 前缀
            
            release_name = release_data.get('name', '')
            release_body = release_data.get('body', '')
            release_url = release_data.get('html_url', '')
            published_at = release_data.get('published_at', '')
            
            # 获取下载链接
            download_urls = []
            assets = release_data.get('assets', [])
            for asset in assets:
                download_urls.append({
                    'name': asset.get('name', ''),
                    'url': asset.get('browser_download_url', ''),
                    'size': asset.get('size', 0)
                })
            
            # 如果没有 assets，使用 zipball_url
            if not download_urls and release_data.get('zipball_url'):
                download_urls.append({
                    'name': 'Source code (zip)',
                    'url': release_data.get('zipball_url', ''),
                    'size': 0
                })
            
            # 比较版本
            if self._compare_versions(CURRENT_VERSION, latest_version) < 0:
                self.log.info(f"发现新版本: {latest_version} (当前版本: {CURRENT_VERSION})")
                return True, {
                    'current_version': CURRENT_VERSION,
                    'latest_version': latest_version,
                    'release_name': release_name,
                    'release_body': release_body,
                    'release_url': release_url,
                    'published_at': published_at,
                    'download_urls': download_urls
                }
            else:
                self.log.info(f"当前已是最新版本 ({CURRENT_VERSION})")
                return False, {}
                
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 403:
                self.log.warning("GitHub API 请求次数已用尽，跳过更新检查")
            else:
                self.log.warning(f"检查更新时 HTTP 错误: {e}")
            return False, {}
        except httpx.TimeoutException:
            self.log.warning("检查更新超时，跳过")
            return False, {}
        except Exception as e:
            self.log.warning(f"检查更新失败: {e}")
            return False, {}

    async def initialize(self) -> Literal["steamtools", "greenluma", "conflict", "none", None]:
        self.config = await self.load_config()
        if self.config is None: return None
        self._configure_logger()
        
        self.steam_path = self.get_steam_path()
        if not self.steam_path or not self.steam_path.exists():
            self.log.error('无法确定有效的Steam路径。请在设置中手动指定。')
            return None
        self.log.info(f"Steam路径: {self.steam_path}")

        force_unlocker = self.config.get("force_unlocker_type", "auto")

        if force_unlocker in ["steamtools", "greenluma"]:
            self.unlocker_type = force_unlocker
            self.log.warning(f"已根据配置强制使用解锁工具: {force_unlocker.capitalize()}")
        else:
            is_steamtools = (self.steam_path / 'config' / 'stplug-in').is_dir()
            is_greenluma = any((self.steam_path / dll).exists() for dll in ['GreenLuma_2025_x86.dll', 'GreenLuma_2025_x64.dll'])
            if is_steamtools and is_greenluma:
                self.log.error("环境冲突：同时检测到SteamTools和GreenLuma！请在设置中强制指定一个。")
                self.unlocker_type = "conflict"
            elif is_steamtools:
                self.log.info("自动检测到解锁工具: SteamTools")
                self.unlocker_type = "steamtools"
            elif is_greenluma:
                self.log.info("自动检测到解锁工具: GreenLuma")
                self.unlocker_type = "greenluma"
            else:
                self.log.warning("未能自动检测到解锁工具。将默认使用标准模式（可能需要手动配置）。")
                self.unlocker_type = "none"

        try:
            (self.steam_path / 'config' / 'stplug-in').mkdir(parents=True, exist_ok=True)
            (self.steam_path / 'AppList').mkdir(parents=True, exist_ok=True)
            (self.steam_path / 'depotcache').mkdir(parents=True, exist_ok=True)
            # Create config/depotcache for workshop manifests
            (self.steam_path / 'config' / 'depotcache').mkdir(parents=True, exist_ok=True)
        except Exception as e:
            self.log.error(f"创建Steam子目录时失败: {e}")

        return self.unlocker_type

    def stack_error(self, exception: Exception) -> str:
        return ''.join(traceback.format_exception(type(exception), exception, exception.__traceback__))

    async def gen_config_file(self):
        config_path = self.project_root / 'config.json'
        try:
        # 确保目录存在
            config_path.parent.mkdir(exist_ok=True, parents=True)
        
            with open(config_path, mode="w", encoding="utf-8") as f:
                f.write(json.dumps(DEFAULT_CONFIG, indent=2, ensure_ascii=False))
            self.log.info('未识别到config.json，可能为首次启动，已自动生成，若进行配置重启生效')
        except Exception as e:
            self.log.error(f'生成配置文件失败: {self.stack_error(e)}')
    
    async def load_config(self) -> Dict | None:
        config_path = self.project_root / 'config.json'
        if not config_path.exists():
            await self.gen_config_file()
            return DEFAULT_CONFIG

        try:
            async with aiofiles.open(config_path, mode="r", encoding="utf-8") as f:
                # --- MODIFIED: Load config and merge with defaults to handle new keys ---
                user_config = json.loads(await f.read())
                config = DEFAULT_CONFIG.copy()
                config.update(user_config)
                
                # --- NEW: Ensure Custom_Repos structure exists ---
                if 'Custom_Repos' not in config:
                    config['Custom_Repos'] = {"github": [], "zip": []}
                elif not isinstance(config['Custom_Repos'], dict):
                    config['Custom_Repos'] = {"github": [], "zip": []}
                else:
                    if 'github' not in config['Custom_Repos']:
                        config['Custom_Repos']['github'] = []
                    if 'zip' not in config['Custom_Repos']:
                        config['Custom_Repos']['zip'] = []
                
                return config
        except Exception as e:
            self.log.error(f"加载配置文件失败: {self.stack_error(e)}。正在重置配置文件...")
            if config_path.exists(): os.remove(config_path)
            await self.gen_config_file()
            self.log.error("配置文件已损坏并被重置。请重启程序。")
            return None

    def get_steam_path(self) -> Path | None:
        try:
            custom_steam_path = self.config.get("Custom_Steam_Path", "").strip()
            if custom_steam_path:
                self.log.info(f"正使用配置文件中的自定义Steam路径: {custom_steam_path}")
                return Path(custom_steam_path)
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Valve\Steam')
            steam_path, _ = winreg.QueryValueEx(key, 'SteamPath')
            winreg.CloseKey(key)
            return Path(steam_path)
        except Exception:
            self.log.error(f'获取Steam路径失败。请检查Steam是否正确安装，或在config.json中设置Custom_Steam_Path。')
            return None

    # --- NEW: Custom repository support functions ---
    def get_custom_github_repos(self) -> List[Dict]:
        """获取自定义GitHub仓库列表"""
        custom_repos = self.config.get("Custom_Repos", {}).get("github", [])
        validated_repos = []
        
        for repo in custom_repos:
            if isinstance(repo, dict) and 'name' in repo and 'repo' in repo:
                validated_repos.append(repo)
            else:
                self.log.warning(f"无效的自定义GitHub仓库配置: {repo}")
        
        return validated_repos

    def get_custom_zip_repos(self) -> List[Dict]:
        """获取自定义ZIP仓库列表"""
        custom_repos = self.config.get("Custom_Repos", {}).get("zip", [])
        validated_repos = []
        
        for repo in custom_repos:
            if isinstance(repo, dict) and 'name' in repo and 'url' in repo:
                # 验证URL中是否包含{app_id}占位符
                if '{app_id}' in repo['url']:
                    validated_repos.append(repo)
                else:
                    self.log.warning(f"自定义ZIP仓库URL缺少{app_id}占位符: {repo}")
            else:
                self.log.warning(f"无效的自定义ZIP仓库配置: {repo}")
        
        return validated_repos

    async def process_custom_zip_manifest(self, app_id: str, repo_config: Dict, add_all_dlc: bool = False, patch_depot_key: bool = False) -> bool:
        """处理自定义ZIP清单库"""
        repo_name = repo_config.get('name', '未知仓库')
        url_template = repo_config.get('url', '')
        
        # 替换占位符
        download_url = url_template.replace('{app_id}', app_id)
        
        return await self._process_zip_manifest_generic(app_id, download_url, f"自定义ZIP库 ({repo_name})", self.unlocker_type, False, add_all_dlc, patch_depot_key)

    def get_all_github_repos(self) -> List[str]:
        """获取所有GitHub仓库（内置+自定义）"""
        builtin_repos = ['Auiowu/ManifestAutoUpdate', 'SteamAutoCracks/ManifestHub']
        custom_repos = [repo['repo'] for repo in self.get_custom_github_repos()]
        return builtin_repos + custom_repos

    # NEW: HTTP helper function for safe requests with retry mechanism
    async def http_get_safe(self, url: str, timeout: int = 30, max_retries: int = 3, retry_delay: float = 1.0) -> httpx.Response | None:
        """安全的HTTP GET请求，带错误处理和重试机制"""
        last_exception = None
        
        for attempt in range(max_retries):
            try:
                # Use different timeout strategies for different attempts
                current_timeout = timeout if attempt == 0 else min(timeout * (attempt + 1), 60)
                
                response = await self.client.get(url, timeout=current_timeout)
                if response.status_code == 200:
                    if attempt > 0:  # Log successful retry
                        self.log.info(f"HTTP请求在第 {attempt + 1} 次尝试后成功: {url}")
                    return response
                else:
                    self.log.warning(f"HTTP请求失败，状态码: {response.status_code} - {url} (尝试 {attempt + 1}/{max_retries})")
                    if response.status_code in [429, 503, 502, 504]:  # Retry on server errors
                        if attempt < max_retries - 1:
                            await asyncio.sleep(retry_delay * (attempt + 1))
                            continue
                    return None
                    
            except (httpx.ConnectTimeout, httpx.ReadTimeout, httpx.TimeoutException) as e:
                last_exception = e
                self.log.warning(f"HTTP请求超时: {url} (尝试 {attempt + 1}/{max_retries}) - {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay * (attempt + 1))
                    continue
                    
            except (httpx.ConnectError, httpx.RemoteProtocolError) as e:
                last_exception = e
                self.log.warning(f"HTTP连接错误: {url} (尝试 {attempt + 1}/{max_retries}) - {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay * (attempt + 1))
                    continue
                    
            except Exception as e:
                last_exception = e
                self.log.error(f"HTTP请求异常: {url} (尝试 {attempt + 1}/{max_retries}) - {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay * (attempt + 1))
                    continue
                break
        
        self.log.error(f"HTTP请求在 {max_retries} 次尝试后仍然失败: {url} - 最后异常: {last_exception}")
        return None

    # NEW: Updated DLC retrieval function with better error handling
    async def get_dlc_ids_safe(self, appid: str) -> List[str]:
        """安全的DLC ID获取函数，支持多数据源回退"""
        self.log.info(f"正在获取 AppID {appid} 的DLC信息...")
        
        # 先尝试 SteamCMD API
        self.log.debug(f"尝试从 SteamCMD API 获取 AppID {appid} 的DLC...")
        data = await self.http_get_safe(f"https://api.steamcmd.net/v1/info/{appid}", timeout=20, max_retries=2)
        if data:
            try:
                j = data.json()
                info = j.get("data", {}).get(str(appid), {})
                
                # Try multiple fields for DLC information
                dlc_str = info.get("extended", {}).get("listofdlc", "") or info.get("common", {}).get("listofdlc", "")
                
                if dlc_str:
                    dlc_ids = sorted(filter(str.isdigit, map(str.strip, dlc_str.split(","))), key=int)
                    if dlc_ids:
                        self.log.info(f"从 SteamCMD API 成功获取到 {len(dlc_ids)} 个DLC")
                        return dlc_ids
                else:
                    self.log.debug(f"SteamCMD API 中 AppID {appid} 没有DLC信息")
                    
            except Exception as e:
                self.log.warning(f"解析 SteamCMD API 响应失败: {e}")
        else:
            self.log.warning(f"无法从 SteamCMD API 获取 AppID {appid} 的数据")
        
        # 降级：使用官方 API，但增加更多重试和容错
        self.log.debug(f"尝试从 Steam 官方 API 获取 AppID {appid} 的DLC...")
        
        # Try different language parameters
        api_variants = [
            f"https://store.steampowered.com/api/appdetails?appids={appid}&l=schinese",
            f"https://store.steampowered.com/api/appdetails?appids={appid}&l=english",
            f"https://store.steampowered.com/api/appdetails?appids={appid}"
        ]
        
        for api_url in api_variants:
            data = await self.http_get_safe(api_url, timeout=25, max_retries=2, retry_delay=2.0)
            if data:
                try:
                    j = data.json()
                    app_data = j.get(str(appid), {})
                    
                    if app_data.get("success") and "data" in app_data:
                        dlc_list = app_data["data"].get("dlc", [])
                        if dlc_list:
                            dlc_ids = [str(d) for d in dlc_list]
                            self.log.info(f"从 Steam 官方 API 成功获取到 {len(dlc_ids)} 个DLC")
                            return dlc_ids
                    else:
                        self.log.debug(f"Steam 官方 API 响应中 AppID {appid} 的成功标志为false或缺少数据")
                        
                except Exception as e:
                    self.log.warning(f"解析 Steam 官方 API 响应失败 ({api_url}): {e}")
                    continue
            else:
                self.log.debug(f"无法从 Steam 官方 API 获取数据: {api_url}")
        
        self.log.info(f"未找到 AppID {appid} 的DLC信息（已尝试所有数据源）")
        return []

    # NEW: Updated depot retrieval function with better error handling
    async def get_depots_safe(self, appid: str) -> List[Tuple[str, str, int, str]]:
        """安全的Depot获取函数，返回 (depot_id, manifest_id, size, source) 元组列表"""
        self.log.info(f"正在获取 AppID {appid} 的Depot信息...")
        
        # 先尝试 SteamCMD API
        self.log.debug(f"尝试从 SteamCMD API 获取 AppID {appid} 的Depot...")
        data = await self.http_get_safe(f"https://api.steamcmd.net/v1/info/{appid}", timeout=20, max_retries=2)
        if data:
            try:
                j = data.json()
                info = j.get("data", {}).get(str(appid), {})
                depots = info.get("depots", {})
                if depots:
                    out = []
                    for depot_id, depot_info in depots.items():
                        if not isinstance(depot_info, dict):
                            continue
                        manifest_info = depot_info.get("manifests", {}).get("public")
                        if not isinstance(manifest_info, dict):
                            continue
                        manifest_id = manifest_info.get("gid")
                        size = int(manifest_info.get("download", 0))
                        dlc_appid = depot_info.get("dlcappid")
                        source = f"DLC:{dlc_appid}" if dlc_appid else "主游戏"
                        if manifest_id:
                            out.append((depot_id, manifest_id, size, source))
                    if out:
                        self.log.info(f"从 SteamCMD API 成功获取到 {len(out)} 个Depot")
                        return out
                else:
                    self.log.debug(f"SteamCMD API 中 AppID {appid} 没有Depot信息")
            except Exception as e:
                self.log.warning(f"解析 SteamCMD API Depot 信息失败: {e}")
        else:
            self.log.warning(f"无法从 SteamCMD API 获取 AppID {appid} 的Depot数据")
        
        # 降级：使用官方 API，但增加更多重试和容错
        self.log.debug(f"尝试从 Steam 官方 API 获取 AppID {appid} 的Depot...")
        
        # Try different language parameters
        api_variants = [
            f"https://store.steampowered.com/api/appdetails?appids={appid}&l=schinese",
            f"https://store.steampowered.com/api/appdetails?appids={appid}&l=english",
            f"https://store.steampowered.com/api/appdetails?appids={appid}"
        ]
        
        for api_url in api_variants:
            data = await self.http_get_safe(api_url, timeout=25, max_retries=2, retry_delay=2.0)
            if data:
                try:
                    j = data.json()
                    app_data = j.get(str(appid), {})
                    
                    if app_data.get("success") and "data" in app_data:
                        depots = app_data["data"].get("depots", {})
                        out = []
                        for depot_id, depot_info in depots.items():
                            if not isinstance(depot_info, dict):
                                continue
                            manifest_info = depot_info.get("manifests", {}).get("public")
                            if not isinstance(manifest_info, dict):
                                continue
                            manifest_id = manifest_info.get("gid")
                            size = int(manifest_info.get("download", 0))
                            dlc_appid = depot_info.get("dlcappid")
                            source = f"DLC:{dlc_appid}" if dlc_appid else "主游戏"
                            if manifest_id:
                                out.append((depot_id, manifest_id, size, source))
                        if out:
                            self.log.info(f"从 Steam 官方 API 成功获取到 {len(out)} 个Depot")
                            return out
                    else:
                        self.log.debug(f"Steam 官方 API 响应中 AppID {appid} 的成功标志为false或缺少数据")
                        
                except Exception as e:
                    self.log.warning(f"解析 Steam 官方 API Depot 信息失败 ({api_url}): {e}")
                    continue
            else:
                self.log.debug(f"无法从 Steam 官方 API 获取Depot数据: {api_url}")
        
        self.log.info(f"未找到 AppID {appid} 的Depot信息（已尝试所有数据源）")
        return []

    # Workshop-related methods
    def extract_workshop_id(self, input_text: str) -> str | None:
        """Extract workshop ID from URL or direct ID input"""
        input_text = input_text.strip()
        if not input_text:
            return None
        
        # Try to match URL pattern
        url_match = re.search(r"https?://steamcommunity\.com/sharedfiles/filedetails/\?id=(\d+)", input_text)
        if url_match:
            return url_match.group(1)
        
        # If it's just digits, treat as direct ID
        if input_text.isdigit():
            return input_text
        
        return None

    async def get_workshop_depot_info(self, workshop_id: str) -> Tuple[str, str] | Tuple[None, None]:
        """Get depot and manifest info for workshop item"""
        try:
            self.log.info(f"正在查询创意工坊物品 {workshop_id} 的信息...")
            api_url = "https://api.steampowered.com/ISteamRemoteStorage/GetPublishedFileDetails/v1/"
            data = {
                'itemcount': 1,
                'publishedfileids[0]': workshop_id
            }
            
            response = await self.client.post(api_url, data=data, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            details = result['response']['publishedfiledetails'][0]
            
            if int(details.get('result', 0)) != 1:
                self.log.error(f"未找到创意工坊物品 {workshop_id}")
                return None, None
            
            consumer_app_id = details.get('consumer_app_id')
            hcontent_file = details.get('hcontent_file')
            title = details.get('title', '未知标题')
            
            if not consumer_app_id or not hcontent_file:
                self.log.error(f"创意工坊物品 '{title}' 缺少必要信息")
                return None, None
            
            self.log.info(f"获取信息成功: [标题: {title}] [应用ID: {consumer_app_id}] [清单ID: {hcontent_file}]")
            return str(consumer_app_id), str(hcontent_file)
            
        except Exception as e:
            self.log.error(f"获取创意工坊信息失败: {self.stack_error(e)}")
            return None, None

    async def download_workshop_manifest(self, depot_id: str, manifest_id: str) -> bytes | None:
        """Download workshop manifest from reliable source"""
        url = f"https://steamcontent.tnkjmec.com/depot/{depot_id}/manifest/{manifest_id}/5"
        
        try:
            self.log.info(f"正在从可靠源下载清单: {url}")
            
            response = await self.client.get(url, timeout=60)
            response.raise_for_status()
            
            # Load content into memory for processing
            zip_in_memory = io.BytesIO(response.content)
            
            # Check if it's a valid ZIP file
            if not zipfile.is_zipfile(zip_in_memory):
                self.log.error("下载失败：服务器返回的不是有效的ZIP文件。")
                return None
            
            self.log.info("文件为ZIP压缩包，正在智能提取...")
            with zipfile.ZipFile(zip_in_memory, 'r') as zip_ref:
                file_list = zip_ref.namelist()
                
                # Verify there's exactly one file in the ZIP
                if len(file_list) != 1:
                    self.log.error(f"下载失败：ZIP包中的文件数量不是1 (实际为: {len(file_list)})。")
                    self.log.warning(f"包内文件列表: {file_list}")
                    return None
                
                # Extract the single file (the manifest)
                filename_inside_zip = file_list[0]
                self.log.info(f"成功锁定ZIP包内唯一文件: '{filename_inside_zip}'")
                
                manifest_content = zip_ref.read(filename_inside_zip)
                return manifest_content
                
        except Exception as e:
            self.log.error(f"下载创意工坊清单时发生错误: {self.stack_error(e)}")
            return None

    async def process_workshop_item(self, workshop_input: str, copy_to_config: bool = True, copy_to_depot: bool = True) -> bool:
        """Process workshop item and copy manifest to specified directories"""
        workshop_id = self.extract_workshop_id(workshop_input)
        if not workshop_id:
            self.log.error(f"无法从输入中提取有效的创意工坊ID: {workshop_input}")
            return False
        
        # Get depot and manifest info
        depot_id, manifest_id = await self.get_workshop_depot_info(workshop_id)
        if not depot_id or not manifest_id:
            return False
        
        # Download manifest
        manifest_content = await self.download_workshop_manifest(depot_id, manifest_id)
        if not manifest_content:
            return False
        
        # Generate filename
        output_filename = f"{depot_id}_{manifest_id}.manifest"
        
        try:
            # Copy to specified directories
            success_count = 0
            
            if copy_to_config:
                config_depot_path = self.steam_path / 'config' / 'depotcache'
                config_file_path = config_depot_path / output_filename
                async with aiofiles.open(config_file_path, 'wb') as f:
                    await f.write(manifest_content)
                self.log.info(f"清单文件已保存到: {config_file_path}")
                success_count += 1
            
            if copy_to_depot:
                depot_cache_path = self.steam_path / 'depotcache'
                depot_file_path = depot_cache_path / output_filename
                async with aiofiles.open(depot_file_path, 'wb') as f:
                    await f.write(manifest_content)
                self.log.info(f"清单文件已保存到: {depot_file_path}")
                success_count += 1
            
            if success_count > 0:
                self.log.info(f"创意工坊清单 {output_filename} 处理完成。")
                return True
            else:
                self.log.error("未指定任何目标目录。")
                return False
                
        except Exception as e:
            self.log.error(f"保存创意工坊清单文件时出错: {self.stack_error(e)}")
            return False

    # NEW: DepotKey patching methods
    async def download_depotkeys_json(self) -> Dict | None:
        """Download depotkeys.json from SteamAutoCracks repository with mirror support"""
        try:
            self.log.info("正在从 SteamAutoCracks 仓库下载 depotkeys.json...")
            
            # Define multiple mirror URLs
            urls = ["https://raw.githubusercontent.com/SteamAutoCracks/ManifestHub/main/depotkeys.json"]
            
            # Add Chinese mirrors if in China
            if os.environ.get('IS_CN') == 'yes':
                urls = [
                    "https://cdn.jsdmirror.com/gh/SteamAutoCracks/ManifestHub@main/depotkeys.json",
                    "https://raw.gitmirror.com/SteamAutoCracks/ManifestHub/main/depotkeys.json", 
                    "https://raw.dgithub.xyz/SteamAutoCracks/ManifestHub/main/depotkeys.json",
                    "https://gh.akass.cn/SteamAutoCracks/ManifestHub/main/depotkeys.json",
                    "https://raw.githubusercontent.com/SteamAutoCracks/ManifestHub/main/depotkeys.json"
                ]
            
            # Try each URL with retries
            for attempt, url in enumerate(urls, 1):
                try:
                    self.log.info(f"尝试从源 {attempt}/{len(urls)} 下载: {url.split('/')[2]}")
                    
                    # Use shorter timeout for each attempt, with retries
                    for retry in range(2):  # 2 retries per URL
                        try:
                            response = await self.client.get(url, timeout=15)
                            response.raise_for_status()
                            
                            depotkeys_data = response.json()
                            self.log.info(f"成功下载 depotkeys.json，包含 {len(depotkeys_data)} 个条目。(来源: {url.split('/')[2]})")
                            return depotkeys_data
                            
                        except (httpx.ConnectTimeout, httpx.ReadTimeout, httpx.TimeoutException) as timeout_err:
                            if retry == 0:  # First retry
                                self.log.warning(f"连接超时，正在重试... (源: {url.split('/')[2]})")
                                await asyncio.sleep(1)  # Brief delay before retry
                                continue
                            else:
                                raise timeout_err
                        
                except Exception as e:
                    error_msg = str(e)
                    if "timeout" in error_msg.lower() or "ConnectTimeout" in str(type(e)):
                        self.log.warning(f"源 {url.split('/')[2]} 连接超时，尝试下一个源...")
                    else:
                        self.log.warning(f"源 {url.split('/')[2]} 下载失败: {error_msg}")
                    
                    # Don't immediately fail, try next URL
                    if attempt < len(urls):
                        continue
                    else:
                        # This was the last URL, re-raise the exception
                        raise e
            
            # If we get here, all URLs failed
            raise Exception("所有镜像源均不可用")
            
        except Exception as e:
            self.log.error(f"下载 depotkeys.json 失败: {self.stack_error(e)}")
            self.log.error("建议检查网络连接或稍后重试。")
            return None

    async def process_steamautocracks_v2_manifest(self, app_id: str, unlocker_type: str, use_st_auto_update: bool, add_all_dlc: bool = False, patch_depot_key: bool = False) -> bool:
        """处理 SteamAutoCracks/ManifestHub(2) 清单库 - 使用 steamui API 获取 depot 和 manifest 信息"""
        try:
            self.log.info(f'正从 SteamAutoCracks/ManifestHub(2) 处理 AppID {app_id} 的清单...')
            
            # 1. 从 steamui API 获取 depot 和 manifest 信息
            depot_manifest_map = await self._get_depots_and_manifests_from_steamui(app_id)
            if not depot_manifest_map:
                self.log.error(f"未能从 steamui API 获取到 AppID {app_id} 的 depot 信息")
                return False
            
            self.log.info(f"从 steamui API 获取到 {len(depot_manifest_map)} 个 depot 及其 manifest")
            
            # 2. 下载 depotkeys.json（复用现有方法）
            if 'IS_CN' not in os.environ:
                self.log.info("检测网络环境以优化下载源选择...")
                await self.checkcn()
            
            depotkeys_data = await self.download_depotkeys_json()
            if not depotkeys_data:
                self.log.error("无法获取 depotkeys 数据")
                return False
            
            # 3. 匹配 depot 与 depotkey
            valid_depots = {}
            for depot_id in depot_manifest_map.keys():
                if depot_id in depotkeys_data:
                    depotkey = depotkeys_data[depot_id]
                    # 检查 depotkey 是否有效（不为空字符串）
                    if depotkey and str(depotkey).strip():
                        valid_depots[depot_id] = str(depotkey).strip()
                        self.log.info(f"找到 depot {depot_id} 的有效 depotkey: {depotkey}")
                    else:
                        self.log.warning(f"depot {depot_id} 的 depotkey 为空，自动跳过")
                else:
                    self.log.warning(f"未找到 depot {depot_id} 的 depotkey，自动跳过")
            
            if not valid_depots:
                self.log.warning(f"AppID {app_id} 没有找到任何有效的 depot 密钥")
                return False
            
            # 4. 根据解锁工具类型处理
            if unlocker_type == "steamtools":
                return await self._process_steamautocracks_v2_for_steamtools(app_id, valid_depots, depot_manifest_map, use_st_auto_update, add_all_dlc, patch_depot_key, depotkeys_data)
            else:
                return await self._process_steamautocracks_v2_for_greenluma(app_id, valid_depots)
                
        except Exception as e:
            self.log.error(f'处理 SteamAutoCracks/ManifestHub(2) 清单时出错: {self.stack_error(e)}')
            return False

    async def _get_depots_and_manifests_from_steamui(self, app_id: str) -> Dict[str, str]:
        """从 steamui API 获取 depot 和对应的 manifest 信息"""
        try:
            url = f"https://steamui.com/api/get_appinfo.php?appid={app_id}"
            response = await self.client.get(url, timeout=20)
            response.raise_for_status()
            
            # steamui API 返回的是VDF格式，不是JSON格式
            vdf_content = response.text
            self.log.info(f"steamui API 原始响应内容预览: {vdf_content[:200]}...")
            
            # 使用VDF解析器解析内容
            import vdf
            data = vdf.loads(vdf_content)
            
            self.log.info(f"VDF解析后的数据结构键: {list(data.keys())}")
            
            depot_manifest_map = {}
            
            # 遍历所有键，找到数字格式的depot ID
            for key, value in data.items():
                # 检查是否是数字格式的 depot ID
                if key.isdigit() and isinstance(value, dict):
                    # 检查是否有 manifests 信息（确认是有效的 depot）
                    if 'manifests' in value and value['manifests']:
                        manifests = value['manifests']
                        if isinstance(manifests, dict) and 'public' in manifests:
                            public_manifest = manifests['public']
                            if isinstance(public_manifest, dict) and 'gid' in public_manifest:
                                manifest_id = public_manifest['gid']
                                depot_manifest_map[key] = manifest_id
                                self.log.info(f"发现有效 depot: {key}, manifest: {manifest_id}")
            
            if depot_manifest_map:
                self.log.info(f"总共找到 {len(depot_manifest_map)} 个有效的 depot 及其 manifest")
                return depot_manifest_map
            else:
                # 如果没有找到depot，尝试查找其他可能的结构
                self.log.warning("在根级别未找到depot，尝试查找嵌套结构...")
                
                # 检查是否有 'depots' 键（某些情况下可能存在）
                if 'depots' in data:
                    depots = data['depots']
                    for depot_id, depot_info in depots.items():
                        if depot_id.isdigit() and isinstance(depot_info, dict):
                            if 'manifests' in depot_info and depot_info['manifests']:
                                manifests = depot_info['manifests']
                                if isinstance(manifests, dict) and 'public' in manifests:
                                    public_manifest = manifests['public']
                                    if isinstance(public_manifest, dict) and 'gid' in public_manifest:
                                        manifest_id = public_manifest['gid']
                                        depot_manifest_map[depot_id] = manifest_id
                                        self.log.info(f"在depots键下发现有效 depot: {depot_id}, manifest: {manifest_id}")
                
                # 如果还是没找到，检查是否有应用信息的嵌套结构
                if not depot_manifest_map:
                    for key, value in data.items():
                        if isinstance(value, dict) and 'depots' in value:
                            depots = value['depots']
                            for depot_id, depot_info in depots.items():
                                if depot_id.isdigit() and isinstance(depot_info, dict):
                                    if 'manifests' in depot_info and depot_info['manifests']:
                                        manifests = depot_info['manifests']
                                        if isinstance(manifests, dict) and 'public' in manifests:
                                            public_manifest = manifests['public']
                                            if isinstance(public_manifest, dict) and 'gid' in public_manifest:
                                                manifest_id = public_manifest['gid']
                                                depot_manifest_map[depot_id] = manifest_id
                                                self.log.info(f"在嵌套depots键下发现有效 depot: {depot_id}, manifest: {manifest_id}")
                
                if not depot_manifest_map:
                    self.log.error(f"经过多种尝试后，仍未在steamui API响应中找到 AppID {app_id} 的depot信息")
                    self.log.error(f"VDF数据结构: {list(data.keys())}")
                    return {}
                
                return depot_manifest_map
            
        except vdf.VDFError as e:
            self.log.error(f"解析 steamui API VDF 响应失败: {e}")
            self.log.error(f"原始VDF内容: {vdf_content[:500]}...")
            return {}
        except Exception as e:
            self.log.error(f"从 steamui API 获取 depot 信息失败: {e}")
            return {}

    async def _process_steamautocracks_v2_for_steamtools(self, app_id: str, valid_depots: Dict[str, str], depot_manifest_map: Dict[str, str], use_st_auto_update: bool, add_all_dlc: bool, patch_depot_key: bool, depotkeys_data: Dict) -> bool:
        """为 SteamTools 处理 SteamAutoCracks/ManifestHub(2) 清单"""
        try:
            stplug_path = self.steam_path / 'config' / 'stplug-in'
            
            lua_filename = f"{app_id}.lua"
            lua_filepath = stplug_path / lua_filename
            
            # 检查是否启用了自动更新模式
            is_auto_update_mode = use_st_auto_update
            
            # 生成 lua 文件内容
            lines = []
            
            # 第一行：主游戏 appid
            lines.append(f'addappid({app_id})')
            
            # 添加所有有效的 depot 及其密钥
            for depot_id, depotkey in valid_depots.items():
                lines.append(f'addappid({depot_id}, 1, "{depotkey}")')
            
            # 添加 setManifestid 行（使用从 steamui API 获取的 manifest 信息）
            manifest_lines = []
            for depot_id in valid_depots.keys():
                if depot_id in depot_manifest_map:
                    manifest_id = depot_manifest_map[depot_id]
                    # 根据是否启用自动更新决定是否注释掉 manifest 行
                    if is_auto_update_mode:
                        # 自动更新模式：注释掉 setManifestid 行
                        manifest_lines.append(f'--setManifestid({depot_id}, "{manifest_id}")')
                        self.log.info(f"添加注释的 manifest 映射（自动更新模式）: depot {depot_id} -> manifest {manifest_id}")
                    else:
                        # 固定版本模式：正常添加 setManifestid 行
                        manifest_lines.append(f'setManifestid({depot_id}, "{manifest_id}")')
                        self.log.info(f"添加 manifest 映射（固定版本）: depot {depot_id} -> manifest {manifest_id}")
            
            # 写入文件
            async with aiofiles.open(lua_filepath, mode="w", encoding="utf-8") as lua_file:
                await lua_file.write('\n'.join(lines) + '\n')
                if manifest_lines:
                    await lua_file.write('\n-- Manifests\n')
                    await lua_file.write('\n'.join(manifest_lines) + '\n')
            
            self.log.info(f"已为SteamTools生成解锁文件: {lua_filename}")
            
            # 处理 DLC
            if add_all_dlc:
                await self._add_free_dlcs_to_lua(app_id, lua_filepath)
            
            # 处理创意工坊密钥修补（复用已下载的 depotkeys_data）
            if patch_depot_key:
                self.log.info("开始修补创意工坊depotkey...")
                await self._patch_lua_with_existing_depotkeys(app_id, lua_filepath, depotkeys_data)
            
            return True
            
        except Exception as e:
            self.log.error(f'为 SteamTools 处理 SteamAutoCracks/ManifestHub(2) 清单时出错: {e}')
            return False

    async def _process_steamautocracks_v2_for_greenluma(self, app_id: str, valid_depots: Dict[str, str]) -> bool:
        """为 GreenLuma 处理 SteamAutoCracks/ManifestHub(2) 清单"""
        try:
            # GreenLuma needs the depotkeys merged into config.vdf
            depots_config = {'depots': {depot_id: {"DecryptionKey": key} for depot_id, key in valid_depots.items()}}
            
            # Merge depotkeys
            config_vdf_path = self.steam_path / 'config' / 'config.vdf'
            if await self.depotkey_merge(config_vdf_path, depots_config):
                self.log.info("已将密钥合并到 config.vdf")
            
            # Add app IDs to GreenLuma
            gl_ids = list(valid_depots.keys())
            gl_ids.append(app_id)
            await self.greenluma_add(list(set(gl_ids)))
            self.log.info("已添加到 GreenLuma")
            
            return True
            
        except Exception as e:
            self.log.error(f'为 GreenLuma 处理 SteamAutoCracks/ManifestHub(2) 清单时出错: {e}')
            return False
    
    async def _patch_lua_with_existing_depotkeys(self, app_id: str, lua_file_path: Path, depotkeys_data: Dict) -> bool:
        """使用已有的 depotkeys 数据修补 LUA 文件（避免重复下载）"""
        try:
            # 检查 app_id 是否在 depotkeys 中
            if app_id not in depotkeys_data:
                self.log.warning(f"没有此AppID的depotkey: {app_id}")
                return False
            
            depotkey = depotkeys_data[app_id]
            
            # 检查 depotkey 是否有效
            if not depotkey or not str(depotkey).strip():
                self.log.warning(f"AppID {app_id} 的 depotkey 为空或无效，跳过修补: '{depotkey}'")
                return False
            
            depotkey = str(depotkey).strip()
            self.log.info(f"找到 AppID {app_id} 的有效 depotkey: {depotkey}")
            
            # 读取现有 LUA 文件
            if not lua_file_path.exists():
                self.log.error(f"LUA文件不存在: {lua_file_path}")
                return False
            
            async with aiofiles.open(lua_file_path, 'r', encoding='utf-8') as f:
                lua_content = await f.read()
            
            # 解析行
            lines = lua_content.strip().split('\n')
            new_lines = []
            app_id_line_removed = False
            
            # 移除现有的 addappid({app_id}) 行并添加带 depotkey 的新行
            for line in lines:
                line = line.strip()
                # 检查是否是需要替换的简单 addappid 行
                if line == f"addappid({app_id})":
                    # 替换为带 depotkey 的版本
                    new_lines.append(f'addappid({app_id},1,"{depotkey}")')
                    app_id_line_removed = True
                    self.log.info(f"已替换: addappid({app_id}) -> addappid({app_id},1,\"{depotkey}\")")
                else:
                    new_lines.append(line)
            
            # 如果没有找到简单的 addappid 行，添加 depotkey 版本
            if not app_id_line_removed:
                new_lines.append(f'addappid({app_id},1,"{depotkey}")')
                self.log.info(f"已添加新的 depotkey 条目: addappid({app_id},1,\"{depotkey}\")")
            
            # 写回文件
            async with aiofiles.open(lua_file_path, 'w', encoding='utf-8') as f:
                await f.write('\n'.join(new_lines) + '\n')
            
            self.log.info(f"成功修补 LUA 文件的 depotkey: {lua_file_path.name}")
            return True
            
        except Exception as e:
            self.log.error(f"修补 LUA depotkey 时出错: {self.stack_error(e)}")
            return False

    async def patch_lua_with_depotkey(self, app_id: str, lua_file_path: Path) -> bool:
        """Patch LUA file with depotkey from SteamAutoCracks repository"""
        try:
            # Ensure network environment is detected for mirror selection
            if 'IS_CN' not in os.environ:
                self.log.info("检测网络环境以优化下载源选择...")
                await self.checkcn()
            
            # Download depotkeys.json
            depotkeys_data = await self.download_depotkeys_json()
            if not depotkeys_data:
                self.log.error("无法获取 depotkeys 数据，跳过 depotkey 修补。")
                return False
            
            # Check if app_id exists in depotkeys
            if app_id not in depotkeys_data:
                self.log.warning(f"没有此AppID的depotkey: {app_id}")
                return False
            
            depotkey = depotkeys_data[app_id]
            
            # FIXED: Check if depotkey is valid (not empty, not None, not just whitespace)
            if not depotkey or not str(depotkey).strip():
                self.log.warning(f"AppID {app_id} 的 depotkey 为空或无效，跳过修补: '{depotkey}'")
                return False
            
            # Make sure depotkey is string and strip whitespace
            depotkey = str(depotkey).strip()
            self.log.info(f"找到 AppID {app_id} 的有效 depotkey: {depotkey}")
            
            # Read existing LUA file
            if not lua_file_path.exists():
                self.log.error(f"LUA文件不存在: {lua_file_path}")
                return False
            
            async with aiofiles.open(lua_file_path, 'r', encoding='utf-8') as f:
                lua_content = await f.read()
            
            # Parse lines
            lines = lua_content.strip().split('\n')
            new_lines = []
            app_id_line_removed = False
            
            # Remove existing addappid({app_id}) line and add new one with depotkey
            for line in lines:
                line = line.strip()
                # Check if this is the simple addappid line we need to replace
                if line == f"addappid({app_id})":
                    # Replace with depotkey version
                    new_lines.append(f'addappid({app_id},1,"{depotkey}")')
                    app_id_line_removed = True
                    self.log.info(f"已替换: addappid({app_id}) -> addappid({app_id},1,\"{depotkey}\")")
                else:
                    new_lines.append(line)
            
            # If we didn't find the simple addappid line, add the depotkey version
            if not app_id_line_removed:
                new_lines.append(f'addappid({app_id},1,"{depotkey}")')
                self.log.info(f"已添加新的 depotkey 条目: addappid({app_id},1,\"{depotkey}\")")
            
            # Write back to file
            async with aiofiles.open(lua_file_path, 'w', encoding='utf-8') as f:
                await f.write('\n'.join(new_lines) + '\n')
            
            self.log.info(f"成功修补 LUA 文件的 depotkey: {lua_file_path.name}")
            return True
            
        except Exception as e:
            self.log.error(f"修补 LUA depotkey 时出错: {self.stack_error(e)}")
            return False

    # Original methods continue...
    def restart_steam(self) -> bool:
        if not self.steam_path:
            self.log.error("无法重启 Steam：未找到 Steam 路径。")
            return False
        steam_exe_path = self.steam_path / 'steam.exe'
        if not steam_exe_path.exists():
            self.log.error(f"无法启动 Steam：在 '{self.steam_path}' 目录下未找到 steam.exe。")
            return False
        try:
            self.log.info("正在尝试关闭正在运行的 Steam 进程...")
            result = subprocess.run(["taskkill", "/F", "/IM", "steam.exe"], capture_output=True, text=True, check=False)
            if result.returncode == 0: self.log.info("成功关闭 Steam 进程。")
            elif result.returncode == 128: self.log.info("未找到正在运行的 Steam 进程，将直接启动。")
            else: self.log.warning(f"关闭 Steam 时遇到问题 (返回码: {result.returncode})。错误信息: {result.stderr.strip()}")
            self.log.info("等待 3 秒以确保 Steam 完全关闭...")
            time.sleep(3)
            self.log.info(f"正在尝试从 '{steam_exe_path}' 启动 Steam...")
            subprocess.Popen([str(steam_exe_path)], creationflags=subprocess.DETACHED_PROCESS, close_fds=True)
            self.log.info("已发送重启 Steam 的指令。")
            return True
        except Exception as e:
            self.log.error(f"重启 Steam 失败: {self.stack_error(e)}")
            return False

    async def check_github_api_rate_limit(self) -> bool:
        github_token = self.config.get("Github_Personal_Token", "").strip()
        headers = {'Authorization': f'Bearer {github_token}'} if github_token else None
        if github_token: self.log.info("已配置GitHub Token。")
        else: self.log.warning("未找到GitHub Token。您的API请求将受到严格的速率限制。")
        url = 'https://api.github.com/rate_limit'
        try:
            r = await self.client.get(url, headers=headers)
            r.raise_for_status()
            rate_limit = r.json().get('resources', {}).get('core', {})
            remaining = rate_limit.get('remaining', 0)
            reset_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(rate_limit.get('reset', 0)))
            self.log.info(f'GitHub API剩余请求次数: {remaining}')
            if remaining == 0:
                self.log.error("GitHub API请求次数已用尽。")
                self.log.error(f"您的请求次数将于 {reset_time} 重置。")
                self.log.error("要提升请求上限，请在config.json文件中添加您的'Github_Personal_Token'。")
                return False
            return True
        except Exception as e:
            self.log.error(f'检查GitHub API速率限制失败: {self.stack_error(e)}')
            return False

    async def checkcn(self) -> bool:
        try:
            req = await self.client.get('https://mips.kugou.com/check/iscn?&format=json', timeout=5)
            body = req.json()
            is_cn = bool(body['flag'])
            os.environ['IS_CN'] = 'yes' if is_cn else 'no'
            if is_cn: self.log.info(f"检测到区域为中国大陆 ({body['country']})。将使用国内镜像。")
            else: self.log.info(f"检测到区域为非中国大陆 ({body['country']})。将直接使用GitHub。")
            return is_cn
        except Exception:
            os.environ['IS_CN'] = 'yes'
            self.log.warning('无法确定服务器位置，默认您在中国大陆。')
            return True

    def parse_lua_file_for_depots(self, lua_file_path: str) -> Dict:
        addappid_pattern = re.compile(r'addappid\((\d+),\s*1,\s*"([^"]+)"\)')
        depots = {}
        try:
            with open(lua_file_path, 'r', encoding='utf-8') as file:
                lua_content = file.read()
                for match in addappid_pattern.finditer(lua_content):
                    depots[match.group(1)] = {"DecryptionKey": match.group(2)}
        except Exception as e:
            self.log.error(f"解析lua文件 {lua_file_path} 出错: {e}")
        return depots

    async def depotkey_merge(self, config_path: Path, depots_config: dict) -> bool:
        if not config_path.exists():
            self.log.error('未找到Steam默认配置文件，您可能尚未登录。')
            return False
        try:
            async with aiofiles.open(config_path, encoding='utf-8') as f: content = await f.read()
            config_vdf = vdf.loads(content)
            steam = config_vdf.get('InstallConfigStore', {}).get('Software', {}).get('Valve') or \
                    config_vdf.get('InstallConfigStore', {}).get('Software', {}).get('valve')
            if steam is None:
                self.log.error('找不到Steam配置节。')
                return False
            depots = steam.setdefault('depots', {})
            depots.update(depots_config.get('depots', {}))
            async with aiofiles.open(config_path, mode='w', encoding='utf-8') as f:
                await f.write(vdf.dumps(config_vdf, pretty=True))
            self.log.info('成功将密钥合并到config.vdf。')
            return True
        except Exception as e:
            self.log.error(f'合并失败: {self.stack_error(e)}')
            return False

    async def _get_from_mirrors(self, sha: str, path: str, repo: str) -> bytes:
        urls = [f'https://raw.githubusercontent.com/{repo}/{sha}/{path}']
        if os.environ.get('IS_CN') == 'yes':
            urls = [f'https://cdn.jsdmirror.com/gh/{repo}@{sha}/{path}', f'https://raw.gitmirror.com/{repo}/{sha}/{path}', f'https://raw.dgithub.xyz/{repo}/{sha}/{path}', f'https://gh.akass.cn/{repo}/{sha}/{path}']
        for url in urls:
            try:
                r = await self.client.get(url, timeout=30)
                if r.status_code == 200:
                    self.log.info(f'下载成功: {path} (来自 {url.split("/")[2]})')
                    return r.content
                self.log.error(f'下载失败: {path} (来自 {url.split("/")[2]}) - 状态码: {r.status_code}')
            except httpx.RequestError as e:
                self.log.error(f'下载失败: {path} (来自 {url.split("/")[2]}) - 错误: {e}')
        raise Exception(f'尝试所有镜像后仍无法下载文件: {path}')

    async def greenluma_add(self, depot_id_list: list) -> bool:
        app_list_path = self.steam_path / 'AppList'
        try:
            for file in app_list_path.glob('*.txt'): file.unlink(missing_ok=True)
            depot_dict = { int(i.stem): int(i.read_text(encoding='utf-8').strip()) for i in app_list_path.iterdir() if i.is_file() and i.stem.isdecimal() and i.suffix == '.txt' }
            for depot_id in map(int, depot_id_list):
                if depot_id not in depot_dict.values():
                    index = max(depot_dict.keys(), default=-1) + 1
                    (app_list_path / f'{index}.txt').write_text(str(depot_id), encoding='utf-8')
                    depot_dict[index] = depot_id
            self.log.info(f"成功将 {len(depot_id_list)} 个ID添加到GreenLuma的AppList中。")
            return True
        except Exception as e:
            self.log.error(f'GreenLuma添加 AppID失败: {e}')
            return False
            
    async def _get_steamcmd_api_data(self, appid: str) -> Dict:
        try:
            resp = await self.client.get(f"https://api.steamcmd.net/v1/info/{appid}", timeout=20)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            self.log.error(f"从 api.steamcmd.net 获取 AppID {appid} 数据失败: {e}")
            return {}

    # UPDATED: Use new safe functions for DLC retrieval
    async def _get_dlc_ids(self, appid: str) -> List[str]:
        """获取DLC ID列表，使用新的安全函数"""
        return await self.get_dlc_ids_safe(appid)

    # UPDATED: Use new safe functions for depot retrieval  
    async def _get_depots(self, appid: str) -> List[Dict]:
        """获取Depot信息列表，转换为旧格式兼容"""
        depot_tuples = await self.get_depots_safe(appid)
        # Convert to old format for compatibility
        return [
            {
                "depot_id": depot_id,
                "size": size,
                "dlc_appid": source.split(':')[1] if source.startswith('DLC:') else None
            }
            for depot_id, manifest_id, size, source in depot_tuples
        ]

    async def _add_free_dlcs_to_lua(self, app_id: str, lua_filepath: Path):
        self.log.info(f"开始为 AppID {app_id} 查找无密钥/无Depot的DLC...")
        try:
            all_dlc_ids = await self._get_dlc_ids(app_id)
            if not all_dlc_ids:
                self.log.info(f"AppID {app_id} 未找到任何DLC。")
                return

            tasks = [self._get_depots(dlc_id) for dlc_id in all_dlc_ids]
            results = await asyncio.gather(*tasks)

            depot_less_dlc_ids = [dlc_id for dlc_id, dlc_depots in zip(all_dlc_ids, results) if not dlc_depots]
            
            if not depot_less_dlc_ids:
                self.log.info(f"未找到适用于 AppID {app_id} 的无密钥/无Depot的DLC。")
                return

            async with self.lock:
                if not lua_filepath.exists():
                    self.log.error(f"目标LUA文件 {lua_filepath} 不存在，无法合并DLC。")
                    return

                async with aiofiles.open(lua_filepath, 'r', encoding='utf-8') as f:
                    existing_lines = [line.strip() for line in await f.readlines() if line.strip()]
                
                existing_appids = {match.group(1) for line in existing_lines if (match := re.search(r'addappid\((\d+)', line))}
                new_dlcs_to_add = [dlc_id for dlc_id in depot_less_dlc_ids if dlc_id not in existing_appids]
                
                if not new_dlcs_to_add:
                    self.log.info(f"所有找到的无Depot DLC均已存在于解锁文件中。无需添加。")
                    return

                self.log.info(f"找到 {len(new_dlcs_to_add)} 个新的无密钥/无Depot DLC，正在合并到 LUA 文件...")

                final_lines = set(existing_lines)
                for dlc_id in new_dlcs_to_add: final_lines.add(f"addappid({dlc_id})")

                def sort_key(line):
                    match_add = re.search(r'addappid\((\d+)', line)
                    if match_add: return (0, int(match_add.group(1)))
                    match_set = re.search(r'setManifestid\((\d+)', line)
                    if match_set: return (1, int(match_set.group(1)))
                    return (2, line)
                
                sorted_lines = sorted(list(final_lines), key=sort_key)

                async with aiofiles.open(lua_filepath, 'w', encoding='utf-8') as f:
                    await f.write('\n'.join(sorted_lines) + '\n')
            
            self.log.info(f"成功将 {len(new_dlcs_to_add)} 个新的无密钥/无Depot DLC合并到 {lua_filepath.name}")

        except Exception as e:
            self.log.error(f"添加无密钥DLC时出错: {self.stack_error(e)}")

    # MODIFIED: Added patch_depot_key parameter
    async def _process_zip_manifest_generic(self, app_id: str, download_url: str, source_name: str, unlocker_type: str, use_st_auto_update: bool, add_all_dlc: bool, patch_depot_key: bool = False) -> bool:
        zip_path = self.temp_path / f'{app_id}.zip'
        extract_path = self.temp_path / app_id
        try:
            self.temp_path.mkdir(exist_ok=True, parents=True)
            self.log.info(f'正从 {source_name} 下载 AppID {app_id} 的清单...')
            response = await self.client.get(download_url, timeout=60)
            response.raise_for_status()
            async with aiofiles.open(zip_path, 'wb') as f: await f.write(response.content)
            self.log.info('正在解压...')
            with zipfile.ZipFile(zip_path, 'r') as zip_ref: zip_ref.extractall(extract_path)
            
            st_files = list(extract_path.glob('*.st'))
            if st_files:
                st_converter = STConverter()
                for st_file in st_files:
                    try:
                        lua_content = st_converter.convert_file(str(st_file))
                        (st_file.with_suffix('.lua')).write_text(lua_content, encoding='utf-8')
                        self.log.info(f'已转换 {st_file.name} -> {st_file.with_suffix(".lua").name}')
                    except Exception as e: self.log.error(f'转换 .st 文件 {st_file.name} 失败: {e}')

            manifest_files = list(extract_path.glob('*.manifest'))
            lua_files = list(extract_path.glob('*.lua'))
            
            if unlocker_type == "steamtools":
                self.log.info(f"SteamTools 自动更新模式: {'已启用' if use_st_auto_update else '已禁用'}")
                stplug_path = self.steam_path / 'config' / 'stplug-in'
                
                all_depots = {}
                for lua_f in lua_files:
                    depots = self.parse_lua_file_for_depots(str(lua_f))
                    all_depots.update(depots)

                lua_filename = f"{app_id}.lua"
                lua_filepath = stplug_path / lua_filename
                async with aiofiles.open(lua_filepath, mode="w", encoding="utf-8") as lua_file:
                    await lua_file.write(f'addappid({app_id})\n')
                    for depot_id, info in all_depots.items():
                        await lua_file.write(f'addappid({depot_id}, 1, "{info["DecryptionKey"]}")\n')

                    for manifest_f in manifest_files:
                        match = re.search(r'(\d+)_(\w+)\.manifest', manifest_f.name)
                        if match:
                            line = f'setManifestid({match.group(1)}, "{match.group(2)}")\n'
                            if use_st_auto_update: await lua_file.write('--' + line)
                            else: await lua_file.write(line)
                self.log.info(f"已为 SteamTools 生成解锁文件: {lua_filename}")

                if add_all_dlc:
                    await self._add_free_dlcs_to_lua(app_id, lua_filepath)

                # NEW: Apply depotkey patch if requested
                if patch_depot_key:
                    self.log.info("开始修补创意工坊depotkey...")
                    await self.patch_lua_with_depotkey(app_id, lua_filepath)

            else:
                self.log.info(f'检测到 GreenLuma/标准模式，将处理来自 {source_name} 的文件。')
                if not manifest_files:
                    self.log.warning(f"在来自 {source_name} 的压缩包中未找到 .manifest 文件。")
                    return False

                steam_depot_path = self.steam_path / 'depotcache'
                for f in manifest_files:
                    shutil.copy2(f, steam_depot_path / f.name)
                    self.log.info(f'已复制清单: {f.name}')
                
                all_depots = {}
                for lua in lua_files:
                    depots = self.parse_lua_file_for_depots(str(lua))
                    all_depots.update(depots)
                if all_depots:
                    await self.depotkey_merge(self.steam_path / 'config' / 'config.vdf', {'depots': all_depots})

            self.log.info(f'成功处理来自 {source_name} 的清单。')
            return True
        except Exception as e:
            self.log.error(f'处理来自 {source_name} 的清单时出错: {self.stack_error(e)}')
            return False
        finally:
            if zip_path.exists(): zip_path.unlink(missing_ok=True)
            if extract_path.exists(): shutil.rmtree(extract_path)

    async def process_zip_source(self, app_id: str, tool_type: str, unlocker_type: str, use_st_auto_update: bool, add_all_dlc: bool, patch_depot_key: bool = False) -> bool:
        source_map = {
            "printedwaste": "https://api.printedwaste.com/gfk/download/{app_id}",
            "cysaw": "https://cysaw.top/uploads/{app_id}.zip",
            "furcate": "https://furcate.eu/files/{app_id}.zip",
            "assiw": "https://assiw.cngames.site/qindan/{app_id}.zip",
            "steamdatabase": "https://steamdatabase.s3.eu-north-1.amazonaws.com/{app_id}.zip",
            "steamautocracks_v2": "special"  # 特殊处理标识
        }
        source_name_map = { 
            "printedwaste": "SWA V2 (printedwaste)", 
            "cysaw": "Cysaw", 
            "furcate": "Furcate", 
            "assiw": "CNGS (assiw)", 
            "steamdatabase": "SteamDatabase",
            "steamautocracks_v2": "SteamAutoCracks/ManifestHub(2)"
        }
        
        # 特殊处理 steamautocracks_v2
        if tool_type == "steamautocracks_v2":
            return await self.process_steamautocracks_v2_manifest(app_id, unlocker_type, use_st_auto_update, add_all_dlc, patch_depot_key)
        
        # Check for custom zip repos
        custom_zip_repos = self.get_custom_zip_repos()
        for repo_config in custom_zip_repos:
            if tool_type == f"custom_zip_{repo_config['name']}":
                return await self.process_custom_zip_manifest(app_id, repo_config, add_all_dlc, patch_depot_key)
        
        url_template = source_map.get(tool_type)
        source_name = source_name_map.get(tool_type)
        if not url_template or not source_name:
            self.log.error(f"未知的压缩包源: {tool_type}")
            return False
        download_url = url_template.format(app_id=app_id)
        return await self._process_zip_manifest_generic(app_id, download_url, source_name, unlocker_type, use_st_auto_update, add_all_dlc, patch_depot_key)

    async def fetch_branch_info(self, url: str, headers: Dict) -> Dict | None:
        try:
            r = await self.client.get(url, headers=headers)
            r.raise_for_status()
            return r.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 403: self.log.error("GitHub API请求次数已用尽。")
            elif e.response.status_code != 404: self.log.error(f"从 {url} 获取信息失败: {self.stack_error(e)}")
            return None
        except Exception as e:
            self.log.error(f'从 {url} 获取信息时发生意外错误: {self.stack_error(e)}')
            return None
            
    # MODIFIED: Updated to use all github repos including custom ones
    async def search_all_repos_for_appid(self, app_id: str, repos: List[str] = None) -> List[Dict]:
        """Search for app_id in all GitHub repositories (builtin + custom)"""
        if repos is None:
            repos = self.get_all_github_repos()
        
        github_token = self.config.get("Github_Personal_Token", "")
        headers = {'Authorization': f'Bearer {github_token}'} if github_token else None
        tasks = [self._search_single_repo(app_id, repo, headers) for repo in repos]
        results = await asyncio.gather(*tasks)
        return [res for res in results if res]

    async def _search_single_repo(self, app_id: str, repo: str, headers: Dict) -> Dict | None:
        self.log.info(f"正在仓库 {repo} 中搜索 AppID: {app_id}")
        url = f'https://api.github.com/repos/{repo}/branches/{app_id}'
        r_json = await self.fetch_branch_info(url, headers)
        if r_json and 'commit' in r_json:
            tree_url = r_json['commit']['commit']['tree']['url']
            r2_json = await self.fetch_branch_info(tree_url, headers)
            if r2_json and 'tree' in r2_json:
                self.log.info(f"在 {repo} 中找到清单。")
                return {'repo': repo, 'sha': r_json['commit']['sha'], 'tree': r2_json['tree'], 'update_date': r_json["commit"]["commit"]["author"]["date"]}
        return None

    # MODIFIED: Added patch_depot_key parameter
    async def process_github_manifest(self, app_id: str, repo: str, unlocker_type: str, use_st_auto_update: bool, add_all_dlc: bool, patch_depot_key: bool = False) -> bool:
        github_token = self.config.get("Github_Personal_Token", "")
        headers = {'Authorization': f'Bearer {github_token}'} if github_token else None
        
        url = f'https://api.github.com/repos/{repo}/branches/{app_id}'
        r_json = await self.fetch_branch_info(url, headers)
        if not (r_json and 'commit' in r_json):
            self.log.error(f'无法获取 {repo} 中 {app_id} 的分支信息。如果该清单在此仓库中不存在，这是正常现象。')
            return False
        
        sha, tree_url = r_json['commit']['sha'], r_json['commit']['commit']['tree']['url']
        r2_json = await self.fetch_branch_info(tree_url, headers)
        if not (r2_json and 'tree' in r2_json):
            self.log.error(f'无法获取 {repo} 中 {app_id} 的文件列表。')
            return False
            
        all_files_in_tree = r2_json.get('tree', [])
        files_to_download = all_files_in_tree[:]
        
        if unlocker_type == "steamtools" and use_st_auto_update:
            files_to_download = [item for item in all_files_in_tree if not item['path'].endswith('.manifest')]
        
        if not files_to_download and all_files_in_tree: self.log.info("没有需要下载的文件（可能是因为自动更新模式跳过了所有文件）。")
        if not all_files_in_tree:
            self.log.warning(f"仓库 {repo} 的分支 {app_id} 为空。")
            return True

        try:
            downloaded_files = {}
            if files_to_download:
                tasks = [self._get_from_mirrors(sha, item['path'], repo) for item in files_to_download]
                downloaded_contents = await asyncio.gather(*tasks)
                downloaded_files = {item['path']: content for item, content in zip(files_to_download, downloaded_contents)}
        except Exception as e:
            self.log.error(f"下载文件失败，正在中止对 {app_id} 的处理: {e}")
            return False
        
        all_manifest_paths_in_tree = [item['path'] for item in all_files_in_tree if item['path'].endswith('.manifest')]
        downloaded_manifest_paths = [p for p in downloaded_files if p.endswith('.manifest')]
        key_vdf_path = next((p for p in downloaded_files if "key.vdf" in p.lower()), None)
        all_depots = {}
        if key_vdf_path:
            try:
                depots_config = vdf.loads(downloaded_files[key_vdf_path].decode('utf-8'))
                all_depots = depots_config.get('depots', {})
            except Exception as e: self.log.error(f"解析 key.vdf 失败: {e}")

        if unlocker_type == "steamtools":
            self.log.info(f"SteamTools 自动更新模式: {'已启用' if use_st_auto_update else '已禁用'}")
            stplug_path = self.steam_path / 'config' / 'stplug-in'
            lua_filename = f"{app_id}.lua"
            lua_filepath = stplug_path / lua_filename
            async with aiofiles.open(lua_filepath, mode="w", encoding="utf-8") as lua_file:
                await lua_file.write(f'addappid({app_id})\n')
                for depot_id, info in all_depots.items():
                    key = info.get("DecryptionKey", "")
                    await lua_file.write(f'addappid({depot_id}, 1, "{key}")\n')
                for manifest_file_path in all_manifest_paths_in_tree:
                    match = re.search(r'(\d+)_(\w+)\.manifest', Path(manifest_file_path).name)
                    if match:
                        line = f'setManifestid({match.group(1)}, "{match.group(2)}")\n'
                        if use_st_auto_update: await lua_file.write('--' + line)
                        else: await lua_file.write(line)
            self.log.info(f"已为 SteamTools 生成解锁文件: {app_id}.lua")
            
            if add_all_dlc:
                await self._add_free_dlcs_to_lua(app_id, lua_filepath)

            # NEW: Apply depotkey patch if requested
            if patch_depot_key:
                self.log.info("开始修补创意工坊depotkey...")
                await self.patch_lua_with_depotkey(app_id, lua_filepath)

        else:
            self.log.info("检测到 GreenLuma/标准模式，将复制 .manifest 文件到 depotcache。")
            if not downloaded_manifest_paths:
                self.log.error("GreenLuma 模式需要 .manifest 文件，但未能找到或下载。")
                return False
            
            depot_cache_path = self.steam_path / 'depotcache'
            for path in downloaded_manifest_paths:
                filename = Path(path).name
                (depot_cache_path / filename).write_bytes(downloaded_files[path])
                self.log.info(f"已为 GreenLuma 保存清单: {filename}")
            
            if all_depots:
                await self.depotkey_merge(self.steam_path / 'config' / 'config.vdf', {'depots': all_depots})
                gl_ids = list(all_depots.keys())
                gl_ids.append(app_id)
                await self.greenluma_add(list(set(gl_ids)))
                self.log.info("已合并密钥并添加到GreenLuma。")

        self.log.info(f'清单最后更新时间: {r_json["commit"]["commit"]["author"]["date"]}')
        return True
    
    def extract_app_id(self, user_input: str) -> str | None:
        match = re.search(r"/app/(\d+)", user_input) or re.search(r"steamdb\.info/app/(\d+)", user_input)
        if match: return match.group(1)
        return user_input if user_input.isdigit() else None

    async def find_appid_by_name(self, game_name: str) -> List[Dict]:
        try:
            game_name_encoded = quote(game_name)
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
            url = f"https://steamui.com/api/loadGames.php?page=1&search={game_name_encoded}&sort=update"
            r = await self.client.get(url, headers=headers, timeout=10)
            r.raise_for_status()
            data = r.json()
            games_data = data if isinstance(data, list) else data.get('games', [])
            games_list = []
            if isinstance(games_data, list):
                for item in games_data:
                    if item and item.get('appid') and item.get('name'):
                        games_list.append({'appid': item.get('appid'), 'name': item.get('name'), 'header_image': item.get('headerImg')})
            return games_list
        except httpx.HTTPStatusError as e:
            self.log.error(f"搜索游戏 '{game_name}' 时API返回状态错误: {e}")
            return []
        except Exception as e:
            self.log.error(f"搜索游戏 '{game_name}' 时出错: {self.stack_error(e)}")
            return []

    async def cleanup_temp_files(self):
        try:
            if self.temp_path.exists():
                shutil.rmtree(self.temp_path)
                self.log.info('临时文件已清理。')
        except Exception as e:
            self.log.error(f'清理临时文件失败: {self.stack_error(e)}')

    async def migrate(self, st_use: bool):
        directory = self.steam_path / "config" / "stplug-in"
        if st_use and directory.exists():
            self.log.info('检测到SteamTools, 正在检查是否有旧文件需要迁移...')
            for file in directory.glob("Cai_unlock_*.lua"):
                new_filename = directory / file.name.replace("Cai_unlock_", "")
                try:
                    file.rename(new_filename)
                    self.log.info(f'已重命名: {file.name} -> {new_filename.name}')
                except Exception as e:
                    self.log.error(f'重命名失败 {file.name}: {e}')

# --- END OF FILE backend.py ---
