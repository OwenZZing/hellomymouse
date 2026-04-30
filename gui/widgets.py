"""Custom tkinter widgets for Hypothesis Maker."""
from __future__ import annotations
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from config import DEFAULT_MODELS, MODEL_OPTIONS, get_api_key


class APISelector(ttk.LabelFrame):
    """API provider selection + key input."""

    def __init__(self, parent, cfg: dict, **kwargs):
        super().__init__(parent, text='① API 설정', padding=10, **kwargs)

        self._cfg = cfg
        self._show_key = False

        # Provider radio buttons
        self._provider = tk.StringVar(value=cfg.get('api_provider', 'claude'))
        radio_frame = ttk.Frame(self)
        radio_frame.pack(fill='x', pady=(0, 6))
        for label, val in [('Claude (Anthropic)', 'claude'),
                            ('OpenAI (GPT)', 'openai'),
                            ('Google Gemini', 'gemini'),
                            ('OpenRouter (Free)', 'openrouter')]:
            ttk.Radiobutton(radio_frame, text=label, variable=self._provider,
                            value=val, command=self._on_provider_change).pack(side='left', padx=8)

        # API Key row
        key_frame = ttk.Frame(self)
        key_frame.pack(fill='x', pady=2)
        ttk.Label(key_frame, text='API Key:', width=10).pack(side='left')
        initial_key = cfg.get('api_key') or get_api_key(self._provider.get())
        self._key_var = tk.StringVar(value=initial_key)
        self._key_entry = ttk.Entry(key_frame, textvariable=self._key_var, show='●', width=36)
        self._key_entry.pack(side='left', padx=(0, 4))
        self._eye_btn = ttk.Button(key_frame, text='👁', width=3, command=self._toggle_key_vis)
        self._eye_btn.pack(side='left')

        # Model row
        model_frame = ttk.Frame(self)
        model_frame.pack(fill='x', pady=2)
        ttk.Label(model_frame, text='Model:', width=10).pack(side='left')
        self._model_var = tk.StringVar(value=cfg.get('model', ''))
        self._model_combo = ttk.Combobox(model_frame, textvariable=self._model_var, width=34)
        self._model_combo.pack(side='left')
        self._on_provider_change()

    def _toggle_key_vis(self):
        self._show_key = not self._show_key
        self._key_entry.config(show='' if self._show_key else '●')

    def _on_provider_change(self):
        provider = self._provider.get()
        options = MODEL_OPTIONS.get(provider, [])
        default = DEFAULT_MODELS.get(provider, '')
        self._model_combo['values'] = options
        # 현재 값이 목록에 없으면 기본값으로 초기화
        if self._model_var.get() not in options:
            self._model_var.set(default)
        # provider 전환 시 해당 provider 저장된 키를 로드 (빈 값이면 비워둠)
        if hasattr(self, '_key_var'):
            stored = get_api_key(provider)
            self._key_var.set(stored)

    @property
    def provider(self) -> str:
        return self._provider.get()

    @property
    def api_key(self) -> str:
        return self._key_var.get().strip()

    @property
    def model(self) -> str:
        return self._model_var.get().strip()

    def save_to_cfg(self, cfg: dict):
        cfg['api_provider'] = self.provider
        cfg['api_key'] = self.api_key
        cfg['model'] = self.model


class FolderSelector(ttk.LabelFrame):
    """Folder path selector with Browse button."""

    def __init__(self, parent, label: str, cfg_key: str, cfg: dict, **kwargs):
        super().__init__(parent, text=label, padding=10, **kwargs)
        self._cfg_key = cfg_key
        self._cfg = cfg

        row = ttk.Frame(self)
        row.pack(fill='x')
        self._path_var = tk.StringVar(value=cfg.get(cfg_key, ''))
        ttk.Entry(row, textvariable=self._path_var).pack(side='left', fill='x', expand=True, padx=(0, 4))
        ttk.Button(row, text='찾기', command=self._browse).pack(side='left')

    def _browse(self):
        path = filedialog.askdirectory(initialdir=self._path_var.get() or '~')
        if path:
            self._path_var.set(path)

    @property
    def path(self) -> str:
        return self._path_var.get().strip()

    def save_to_cfg(self, cfg: dict):
        cfg[self._cfg_key] = self.path


class ProgressSection(ttk.LabelFrame):
    """Progress bar + scrollable log area."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, text='진행 상황', padding=10, **kwargs)

        self._pct_var = tk.IntVar(value=0)
        self._bar = ttk.Progressbar(self, variable=self._pct_var, maximum=100, length=400)
        self._bar.pack(fill='x', pady=(0, 4))

        self._pct_label = ttk.Label(self, text='대기 중', foreground='gray')
        self._pct_label.pack(anchor='w')

        log_frame = ttk.Frame(self)
        log_frame.pack(fill='both', expand=True, pady=(4, 0))
        self._log = tk.Text(log_frame, height=8, state='disabled',
                            font=('Malgun Gothic', 9), bg='#1e1e1e', fg='#d4d4d4',
                            relief='flat', wrap='word')
        scrollbar = ttk.Scrollbar(log_frame, orient='vertical', command=self._log.yview)
        self._log.configure(yscrollcommand=scrollbar.set)
        self._log.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

    def update(self, message: str, percent: int):
        self._pct_var.set(percent)
        self._pct_label.config(text=f'{percent}%  {message}')
        self._log.config(state='normal')
        self._log.insert('end', f'{message}\n')
        self._log.see('end')
        self._log.config(state='disabled')

    def reset(self):
        self._pct_var.set(0)
        self._pct_label.config(text='대기 중')
        self._log.config(state='normal')
        self._log.delete('1.0', 'end')
        self._log.config(state='disabled')


class ProjectSelectorDialog(tk.Toplevel):
    """
    Shows detected projects as radio buttons.
    User selects their assigned project (or 'none').
    """

    def __init__(self, parent, projects: list[dict], lab_name: str = ''):
        super().__init__(parent)
        self.title('프로젝트 선택')
        self.resizable(True, True)
        self.minsize(420, 300)
        self.grab_set()  # modal

        self.result: str = ''
        self._custom_var = tk.StringVar()
        self._choice = tk.StringVar(value='__none__')

        # Header (fixed, outside scroll)
        ttk.Label(self, text=f'{"[" + lab_name + "] " if lab_name else ""}AI가 파악한 연구실 프로젝트입니다.',
                  font=('Malgun Gothic', 10, 'bold'), padding=(10, 10, 10, 4)).pack(anchor='w')
        ttk.Label(self, text='교수님이 배정하신 프로젝트를 선택하세요. 없으면 "전체 분석"을 선택하세요.',
                  padding=(10, 0, 10, 6), foreground='gray').pack(anchor='w')

        # Scrollable middle area
        canvas = tk.Canvas(self, highlightthickness=0)
        sb = ttk.Scrollbar(self, orient='vertical', command=canvas.yview)
        scroll_frame = ttk.Frame(canvas)
        scroll_frame.bind('<Configure>',
                          lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        win_id = canvas.create_window((0, 0), window=scroll_frame, anchor='nw')
        canvas.configure(yscrollcommand=sb.set)
        canvas.bind('<Configure>', lambda e: canvas.itemconfig(win_id, width=e.width))
        # Bind scroll only to this dialog's widgets — do NOT use bind_all
        _scroll = lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), 'units')
        canvas.bind('<MouseWheel>', _scroll)
        scroll_frame.bind('<MouseWheel>', _scroll)
        self.bind('<MouseWheel>', _scroll)
        canvas.pack(side='left', fill='both', expand=True, padx=(14, 0), pady=4)
        sb.pack(side='right', fill='y')

        frame = scroll_frame

        # None option
        ttk.Radiobutton(frame, text='🔍 배정 프로젝트 없음 — 전체 프로젝트 고르게 분석',
                        variable=self._choice, value='__none__',
                        command=self._on_choice).pack(anchor='w', pady=3)
        ttk.Separator(frame, orient='horizontal').pack(fill='x', pady=6)

        for proj in projects:
            pid = str(proj.get('id', ''))
            pname = proj.get('name', f'Project {pid}')
            pdesc = proj.get('description', '')

            rb_frame = ttk.Frame(frame)
            rb_frame.pack(anchor='w', pady=2, fill='x')
            ttk.Radiobutton(rb_frame, text=f'  {pname}',
                            variable=self._choice, value=pname,
                            command=self._on_choice).pack(anchor='w')
            if pdesc:
                ttk.Label(rb_frame, text=f'     {pdesc}',
                          foreground='gray', font=('Malgun Gothic', 9),
                          wraplength=380).pack(anchor='w')

        ttk.Separator(frame, orient='horizontal').pack(fill='x', pady=6)

        # Custom input
        custom_frame = ttk.Frame(frame)
        custom_frame.pack(anchor='w', fill='x')
        ttk.Radiobutton(custom_frame, text='✏  직접 입력:',
                        variable=self._choice, value='__custom__',
                        command=self._on_choice).pack(side='left')
        self._custom_entry = ttk.Entry(custom_frame, textvariable=self._custom_var, width=30)
        self._custom_entry.pack(side='left', padx=4, fill='x', expand=True)

        # Buttons (fixed bottom)
        btn_frame = ttk.Frame(self, padding=10)
        btn_frame.pack(fill='x')
        ttk.Button(btn_frame, text='확인', command=self._confirm).pack(side='right', padx=4)
        ttk.Button(btn_frame, text='취소', command=self.destroy).pack(side='right')

        # Size: fit content but cap at 600×500
        self.update_idletasks()
        w = min(self.winfo_reqwidth() + 20, 600)
        h = min(self.winfo_reqheight() + 20, 500)
        x = parent.winfo_rootx() + 50
        y = parent.winfo_rooty() + 50
        self.geometry(f'{w}x{h}+{x}+{y}')

    def _on_choice(self):
        if self._choice.get() == '__custom__':
            self._custom_entry.focus()

    def _confirm(self):
        choice = self._choice.get()
        if choice == '__none__':
            self.result = ''
        elif choice == '__custom__':
            self.result = self._custom_var.get().strip()
        else:
            self.result = choice
        self.destroy()
