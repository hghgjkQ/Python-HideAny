import tkinter as tk
from tkinter import ttk, StringVar, BooleanVar
import win32gui
import win32con

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

# 运行程序
if __name__ == "__main__":
    app = WindowManager()
    # 可通过 app.is_main_hidden 变量控制主窗口隐藏状态，示例：
    # app.is_main_hidden.set(True)  # 隐藏主窗口
    # app.is_main_hidden.set(False) # 显示主窗口
    app.mainloop()
