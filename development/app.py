"""python development/app.py — 기본값은 모의 모드이며 설치하지 않는다."""
import argparse
import queue
import threading
import tkinter as tk
from tkinter import messagebox, ttk
from pathlib import Path
from installone.core import Store, VERSION, interpret, execute_job, validate_plan
from installone.executors import MockExecutor, SSHExecutor, load_targets
from installone.tk_runtime import prepare_tk

ROOT = Path(__file__).resolve().parent


class App:
    def __init__(self, root, *, real=False, interpreter="mock", db=None):
        self.root = root
        self.real = real
        self.interpreter = interpreter
        self.targets = load_targets(ROOT / "local.json") if real else {"1": {}, "2": {}}
        self.store = Store(db or ROOT / "data" / ("real.db" if real else "mock.db"))
        self.executor = SSHExecutor(self.targets) if real else MockExecutor()
        self.events = queue.Queue()
        self.busy = False
        root.title("InstallONE · 소선웅 개인 프로토타입")
        root.geometry("1080x650")
        root.minsize(850, 500)
        frame = ttk.Frame(root, padding=20)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="InstallONE | Python 실습환경", font=("맑은 고딕", 18, "bold")).pack(anchor="w")
        mode = "실제 SSH 설치 (VM 미검증)" if real else "모의 실행 — 실제 PC 변경 없음 · 2번은 연결 실패 시나리오"
        ttk.Label(frame, text=mode, foreground="#a33").pack(anchor="w", pady=6)
        self.connection = tk.StringVar(value="HaiGPT 미연결" if interpreter == "haigpt" else "모의 응답 · HaiGPT 미연결")
        ttk.Label(frame, textvariable=self.connection, foreground="#a33").pack(anchor="w", pady=4)
        self.request = tk.StringVar(value="1번 PC에 Python 실습환경 설치해 줘")
        self.entry = ttk.Entry(frame, textvariable=self.request, font=("맑은 고딕", 12))
        self.entry.pack(fill="x")
        self.preview_button = ttk.Button(frame, text="1. 요청 해석 및 대상 확인", command=self.preview)
        self.preview_button.pack(anchor="w", pady=10)
        self.summary = tk.StringVar(value="요청을 해석하면 실행 대상과 설치 내용이 표시됩니다.")
        ttk.Label(frame, textvariable=self.summary, wraplength=1000).pack(anchor="w", pady=6)
        self.run_button = ttk.Button(frame, text="2. 확인한 대상에 실행", command=self.run, state="disabled")
        self.run_button.pack(anchor="w", pady=10)
        ttk.Label(frame, text="작업 이력 · 시간은 UTC · 모의/실제 결과를 구분해 보세요").pack(anchor="w")
        columns = ("created", "seat", "mode", "state", "status", "detail")
        self.table = ttk.Treeview(frame, columns=columns, show="headings", height=12)
        for column, label, width in zip(columns, ("시간", "좌석", "해석/실행", "작업 상태", "좌석 결과", "검증 내용"), (145, 50, 100, 95, 145, 430)):
            self.table.heading(column, text=label)
            self.table.column(column, width=width, minwidth=40)
        self.table.pack(fill="both", expand=True)
        scroll = ttk.Scrollbar(frame, orient="horizontal", command=self.table.xview)
        scroll.pack(fill="x")
        self.table.configure(xscrollcommand=scroll.set)
        self.status = tk.StringVar(value="준비됨. 비밀번호·API 키를 요청문에 입력하지 마세요.")
        ttk.Label(frame, textvariable=self.status).pack(anchor="w", pady=6)
        self.plan = None
        self.request.trace_add("write", self.invalidate)
        root.protocol("WM_DELETE_WINDOW", self.close)
        self.refresh()
        self.poll_id = root.after(200, self.poll)

    def invalidate(self, *_):
        self.plan = None
        self.run_button.configure(state="disabled")

    def preview(self):
        if self.busy:
            return
        self.invalidate()
        if self.interpreter == "haigpt":
            self.busy = True
            self.entry.configure(state="disabled")
            self.preview_button.configure(state="disabled")
            self.status.set("HaiGPT 요청 중. API 응답만 확인하며 설치하지 않습니다.")
            text = self.request.get()
            seats = dict(self.targets)
            def worker():
                try:
                    plan = interpret(text, seats, "haigpt")
                    self.events.put(("plan", plan))
                except ValueError as exc:
                    self.events.put(("interpret_error", str(exc)))
                except Exception:
                    self.events.put(("interpret_error", "HaiGPT 처리 오류. 실행하지 않았습니다."))
            threading.Thread(target=worker, daemon=True).start()
            return
        try:
            self.plan = interpret(self.request.get(), self.targets, self.interpreter)
        except ValueError as error:
            self.summary.set(str(error))
            return
        self.show_plan()

    def show_plan(self):
        names = [f"{s}번 ({self.targets[s]['host']})" if self.real else f"{s}번 (모의 VM)" for s in self.plan.seats]
        self.summary.set(f"대상: {', '.join(names)}\n프로필: Python {VERSION} x64 + pip / 계정별 InstallONE 전용 폴더 / PATH 변경 없음\n전용 경로의 기존 버전 확인 → 없으면 설치 → 버전·예제 42·pip 검증")
        self.run_button.configure(state="normal")

    def run(self):
        if self.busy or self.plan is None:
            return
        try:
            self.plan = validate_plan({"seats": list(self.plan.seats), "profile": self.plan.profile}, self.targets)
        except ValueError:
            self.invalidate()
            self.summary.set("실행 전 대상 검증 실패. 요청을 다시 확인하세요.")
            return
        if not messagebox.askyesno("실행 확인", self.summary.get() + ("\n위 VM에 실제 설치합니다." if self.real else "\n모의 실행입니다. 실제 설치하지 않습니다.")):
            return
        job = self.store.create(self.plan, self.interpreter, "ssh" if self.real else "mock")
        self.busy = True
        self.invalidate()
        self.entry.configure(state="disabled")
        self.preview_button.configure(state="disabled")
        self.status.set("실행 중. 좌석별 결과를 저장합니다.")
        def worker():
            try:
                execute_job(self.store, job, self.executor)
                self.events.put("작업 종료. 좌석별 결과를 확인하세요.")
            except Exception:
                self.events.put("작업 저장/실행 오류. 이력 상태를 확인하세요.")
        threading.Thread(target=worker, daemon=True).start()

    def refresh(self):
        self.table.delete(*self.table.get_children())
        for row in self.store.history():
            self.table.insert("", "end", values=(row["created"], row["seat"], f'{row["interpreter"]}/{row["executor"]}', row["state"], row["status"], row["detail"]))

    def poll(self):
        try:
            event = self.events.get_nowait()
            self.busy = False
            self.entry.configure(state="normal")
            self.preview_button.configure(state="normal")
            if isinstance(event, tuple):
                kind, value = event
                if kind == "plan":
                    self.plan = value
                    self.connection.set("HaiGPT 실제 응답·해석 검증 완료 · 설치 결과와 별개")
                    self.status.set("대상과 설치 내용을 확인한 뒤 실행하세요.")
                    self.show_plan()
                else:
                    self.invalidate()
                    self.connection.set("HaiGPT 해석 미확인 — 최근 요청 실패 또는 보완 필요")
                    self.summary.set(value)
                    self.status.set("실행하지 않았습니다. 안내를 확인하고 다시 요청하세요.")
            else:
                self.status.set(event)
        except queue.Empty:
            pass
        if self.busy or self.table.winfo_exists():
            self.refresh()
        self.poll_id = self.root.after(500, self.poll)

    def close(self):
        if self.busy:
            messagebox.showinfo("실행 중", "작업 결과 저장 후 닫아주세요. 강제 종료 시 원격 작업은 계속될 수 있습니다.")
            return
        self.root.after_cancel(self.poll_id)
        self.root.destroy()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--real", action="store_true", help="승인된 VM에 실제 설치; local.json 필요")
    parser.add_argument("--interpreter", choices=("mock", "haigpt"), default="mock")
    args = parser.parse_args()
    prepare_tk()
    root = tk.Tk()
    try:
        App(root, real=args.real, interpreter=args.interpreter)
    except (ValueError, OSError) as error:
        root.withdraw()
        messagebox.showerror("설정 확인", "로컬 설정을 읽을 수 없습니다. README와 local.json을 확인하세요.")
        root.destroy()
    else:
        root.mainloop()
