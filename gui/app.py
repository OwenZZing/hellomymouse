"""Main application window for Hypothesis Maker."""
from __future__ import annotations
import os
import glob
import threading
import traceback
import datetime
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, font as tkfont

_LOG_PATH = os.path.join(os.path.expanduser('~'), 'HypothesisMaker_debug.log')

def _log(msg: str):
    try:
        with open(_LOG_PATH, 'a', encoding='utf-8') as f:
            f.write(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {msg}\n")
    except Exception:
        pass

from config import load_config, save_config
from gui.widgets import APISelector, FolderSelector, ProgressSection, ProjectSelectorDialog
from analyzer.api_client import APIClient
from analyzer.processor import AnalysisPipeline
from report.docx_builder import build_report


class HypothesisMakerApp:
    VERSION = '1.0'

    def __init__(self):
        _log('=== App start ===')
        self._cfg = load_config()
        self._stage0_result: dict | None = None
        self._output_path: str = ''

        self._root = tk.Tk()
        self._root.title(f'Hypothesis Maker v{self.VERSION}')
        self._root.geometry('600x700')
        self._root.minsize(480, 400)
        self._root.resizable(True, True)
        self._root.protocol('WM_DELETE_WINDOW', self._on_close)

        # ── Normalize fonts & colors via ttk.Style (covers LabelFrame titles etc.) ──
        _FONT  = ('Malgun Gothic', 10)
        _FONTS = ('Malgun Gothic', 10, 'bold')
        _FG    = '#1a1a1a'

        style = ttk.Style(self._root)
        style.configure('.',                   font=_FONT,  foreground=_FG)
        style.configure('TLabel',              font=_FONT,  foreground=_FG)
        style.configure('TButton',             font=_FONT)
        style.configure('TRadiobutton',        font=_FONT,  foreground=_FG)
        style.configure('TCheckbutton',        font=_FONT,  foreground=_FG)
        style.configure('TEntry',              font=_FONT)
        style.configure('TLabelframe',         font=_FONT)
        style.configure('TLabelframe.Label',   font=_FONTS, foreground=_FG)

        # tk named fonts (for tk.Text etc.)
        for name in ('TkDefaultFont', 'TkTextFont', 'TkFixedFont', 'TkMenuFont',
                     'TkHeadingFont', 'TkCaptionFont', 'TkSmallCaptionFont'):
            try:
                tkfont.nametofont(name).configure(family='Malgun Gothic', size=10)
            except Exception:
                pass

        self._build_ui()

    # ── UI construction ───────────────────────────────────────

    def _build_ui(self):
        root = self._root
        # Main scrollable frame
        canvas = tk.Canvas(root, highlightthickness=0)
        scrollbar = ttk.Scrollbar(root, orient='vertical', command=canvas.yview)
        self._scroll_frame = ttk.Frame(canvas)

        self._scroll_frame.bind('<Configure>',
            lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        win_id = canvas.create_window((0, 0), window=self._scroll_frame, anchor='nw')
        canvas.configure(yscrollcommand=scrollbar.set)
        # Make inner frame fill canvas width when window is resized
        canvas.bind('<Configure>',
            lambda e: canvas.itemconfig(win_id, width=e.width))

        canvas.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # Mousewheel scroll — bind globally but only scroll main canvas
        # (Using bind_all on root is intentional; dialogs must NOT override this)
        self._main_canvas = canvas
        root.bind_all('<MouseWheel>', self._on_mousewheel)

        f = self._scroll_frame
        pad = {'padx': 10, 'pady': 4, 'fill': 'x'}

        # Title
        title_frame = ttk.Frame(f)
        title_frame.pack(fill='x', padx=10, pady=(12, 2))
        ttk.Label(title_frame, text='🔬 Hypothesis Maker',
                  font=('Segoe UI', 14, 'bold'), foreground='#1a1a1a').pack(side='left')
        ttk.Label(title_frame, text=f'v{self.VERSION}  — Research Starter Kit Generator',
                  foreground='gray', font=('Segoe UI', 9)).pack(side='left', padx=8)

        ttk.Separator(f, orient='horizontal').pack(fill='x', padx=10, pady=4)

        # API settings
        self._api_sel = APISelector(f, self._cfg)
        self._api_sel.pack(**pad)

        # Lab papers folder
        self._folder_sel = FolderSelector(f, '② 연구실 논문 폴더 (PDF)', 'last_folder', self._cfg)
        self._folder_sel.pack(**pad)

        # Reference papers folder
        self._ref_sel = FolderSelector(f, '③ 추가 참조 논문 폴더 — 선택사항 (교수님 추천 논문 등)',
                                       'last_ref_folder', self._cfg)
        self._ref_sel.pack(**pad)

        # Stage 0 button
        stage0_frame = ttk.LabelFrame(f, text='④ 연구실 프로젝트 파악 (Stage 0)', padding=10)
        stage0_frame.pack(**pad)
        ttk.Label(stage0_frame,
                  text='논문 제목·초록만 빠르게 읽어 연구실의 프로젝트 목록을 파악합니다.',
                  foreground='gray', font=('Malgun Gothic', 9)).pack(anchor='w')
        self._stage0_btn = ttk.Button(stage0_frame, text='🔍  프로젝트 목록 파악',
                                      command=self._run_stage0)
        self._stage0_btn.pack(anchor='w', pady=(6, 0))
        self._project_label = ttk.Label(stage0_frame, text='', foreground='#0057a0', font=('Malgun Gothic', 9))
        self._project_label.pack(anchor='w', pady=(2, 0))

        # Assigned project
        assign_frame = ttk.LabelFrame(f, text='⑤ 배정된 프로젝트 (선택사항)', padding=10)
        assign_frame.pack(**pad)
        ttk.Label(assign_frame,
                  text='교수님이 배정하신 프로젝트 이름을 입력하거나, 위에서 파악한 목록에서 선택하세요.',
                  foreground='gray', font=('Malgun Gothic', 9)).pack(anchor='w')
        assign_row = ttk.Frame(assign_frame)
        assign_row.pack(fill='x', pady=(4, 0))
        self._assigned_var = tk.StringVar(value='')
        ttk.Entry(assign_row, textvariable=self._assigned_var, width=30).pack(side='left', padx=(0, 6))
        self._select_proj_btn = ttk.Button(assign_row, text='목록에서 선택',
                                           command=self._open_project_selector,
                                           state='disabled')
        self._select_proj_btn.pack(side='left')

        # Professor instructions
        prof_frame = ttk.LabelFrame(f, text='⑥ 교수님 지시사항 — 선택사항', padding=10)
        prof_frame.pack(**pad)
        ttk.Label(prof_frame,
                  text='교수님이 추가로 말씀하신 내용을 자유롭게 입력하세요.\n예) "이 분야에서 X 방법론도 같이 보면 좋겠다", "Y 논문 꼭 참고해", 특정 방향 등',
                  foreground='gray', font=('Malgun Gothic', 9)).pack(anchor='w')
        self._prof_text = tk.Text(prof_frame, height=3, font=('Malgun Gothic', 10), relief='solid', bd=1)
        self._prof_text.pack(fill='x', pady=(4, 0))

        # Analyze button
        analyze_frame = ttk.LabelFrame(f, text='⑦ 분석 시작', padding=10)
        analyze_frame.pack(**pad)
        self._analyze_btn = ttk.Button(analyze_frame, text='▶  분석 시작 (Stage 1 + 2)',
                                       command=self._run_analysis)
        self._analyze_btn.pack(fill='x')
        ttk.Label(analyze_frame,
                  text='논문 수에 따라 3~10분 소요됩니다. API 비용이 발생합니다.',
                  foreground='gray', font=('Malgun Gothic', 9)).pack(anchor='w', pady=(4, 0))

        # Progress
        self._progress = ProgressSection(f)
        self._progress.pack(padx=10, pady=4, fill='both', expand=True)

        # Output
        out_frame = ttk.LabelFrame(f, text='⑧ 저장 위치 및 완료', padding=10)
        out_frame.pack(**pad)
        out_row = ttk.Frame(out_frame)
        out_row.pack(fill='x', pady=(0, 6))
        self._out_var = tk.StringVar(value=self._cfg.get('last_output', ''))
        ttk.Entry(out_row, textvariable=self._out_var).pack(side='left', fill='x', expand=True, padx=(0, 4))
        ttk.Button(out_row, text='저장 위치', command=self._choose_output).pack(side='left')

        btn_row = ttk.Frame(out_frame)
        btn_row.pack(fill='x')
        self._gen_btn = ttk.Button(btn_row, text='📄  리포트 생성', command=self._save_report,
                                   state='disabled')
        self._gen_btn.pack(side='left', padx=(0, 6))
        self._open_btn = ttk.Button(btn_row, text='📂  파일 열기', command=self._open_file,
                                    state='disabled')
        self._open_btn.pack(side='left')

        # Review (optional)
        review_frame = ttk.LabelFrame(f, text='⑨ 리뷰 — 선택사항 (리포트 마지막 페이지에 삽입됩니다)', padding=10)
        review_frame.pack(**pad)
        ttk.Label(review_frame,
                  text='이름, 연구 분야, 별점, 한줄평을 남기면 Word 파일 마지막에 기록됩니다.',
                  foreground='gray', font=('Malgun Gothic', 9)).pack(anchor='w')

        row1 = ttk.Frame(review_frame)
        row1.pack(fill='x', pady=(6, 2))
        ttk.Label(row1, text='이름').pack(side='left')
        self._review_name = tk.StringVar()
        ttk.Entry(row1, textvariable=self._review_name, width=16).pack(side='left', padx=(4, 14))
        ttk.Label(row1, text='연구 분야').pack(side='left')
        self._review_field = tk.StringVar()
        ttk.Entry(row1, textvariable=self._review_field, width=20).pack(side='left', padx=(4, 0))

        row2 = ttk.Frame(review_frame)
        row2.pack(fill='x', pady=(2, 2))
        ttk.Label(row2, text='별점').pack(side='left')
        self._review_stars = tk.IntVar(value=0)
        for i in range(1, 6):
            ttk.Radiobutton(row2, text=f'★{i}', variable=self._review_stars, value=i).pack(side='left', padx=2)
        ttk.Radiobutton(row2, text='없음', variable=self._review_stars, value=0).pack(side='left', padx=(8, 0))

        ttk.Label(review_frame, text='한줄평').pack(anchor='w', pady=(4, 0))
        self._review_comment = tk.Text(review_frame, height=2, font=('Malgun Gothic', 10), relief='solid', bd=1)
        self._review_comment.pack(fill='x', pady=(2, 0))

        # Attribution footer
        ttk.Separator(f, orient='horizontal').pack(fill='x', padx=10, pady=(8, 2))
        ttk.Label(f, text='Made by @hellomymouse  ·  kby930@gmail.com',
                  foreground='#aaaaaa', font=('Malgun Gothic', 8)).pack(pady=(0, 8))

    # ── Helpers ───────────────────────────────────────────────

    def _get_pdf_paths(self, folder: str) -> list[str]:
        if not folder or not os.path.isdir(folder):
            return []
        # recursive=True already includes root folder — no need to add '*.pdf' separately
        return sorted(set(glob.glob(os.path.join(folder, '**', '*.pdf'), recursive=True)))

    def _make_api_client(self) -> APIClient:
        provider = self._api_sel.provider
        key = self._api_sel.api_key
        model = self._api_sel.model
        if not key:
            raise ValueError('API Key를 입력하세요.')
        return APIClient(provider, key, model)

    def _update_progress(self, msg: str, pct: int):
        self._root.after(0, lambda: self._progress.update(msg, pct))

    def _on_mousewheel(self, event):
        self._main_canvas.yview_scroll(int(-1 * (event.delta / 120)), 'units')

    def _set_buttons_state(self, running: bool):
        state = 'disabled' if running else 'normal'
        self._stage0_btn.config(state=state)
        self._analyze_btn.config(state=state)

    # ── Stage 0 ───────────────────────────────────────────────

    def _run_stage0(self):
        _log('Stage0 button clicked')
        folder = self._folder_sel.path
        _log(f'folder={folder!r}')
        if not folder:
            messagebox.showwarning('폴더 필요', '연구실 논문 폴더를 선택하세요.')
            return
        pdfs = self._get_pdf_paths(folder)
        _log(f'pdfs found={len(pdfs)}')
        if not pdfs:
            messagebox.showwarning('PDF 없음', f'선택한 폴더에 PDF 파일이 없습니다.\n{folder}')
            return

        try:
            _log('creating API client...')
            client = self._make_api_client()
            _log(f'API client OK: provider={client.provider} model={client.model}')
        except Exception as e:
            _log(f'API client error: {e}\n{traceback.format_exc()}')
            messagebox.showerror('API 오류', str(e))
            return

        self._set_buttons_state(True)
        self._progress.reset()
        self._stage0_result = None
        self._select_proj_btn.config(state='disabled')
        self._project_label.config(text='')

        def task():
            try:
                _log('stage0 thread started')
                pipeline = AnalysisPipeline(client, self._update_progress)
                result = pipeline.run_stage0(pdfs)
                self._stage0_result = result
                projects = result.get('projects', [])
                lab_name = result.get('lab_name_guess', '')
                _log(f'stage0 done: {len(projects)} projects')
                self._root.after(0, lambda: self._on_stage0_done(projects, lab_name))
            except Exception as e:
                _log(f'stage0 thread error: {e}\n{traceback.format_exc()}')
                self._root.after(0, lambda: self._on_error(str(e)))

        threading.Thread(target=task, daemon=True).start()

    def _on_stage0_done(self, projects: list[dict], lab_name: str):
        try:
            _log(f'_on_stage0_done called: {len(projects)} projects')
            self._set_buttons_state(False)
            self._select_proj_btn.config(state='normal')
            n = len(projects)
            names = ', '.join(p.get('name', '') for p in projects[:3])
            label_text = f'[완료] {n}개 프로젝트: {names}' + ('...' if n > 3 else '')
            self._project_label.config(text=label_text)
            self._progress.update(f'Stage 0 완료 — {n}개 프로젝트 파악', 100)
            _log('_on_stage0_done: UI updated OK')
            messagebox.showinfo('Stage 0 완료',
                                f'{n}개 프로젝트를 파악했습니다.\n\n'
                                + '\n'.join(f'• {p.get("name","")}' for p in projects)
                                + '\n\n"목록에서 선택" 또는 직접 입력 후 ⑦ 분석 시작을 눌러주세요.')
        except Exception as e:
            _log(f'_on_stage0_done error: {e}\n{traceback.format_exc()}')
            messagebox.showerror('오류', f'완료 처리 중 오류:\n{e}')

    def _open_project_selector(self):
        if not self._stage0_result:
            messagebox.showinfo('먼저 실행', '"프로젝트 목록 파악"을 먼저 실행하세요.')
            return
        projects = self._stage0_result.get('projects', [])
        lab_name = self._stage0_result.get('lab_name_guess', '')
        dialog = ProjectSelectorDialog(self._root, projects, lab_name)
        self._root.wait_window(dialog)
        if dialog.result is not None:
            self._assigned_var.set(dialog.result)

    # ── Analysis ──────────────────────────────────────────────

    def _run_analysis(self):
        folder = self._folder_sel.path
        if not folder:
            messagebox.showwarning('폴더 필요', '연구실 논문 폴더를 선택하세요.')
            return
        lab_pdfs = self._get_pdf_paths(folder)
        if not lab_pdfs:
            messagebox.showwarning('PDF 없음', '선택한 폴더에 PDF 파일이 없습니다.')
            return

        ref_pdfs = self._get_pdf_paths(self._ref_sel.path)
        assigned = self._assigned_var.get().strip()
        prof_instructions = self._prof_text.get('1.0', 'end').strip()

        try:
            client = self._make_api_client()
        except Exception as e:
            messagebox.showerror('API 오류', str(e))
            return

        # Confirm cost warning
        total = len(lab_pdfs) + len(ref_pdfs)
        if not messagebox.askyesno('분석 시작',
                                   f'논문 {total}편을 분석합니다.\n'
                                   f'API 비용이 발생하며 3~10분 소요됩니다.\n\n계속할까요?'):
            return

        self._set_buttons_state(True)
        self._gen_btn.config(state='disabled')
        self._open_btn.config(state='disabled')
        self._progress.reset()
        self._report_data: dict | None = None

        def task():
            try:
                pipeline = AnalysisPipeline(client, self._update_progress)
                result = pipeline.run_full_analysis(lab_pdfs, ref_pdfs, assigned, prof_instructions)
                self._report_data = result
                self._root.after(0, self._on_analysis_done)
            except Exception as e:
                self._root.after(0, lambda: self._on_error(str(e)))

        threading.Thread(target=task, daemon=True).start()

    def _on_analysis_done(self):
        self._set_buttons_state(False)
        self._gen_btn.config(state='normal')
        self._update_progress('✅ 분석 완료! "리포트 생성" 버튼을 클릭하세요.', 100)
        messagebox.showinfo('분석 완료', '분석이 완료되었습니다.\n"리포트 생성" 버튼으로 Word 파일을 만드세요.')

    # ── Report ────────────────────────────────────────────────

    def _choose_output(self):
        init_dir = self._out_var.get() or os.path.expanduser('~')
        if os.path.isfile(init_dir):
            init_dir = os.path.dirname(init_dir)
        path = filedialog.asksaveasfilename(
            initialdir=init_dir,
            initialfile='Research_Starter_Kit.docx',
            defaultextension='.docx',
            filetypes=[('Word Document', '*.docx')],
        )
        if path:
            self._out_var.set(path)

    def _save_report(self):
        if not hasattr(self, '_report_data') or self._report_data is None:
            messagebox.showwarning('먼저 분석', '먼저 분석을 실행하세요.')
            return

        out_path = self._out_var.get().strip()
        if not out_path:
            self._choose_output()
            out_path = self._out_var.get().strip()
        if not out_path:
            return

        review = {
            'name':    self._review_name.get().strip(),
            'field':   self._review_field.get().strip(),
            'stars':   self._review_stars.get(),
            'comment': self._review_comment.get('1.0', 'end').strip(),
        }

        try:
            build_report(self._report_data, out_path, review=review)
            self._output_path = out_path
            self._open_btn.config(state='normal')
            self._cfg['last_output'] = out_path
            save_config(self._cfg)
            messagebox.showinfo('완료', f'리포트가 저장되었습니다.\n{out_path}')
        except PermissionError:
            messagebox.showerror('파일 열림', f'파일이 이미 열려 있습니다. Word를 닫고 다시 시도하세요.\n{out_path}')
        except Exception as e:
            messagebox.showerror('저장 실패', str(e))

    def _open_file(self):
        if self._output_path and os.path.exists(self._output_path):
            os.startfile(self._output_path)
        else:
            messagebox.showwarning('파일 없음', '먼저 리포트를 생성하세요.')

    # ── Error handling ────────────────────────────────────────

    def _on_error(self, msg: str):
        self._set_buttons_state(False)
        self._update_progress(f'❌ 오류: {msg}', 0)
        messagebox.showerror('오류 발생', msg)

    # ── Lifecycle ─────────────────────────────────────────────

    def _on_close(self):
        self._api_sel.save_to_cfg(self._cfg)
        self._folder_sel.save_to_cfg(self._cfg)
        self._ref_sel.save_to_cfg(self._cfg)
        save_config(self._cfg)
        self._root.destroy()

    def run(self):
        self._root.mainloop()
