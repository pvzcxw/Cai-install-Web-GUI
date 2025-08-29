# --- START OF FILE app.py (MODIFIED WITH AUTO-UPDATE AND CUSTOM REPOS) ---

import asyncio
import os
import webbrowser
import sys
import threading
import time
from typing import List, Dict, Optional, Any
from pathlib import Path
import json as standard_json
import winreg
import shutil
from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_socketio import SocketIO, emit

import tkinter as tk
from tkinter import ttk



if sys.platform == 'win32':
    import ctypes
    
    class ConsoleManager:
        def __init__(self):
            self.kernel32 = ctypes.WinDLL('kernel32')
            self.is_visible = self.kernel32.GetConsoleWindow() != 0
        def toggle_console(self):
            if self.is_visible: self._hide_console()
            else: self._show_console()
            return not self.is_visible
        def _show_console(self):
            if not self.is_visible:
                if self.kernel32.AllocConsole():
                    sys.stdout = open('CONOUT$', 'w')
                    sys.stderr = open('CONOUT$', 'w')
                    print("--- 控制台已附加 ---")
                    print("Cai Install 的日志将在这里显示。")
                    self.is_visible = True
                else: print("错误: 无法分配新的控制台。")
        def _hide_console(self):
            if self.is_visible:
                sys.stdout = sys.__stdout__
                sys.stderr = sys.__stderr__
                if self.kernel32.FreeConsole(): self.is_visible = False
                else: print("错误: 无法释放控制台。")
    console_manager = ConsoleManager()
else:
    class ConsoleManager:
        def toggle_console(self): return False
        def _show_console(self): pass
    console_manager = ConsoleManager()

# --- Project Setup ---
if getattr(sys, 'frozen', False): 
    project_root = Path(sys.executable).parent
elif hasattr(sys, '__nuitka_binary_dir__'):
    project_root = Path(sys.executable).parent
else: 
    project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

try:
    from backend import CaiBackend, DEFAULT_CONFIG
except ImportError as e:
    print(f"Import Error: {e}")
    sys.exit(1)

# --- Flask App Initialization ---
app = Flask(__name__)
app.config['SECRET_KEY'] = 'cai-install-gui-secret-key-v2'
app.config['USER_DATA_FOLDER'] = project_root / 'userdata'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')
socketio = SocketIO(app, cors_allowed_origins="*")

# --- GUI Port Prompt ---
def get_port_from_gui():
    result = {'port': 5000}
    root = tk.Tk()
    root.title("设置端口")
    window_width, window_height = 300, 150
    screen_width, screen_height = root.winfo_screenwidth(), root.winfo_screenheight()
    center_x = int(screen_width / 2 - window_width / 2)
    center_y = int(screen_height / 2 - window_height / 2)
    root.geometry(f'{window_width}x{window_height}+{center_x}+{center_y}')
    root.attributes('-topmost', True)
    main_frame = ttk.Frame(root, padding="20")
    main_frame.pack(fill="both", expand=True)
    ttk.Label(main_frame, text="请输入端口号 (默认: 5000):").pack(pady=5)
    port_var = tk.StringVar(value="5000")
    entry = ttk.Entry(main_frame, textvariable=port_var, width=10)
    entry.pack(pady=5)
    entry.focus()
    def on_ok():
        try:
            port_val = int(port_var.get().strip())
            if 1024 <= port_val <= 65535: result['port'] = port_val
        except (ValueError, TypeError): pass
        root.destroy()
    ttk.Button(main_frame, text="启动", command=on_ok).pack(pady=10)
    root.bind('<Return>', lambda event: on_ok())
    root.mainloop()
    return result['port']


# --- Pre-startup Config Check ---
def should_show_console_on_startup():
    config_path = project_root / 'config.json'
    if not config_path.exists(): return False
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = standard_json.load(f)
        return config.get("show_console_on_startup", False)
    except Exception as e:
        print(f"启动时读取配置失败: {e}")
        return False

# --- Global Task State & Logging ---
TASK_STATE = {"status": "idle", "progress": [], "result": None}

def patch_log_for_socketio(logger):
    if hasattr(logger, '_is_patched_by_web'): return
    def create_handler(original_func, log_type):
        def handler(msg, *args, **kwargs):
            try: full_msg = msg % args if args else msg
            except TypeError: full_msg = str(msg)
            if len(TASK_STATE["progress"]) > 200: TASK_STATE["progress"].pop(0)
            TASK_STATE["progress"].append({"type": log_type, "message": full_msg})
            socketio.emit('task_progress', {"type": log_type, "message": full_msg})
            return original_func(full_msg)
        return handler
    original_info, original_warning, original_error, original_debug = logger.info, logger.warning, logger.error, logger.debug
    logger.info, logger.warning, logger.error, logger.debug = create_handler(original_info, "info"), create_handler(original_warning, "warning"), create_handler(original_error, "error"), create_handler(original_debug, "debug")
    setattr(logger, '_is_patched_by_web', True)

# --- HTML Page Routes ---
@app.route('/')
def index(): return render_template('index.html')
@app.route('/settings')
def settings_page(): return render_template('settings.html')
@app.route('/about')
def about_page(): return render_template('about.html')

# --- Core API Routes ---
@app.route('/api/initialize', methods=['POST'])
def initialize_app():  # 改为同步函数
    try:
        async def _init():
            async with CaiBackend() as backend:
                patch_log_for_socketio(backend.log)
                unlocker_type = await backend.initialize()
                if backend.config is None:
                    return {"success": False, "message": "加载配置失败，请检查日志。"}
                return {
                    "success": True,
                    "unlocker_type": unlocker_type,
                    "steam_path": str(backend.steam_path) if backend.steam_path else "Not Found",
                    "has_token": bool(backend.config.get("Github_Personal_Token", "").strip())
                }
        
        result = asyncio.run(_init())
        return jsonify(result)
        
    except Exception as e:
        dummy_backend = CaiBackend()
        message = f"后端初始化失败: {str(e)}"
        dummy_backend.log.error(dummy_backend.stack_error(e))
        return jsonify({"success": False, "message": message})

# NEW: Auto-update check endpoint
@app.route('/api/check_updates', methods=['POST'])
def check_updates():  # 改为同步函数
    try:
        async def _check():
            async with CaiBackend() as backend:
                patch_log_for_socketio(backend.log)
                await backend.initialize()
                has_update, update_info = await backend.check_for_updates()
                return {
                    "success": True,
                    "has_update": has_update,
                    "update_info": update_info
                }
        
        result = asyncio.run(_check())
        return jsonify(result)
        
    except Exception as e:
        dummy_backend = CaiBackend()
        message = f"检查更新失败: {str(e)}"
        dummy_backend.log.error(dummy_backend.stack_error(e))
        return jsonify({"success": False, "message": message})

# NEW: Get available sources (including custom repos)
@app.route('/api/sources', methods=['GET'])
def get_sources():  # 改为同步函数
    try:
        async def _get_sources():
            async with CaiBackend() as backend:
                await backend.initialize()
                
                # Built-in sources
                builtin_sources = {
                    "自动搜索GitHub": "search",
                    "SWA V2": "printedwaste", 
                    "Cysaw": "cysaw",
                    "Furcate": "furcate",
                    "CNGS": "assiw",
                    "steamdatabase": "steamdatabase",
                    "SteamAutoCracks/ManifestHub(2)": "steamautocracks_v2",
                    "GitHub (Auiowu)": "Auiowu/ManifestAutoUpdate",
                    "GitHub (SAC)": "SteamAutoCracks/ManifestHub"
                }
                
                # Custom sources
                custom_github_repos = backend.get_custom_github_repos()
                custom_zip_repos = backend.get_custom_zip_repos()
                
                # Add custom GitHub repos
                for repo in custom_github_repos:
                    builtin_sources[f"{repo['name']} (自定义GitHub)"] = repo['repo']
                
                # Add custom ZIP repos  
                for repo in custom_zip_repos:
                    builtin_sources[f"{repo['name']} (自定义ZIP)"] = f"custom_zip_{repo['name']}"
                
                return {
                    "success": True,
                    "sources": builtin_sources,
                    "custom_github_count": len(custom_github_repos),
                    "custom_zip_count": len(custom_zip_repos)
                }
        
        result = asyncio.run(_get_sources())
        return jsonify(result)
        
    except Exception as e:
        dummy_backend = CaiBackend()
        message = f"获取清单源失败: {str(e)}"
        dummy_backend.log.error(dummy_backend.stack_error(e))
        return jsonify({"success": False, "message": message})

async def _run_search_game_task(game_name):
    async with CaiBackend() as backend:
        patch_log_for_socketio(backend.log)
        await backend.initialize()
        results = await backend.find_appid_by_name(game_name)
        return results

@app.route('/api/search_game', methods=['POST'])
def search_game():
    data = request.get_json()
    game_name = data.get('game_name', '').strip()
    if not game_name:
        return jsonify({"success": False, "message": "请输入游戏名称。"}), 400
    try:
        results = asyncio.run(_run_search_game_task(game_name))
        return jsonify({"success": True, "games": results})
    except Exception as e:
        dummy_backend = CaiBackend()
        message = f"搜索时发生错误: {e}"
        dummy_backend.log.error(dummy_backend.stack_error(e))
        return jsonify({"success": False, "message": message}), 500

async def _run_unlock_task(app_id, tool_type, use_st_auto_update, add_all_dlc, patch_depot_key):
    async with CaiBackend() as backend:
        patch_log_for_socketio(backend.log)
        TASK_STATE["status"] = "running"
        TASK_STATE["progress"] = []
        TASK_STATE["result"] = None
        unlocker_type = await backend.initialize()
        if not unlocker_type:
            raise Exception("解锁工具类型未能确定，请检查配置或Steam路径。")

        await backend.checkcn()
        if tool_type == "search" or "github" in tool_type.lower() or 'auiowu' in tool_type.lower() or 'steamautocracks' in tool_type.lower():
            # 注意：这里需要排除steamautocracks_v2，因为它不是GitHub仓库
            if tool_type != "steamautocracks_v2" and not await backend.check_github_api_rate_limit():
                raise Exception("GitHub API 请求次数已用尽，无法继续。")
                
        app_id_extracted = backend.extract_app_id(app_id)
        if not app_id_extracted:
            raise Exception(f"无法从 '{app_id}' 中提取有效AppID。请输入有效的AppID或链接。")
            
        if tool_type == "search":
            backend.log.info(f"正在所有 GitHub 仓库中搜索 AppID: {app_id_extracted}...")
            # MODIFIED: Use all repos including custom ones
            results = await backend.search_all_repos_for_appid(app_id_extracted)
            if not results:
                raise Exception(f"在所有 GitHub 仓库中都未找到 AppID {app_id_extracted} 的清单。")
            TASK_STATE["result"] = {
                "success": True, "message": "搜索完成，请选择一个清单源。", "action_required": "select_source",
                "sources": results, "context": {"use_st_auto_update": use_st_auto_update, "add_all_dlc": add_all_dlc, "patch_depot_key": patch_depot_key}
            }
            backend.log.info(f"找到 {len(results)} 个源，请在界面上选择。")
            return
            
        backend.log.info(f"--- 正在使用源 '{tool_type}' 处理 AppID: {app_id_extracted} ---")
        
        # 修改这里：添加steamautocracks_v2到zip_sources列表
        zip_sources = ["printedwaste", "cysaw", "furcate", "assiw", "steamdatabase", "steamautocracks_v2"]
        
        # Check for custom zip sources
        if tool_type.startswith("custom_zip_"):
            success = await backend.process_zip_source(app_id_extracted, tool_type, unlocker_type, use_st_auto_update, add_all_dlc, patch_depot_key)
        elif tool_type in zip_sources:
            success = await backend.process_zip_source(app_id_extracted, tool_type, unlocker_type, use_st_auto_update, add_all_dlc, patch_depot_key)
        else:
            success = await backend.process_github_manifest(app_id_extracted, tool_type, unlocker_type, use_st_auto_update, add_all_dlc, patch_depot_key)
        
        if success:
            TASK_STATE["result"] = {"success": True, "message": f"成功配置 AppID {app_id_extracted}。重启 Steam 后生效。"}
        else:
            raise Exception(f"处理 AppID {app_id_extracted} 失败，请检查日志。")

# Workshop task runner
async def _run_workshop_task(workshop_input, copy_to_config, copy_to_depot):
    async with CaiBackend() as backend:
        patch_log_for_socketio(backend.log)
        TASK_STATE["status"] = "running"
        TASK_STATE["progress"] = []
        TASK_STATE["result"] = None
        
        unlocker_type = await backend.initialize()
        if not unlocker_type:
            raise Exception("后端初始化失败，请检查配置或Steam路径。")
        
        backend.log.info(f"--- 开始处理创意工坊物品: {workshop_input} ---")
        
        success = await backend.process_workshop_item(workshop_input, copy_to_config, copy_to_depot)
        
        if success:
            TASK_STATE["result"] = {"success": True, "message": f"成功处理创意工坊物品。重启 Steam 后生效。"}
        else:
            raise Exception(f"处理创意工坊物品失败，请检查日志。")

@app.route('/api/start_task', methods=['POST'])
def start_task():
    if TASK_STATE["status"] == "running":
        return jsonify({"success": False, "message": "一个任务正在运行中。"})
    data = request.get_json()
    app_id_input = data.get('app_id', '').strip()
    tool_type = data.get('tool_type', 'search')
    use_st_auto_update = data.get('use_st_auto_update', False)
    add_all_dlc = data.get('add_all_dlc', False)
    patch_depot_key = data.get('patch_depot_key', False)  # NEW: 获取depotkey修补参数
    
    if not app_id_input:
        return jsonify({"success": False, "message": "请输入 AppID 或链接。"})
    def task_wrapper():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(_run_unlock_task(app_id_input, tool_type, use_st_auto_update, add_all_dlc, patch_depot_key))
            TASK_STATE["status"] = "completed"
        except Exception as e:
            TASK_STATE["status"] = "error"
            message = f"发生错误: {str(e)}"
            TASK_STATE["result"] = {"success": False, "message": message}
            dummy_backend = CaiBackend()
            patch_log_for_socketio(dummy_backend.log)
            dummy_backend.log.error(dummy_backend.stack_error(e))
        finally:
            if TASK_STATE["status"] == "running":
                TASK_STATE["status"] = "error"
                TASK_STATE["result"] = {"success": False, "message": "任务意外终止。"}
            loop.close()
    thread = threading.Thread(target=task_wrapper, daemon=True)
    thread.start()
    return jsonify({"success": True, "message": "任务已开始。"})

# Workshop task endpoint
@app.route('/api/workshop/start_task', methods=['POST'])
def start_workshop_task():
    if TASK_STATE["status"] == "running":
        return jsonify({"success": False, "message": "一个任务正在运行中。"})
    
    data = request.get_json()
    workshop_input = data.get('workshop_input', '').strip()
    copy_to_config = data.get('copy_to_config', True)
    copy_to_depot = data.get('copy_to_depot', True)
    
    if not workshop_input:
        return jsonify({"success": False, "message": "请输入创意工坊物品链接或ID。"})
    
    if not copy_to_config and not copy_to_depot:
        return jsonify({"success": False, "message": "请至少选择一个目标目录。"})
    
    def task_wrapper():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(_run_workshop_task(workshop_input, copy_to_config, copy_to_depot))
            TASK_STATE["status"] = "completed"
        except Exception as e:
            TASK_STATE["status"] = "error"
            message = f"发生错误: {str(e)}"
            TASK_STATE["result"] = {"success": False, "message": message}
            dummy_backend = CaiBackend()
            patch_log_for_socketio(dummy_backend.log)
            dummy_backend.log.error(dummy_backend.stack_error(e))
        finally:
            if TASK_STATE["status"] == "running":
                TASK_STATE["status"] = "error"
                TASK_STATE["result"] = {"success": False, "message": "任务意外终止。"}
            loop.close()
    
    thread = threading.Thread(target=task_wrapper, daemon=True)
    thread.start()
    return jsonify({"success": True, "message": "创意工坊任务已开始。"})

@app.route('/api/task_status')
def get_task_status():
    return jsonify({"status": TASK_STATE["status"], "progress": TASK_STATE["progress"][-20:], "result": TASK_STATE["result"]})

@app.route('/api/config/detailed')
def get_detailed_config():
    config_path = project_root / 'config.json'
    try:
        config = standard_json.load(open(config_path, 'r', encoding='utf-8')) if config_path.exists() else DEFAULT_CONFIG.copy()
        steam_path_str = config.get("Custom_Steam_Path", "")
        steam_path_is_auto = False
        if not steam_path_str:
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Valve\Steam') as key:
                    steam_path_str, _ = winreg.QueryValueEx(key, 'SteamPath')
                steam_path_is_auto = True
            except Exception: steam_path_str = ""
        return jsonify({"success": True, "config": {
            "github_token": config.get("Github_Personal_Token", ""),
            "steam_path": str(steam_path_str),
            "debug_mode": config.get("debug_mode", False),
            "logging_files": config.get("logging_files", True),
            "steam_path_is_auto": steam_path_is_auto,
            "background_image_path": config.get("background_image_path", ""),
            "background_blur": config.get("background_blur", 0),
            "background_saturation": config.get("background_saturation", 100),
            "background_brightness": config.get("background_brightness", 100),
            "show_console_on_startup": config.get("show_console_on_startup", False),
            "force_unlocker_type": config.get("force_unlocker_type", "auto"),
            # NEW: 添加自定义清单库配置
            "custom_repos": config.get("Custom_Repos", {"github": [], "zip": []}),
        }})
    except Exception as e:
        return jsonify({"success": False, "message": f"加载详细配置失败: {e}"})

@app.route('/api/config/update', methods=['POST'])
def update_config():  # 改为同步函数
    config_path = project_root / 'config.json'
    try:
        data = request.get_json()
        
        # 确保配置文件存在
        if not config_path.exists():
            # 创建默认配置
            config_path.parent.mkdir(exist_ok=True, parents=True)
            with open(config_path, 'w', encoding='utf-8') as f:
                standard_json.dump(DEFAULT_CONFIG, f, indent=2, ensure_ascii=False)
        
        # 读取当前配置
        with open(config_path, 'r', encoding='utf-8') as f:
            current_config = standard_json.load(f)
        
        # 更新所有可能的键
        updatable_keys = [
            "github_token", "steam_path", "debug_mode", "logging_files",
            "background_image_path", "background_blur", "background_saturation", 
            "background_brightness", "show_console_on_startup", "force_unlocker_type"
        ]
        key_map = {
            "github_token": "Github_Personal_Token",
            "steam_path": "Custom_Steam_Path"
        }
        
        for key in updatable_keys:
            if key in data:
                config_key = key_map.get(key, key)
                current_config[config_key] = data[key]

        # 处理自定义清单库配置
        if "custom_repos" in data:
            current_config["Custom_Repos"] = data["custom_repos"]

        # 保存配置
        with open(config_path, 'w', encoding='utf-8') as f:
            standard_json.dump(current_config, f, indent=2, ensure_ascii=False)
        
        print(f"配置已保存到: {config_path}")  # 添加调试日志
        return jsonify({"success": True, "message": "配置已保存。"})
        
    except Exception as e:
        print(f"保存配置失败: {e}")  # 添加错误日志
        return jsonify({"success": False, "message": f"保存配置失败: {e}"})

@app.route('/api/config/reset', methods=['POST'])
def reset_config():  # 改为同步函数
    config_path = project_root / 'config.json'
    try:
        existing_bg_settings = {}
        
        # 保留背景设置
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                current_config = standard_json.load(f)
            bg_keys = ["background_image_path", "background_blur", "background_saturation", "background_brightness"]
            for key in bg_keys:
                if key in current_config:
                    existing_bg_settings[key] = current_config[key]
        
        # 创建新配置
        new_config = DEFAULT_CONFIG.copy()
        new_config.update(existing_bg_settings)
        
        # 确保目录存在
        config_path.parent.mkdir(exist_ok=True, parents=True)
        
        # 保存配置
        with open(config_path, 'w', encoding='utf-8') as f:
            standard_json.dump(new_config, f, indent=2, ensure_ascii=False)
        
        print(f"配置已重置并保存到: {config_path}")  # 添加调试日志
        return jsonify({"success": True, "message": "配置已重置为默认值 (背景设置已保留)。"})
        
    except Exception as e:
        print(f"重置配置失败: {e}")  # 添加错误日志
        return jsonify({"success": False, "message": f"重置配置失败: {e}"})


@app.route('/api/upload_background', methods=['POST'])
def upload_background():
    if 'backgroundFile' not in request.files: return jsonify({"success": False, "message": "未找到文件"}), 400
    file = request.files['backgroundFile']
    if file.filename == '': return jsonify({"success": False, "message": "未选择文件"}), 400
    if file:
        userdata_folder = app.config['USER_DATA_FOLDER']
        userdata_folder.mkdir(exist_ok=True)
        save_path = userdata_folder / f"custom_background{Path(file.filename).suffix}"
        try:
            file.save(save_path)
            return jsonify({"success": True, "path": str(save_path.relative_to(project_root)).replace('\\', '/')})
        except Exception as e:
            return jsonify({"success": False, "message": f"保存文件失败: {e}"}), 500

@app.route('/userdata/<path:filename>')
def serve_userdata(filename): return send_from_directory(app.config['USER_DATA_FOLDER'], filename)

@app.route('/api/steam/restart', methods=['POST'])
def restart_steam():  # 改为同步函数
    try:
        async def _restart():
            async with CaiBackend() as backend:
                await backend.initialize()
                patch_log_for_socketio(backend.log)
                success = backend.restart_steam()
                if success:
                    return {"success": True, "message": "已发送重启 Steam 的指令。这可能需要一些时间。"}
                else:
                    return {"success": False, "message": "重启 Steam 失败，请检查路径配置或日志。"}
        
        result = asyncio.run(_restart())
        return jsonify(result)
        
    except Exception as e:
        dummy_backend = CaiBackend()
        message = f"请求重启Steam时发生后端错误: {str(e)}"
        dummy_backend.log.error(dummy_backend.stack_error(e))
        return jsonify({"success": False, "message": message}), 500
@app.route('/api/console/toggle', methods=['POST'])
def toggle_console():
    if sys.platform != 'win32': return jsonify({"success": False, "message": "此功能仅在Windows上可用。"}), 400
    was_visible = console_manager.is_visible
    console_manager.toggle_console()
    message = "控制台已隐藏。" if was_visible else "控制台已显示。日志将输出到新窗口。"
    return jsonify({"success": True, "message": message, "isVisible": not was_visible})

@socketio.on('connect')
def handle_connect(): emit('response', {"message": "已连接到 Cai Install 服务器"})

@app.route('/api/shutdown', methods=['POST'])
def shutdown():
    print("接收到 HTTP 关闭请求，正在准备关闭服务器...")
    def kill_process():
        time.sleep(0.5)
        os._exit(0)
    threading.Thread(target=kill_process, daemon=True).start()
    return jsonify({"success": True, "message": "服务器正在关闭..."})

if __name__ == '__main__':
    if sys.platform == 'win32':
        try:
            os.system('title ' + 'Cai Install XP Web GUI')
        except:
            pass 
    
    # 只调用一次控制台显示检查
    if sys.platform == 'win32' and should_show_console_on_startup():
        console_manager._show_console()
    
    # 只调用一次端口选择
    port = get_port_from_gui()
    
    print(f"将使用端口: {port}")
    url = f"http://127.0.0.1:{port}"
    def open_browser():
        print("服务器已启动，正在尝试自动打开浏览器...")
        webbrowser.open_new(url)
    print("正在启动 Cai Install Web GUI...")
    print(f"服务器将在 {url} 上运行")
    threading.Timer(1.5, open_browser).start()
    socketio.run(app, host='127.0.0.1', port=port, debug=False, allow_unsafe_werkzeug=True)
