import win32gui
import win32con
import time,keyboard
import pygame
import threading
import os
import win32event, win32api
import tkinter as tk
from tkinter import ttk, StringVar, BooleanVar
import winerror  # 包含ERROR_ALREADY_EXISTS常量
import sys  # 新增：原代码使用sys.exit但未导入

# 1. 自定义窗口控制按钮（子控件）
class WindowControlBtn(tk.Button):
    def __init__(self, parent, hwnd, title, is_hidden, **kwargs):
        super().__init__(parent, **kwargs)
        self.hwnd = hwnd
        self.title = title
        self.is_hidden = is_hidden  # 窗口是否隐藏
        self.match_score = 0  # 搜索匹配度（用于排序）

        # 初始化样式
        self._update_style()
        self.config(
            text=self.title[:30],  # 标题截断
            width=40,
            command=self.toggle_window
        )

    def _update_style(self):
        """更新按钮样式：未隐藏=默认，隐藏=红色"""
        if self.is_hidden:
            self.config(bg="#ff0000", fg="#ffffff", relief=tk.RAISED)
        else:
            self.config(bg=tk.Button().cget("bg"), fg="#000000", relief=tk.RAISED)

    def toggle_window(self):
        """切换窗口显隐 + 更新样式"""
        if self.is_hidden:
            win32gui.ShowWindow(self.hwnd, win32con.SW_SHOW)
            self.is_hidden = False
        else:
            win32gui.ShowWindow(self.hwnd, win32con.SW_HIDE)
            self.is_hidden = True
        self._update_style()
        self.update()

    def calc_match_score(self, keyword):
        """计算搜索匹配度：关键词越靠前/越完整，分数越高"""
        if not keyword:
            self.match_score = 100  # 无关键词默认高分
            return
        keyword = keyword.lower()
        title_lower = self.title.lower()
        if keyword in title_lower:
            # 匹配位置越靠前，分数越高
            self.match_score = 100 - title_lower.index(keyword)
        else:
            self.match_score = 0  # 不匹配分数为0

# 2. 主窗口类（含搜索、排序、隐藏控制）
class WindowManager(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("窗口控制器（搜索+排序+隐藏控制）")
        self.geometry("450x600")
        self.resizable(True, True)

        # 绑定窗口关闭事件（核心修改：捕获右上角X按钮的点击）
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        # -------- 核心变量 --------
        # 控制主窗口是否隐藏（tk自带变量）
        self.is_main_hidden = BooleanVar(value=False)
        # 搜索关键词变量
        self.search_var = StringVar(value="")
        # 存储所有按钮控件
        self.all_btns = []

        # -------- UI布局 --------
        # 1. 顶部控制区（刷新+搜索+主窗口隐藏按钮）
        self._create_top_bar()

        # 2. 滚动区域（按钮列表）
        self._create_scrollable_frame()

        # -------- 初始化 --------
        # 绑定搜索框回车事件
        self.search_var.trace_add("write", lambda *args: self.refresh_windows())
        # 首次刷新
        self.refresh_windows()

    def on_closing(self):
        """自定义窗口关闭逻辑：清理资源并退出整个程序"""
        # 1. 停止keyboard的按键监听（避免后台线程残留）
        keyboard.unhook_all()
        # 2. 退出pygame混音器（释放音频资源）
        pygame.mixer.quit()
        # 3. 销毁tkinter窗口
        self.destroy()
        # 4. 强制退出整个程序（确保无残留）
        sys.exit(0)

    def _create_top_bar(self):
        """创建顶部控制栏（刷新+搜索+主窗口隐藏按钮）"""
        top_frame = tk.Frame(self)
        top_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=10)

        # 刷新按钮
        refresh_btn = tk.Button(top_frame, text="刷新", command=self.refresh_windows)
        refresh_btn.pack(side=tk.LEFT, padx=5)

        # 主窗口隐藏/显示按钮（绑定控制变量）
        hide_main_btn = tk.Button(
            top_frame,
            text="隐藏主窗口",
            command=self.toggle_main_window
        )
        hide_main_btn.pack(side=tk.LEFT, padx=5)

        # 搜索框
        search_label = tk.Label(top_frame, text="搜索：")
        search_label.pack(side=tk.LEFT, padx=5)
        search_entry = tk.Entry(top_frame, textvariable=self.search_var, width=20)
        search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

    def _create_scrollable_frame(self):
        """创建带滚动条的按钮区域"""
        # 滚动条
        self.scrollbar = ttk.Scrollbar(self, orient=tk.VERTICAL)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 画布
        self.canvas = tk.Canvas(self, yscrollcommand=self.scrollbar.set, bg="#f0f0f0")
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.scrollbar.config(command=self.canvas.yview)

        # 按钮容器
        self.btn_frame = tk.Frame(self.canvas)
        self.canvas.create_window((0, 0), window=self.btn_frame, anchor=tk.NW)
        self.btn_frame.bind("<Configure>", lambda e: self.canvas.configure(
            scrollregion=self.canvas.bbox("all")
        ))

    def toggle_main_window(self):
        """控制主窗口隐藏/显示（绑定核心变量）"""
        if self.is_main_hidden.get():
            # 隐藏 → 显示
            self.deiconify()  # tk显示窗口
            self.is_main_hidden.set(False)
        else:
            # 显示 → 隐藏
            self.withdraw()  # tk隐藏窗口
            self.is_main_hidden.set(True)

    def refresh_windows(self):
        """刷新窗口列表：过滤+排序（未隐藏置顶+匹配度排序）"""
        # 清空旧按钮
        for btn in self.all_btns:
            btn.destroy()
        self.all_btns.clear()

        # 1. 枚举所有有标题的窗口，创建按钮
        def enum_windows(hwnd, extra):
            title = win32gui.GetWindowText(hwnd)
            if not title:
                return True
            is_hidden = not win32gui.IsWindowVisible(hwnd)
            # 创建按钮并计算匹配度
            btn = WindowControlBtn(self.btn_frame, hwnd, title, is_hidden)
            btn.calc_match_score(self.search_var.get())
            self.all_btns.append(btn)
            return True
        win32gui.EnumWindows(enum_windows, None)

        # 2. 排序：
        # 规则1：未隐藏按钮（非红色）排在前面
        # 规则2：同状态下按搜索匹配度降序排列
        self.all_btns.sort(key=lambda x: (x.is_hidden, -x.match_score))

        # 3. 渲染排序后的按钮
        for btn in self.all_btns:
            btn.pack(side=tk.TOP, fill=tk.X, padx=5, pady=2)

def press(x):
    global 模式,输入,login
    if x.name=='o':
        if keyboard.is_pressed('shift'):
            if 模式:
                模式=False
                if 输入==login:
                    app.deiconify()
            else:
                模式=True
    if 模式:
        if x.name in '1234567890':
            play_mp3_async(float(f'0.{x.name}')+0.1)
            输入+=x.name
    else:
        输入=''

def play_mp3_async(volume=1.0):
    """
    多线程非阻塞播放a.mp3
    :param volume: 播放音量（0.0~1.0）
    """
    def _play():
        # 自动找空闲声道（支持同时播放多次，实现多线程效果）
        channel = pygame.mixer.find_channel()
        if channel:
            channel.set_volume(volume)
            channel.play(audio_sound)
    
    # 启动后台线程播放，主线程不阻塞
    play_thread = threading.Thread(target=_play, daemon=True)
    play_thread.start()

def hide_window(handle: int):
    """隐藏指定句柄的窗口"""
    if handle != 0:
        win32gui.ShowWindow(handle, win32con.SW_HIDE)

def show_window(handle: int):
    """恢复显示指定句柄的窗口"""
    if handle != 0:
        win32gui.ShowWindow(handle, win32con.SW_SHOW)

if __name__ == "__main__":
    # 核心逻辑：创建全局互斥体，检测是否已存在实例
    mutex = win32event.CreateMutex(None, True, "3DHghgjkLock-0001")

    if win32api.GetLastError() == winerror.ERROR_ALREADY_EXISTS:
        win32api.MessageBox(0, "程序已运行！", "提示", 0)
        win32api.CloseHandle(mutex)
        sys.exit(1)  
    try:
        login='818925'
        # 初始化pygame混音器（仅需初始化一次）
        pygame.mixer.init(frequency=44100, size=-16, channels=16, buffer=512)
        # 预加载a.mp3（避免重复读取文件，提升播放效率）
        try:
            audio_sound = pygame.mixer.Sound("a.mp3")
        except Exception as e:
            raise FileNotFoundError(f"无法加载a.mp3：{e}，请确认文件路径正确")

        模式=False
        输入=''
        keyboard.on_press(press)
        app = WindowManager()
        app.mainloop()
    finally:
        win32api.CloseHandle(mutex)
        sys.exit(0)
