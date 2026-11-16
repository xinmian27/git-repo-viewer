"""workers.py —— 后台任务执行器。

界面（主线程）绝不能直接执行 git 命令——仓库大的时候会卡住窗口。
这里把"干活"放到线程池里，干完通过 Qt 信号把结果送回主线程。
AsyncRunner 还带一个"只认最新一次"的令牌：用户快速切换仓库时，
迟到的旧结果会被自动丢弃，不会串台。
"""
from __future__ import annotations

from PySide6.QtCore import QObject, QRunnable, Signal, QThreadPool


class _JobSignals(QObject):
    done = Signal(object)


class FuncWorker(QRunnable):
    """在线程池里跑一个函数；无论成功失败，都通过 done 信号发回主线程。

    注意：必须 setAutoDelete(False)，并由 AsyncRunner 持有引用直到结果送达，
    否则线程池会在 run() 结束后立刻回收它，连带回收信号对象，
    排队中的结果信号就会被丢弃，主线程永远收不到回调。
    """

    def __init__(self, fn):
        super().__init__()
        self.setAutoDelete(False)
        self.signals = _JobSignals()
        self._fn = fn

    def run(self):
        try:
            self.signals.done.emit(("ok", self._fn()))
        except Exception as e:  # 兜底：任何异常都要送回主线程显示，不能让线程无声死掉
            self.signals.done.emit(("err", str(e)))


class AsyncRunner(QObject):
    """同一类任务只认最后一次发起的结果（旧的自动作废）。"""

    def __init__(self, pool: QThreadPool, parent=None):
        super().__init__(parent)
        self._pool = pool
        self._seq = 0
        self._workers = set()  # 持有运行中的任务对象，防止被提前垃圾回收

    def run(self, fn, on_ok, on_err=None):
        self._seq += 1
        seq = self._seq

        def handle(result):
            self._workers.discard(worker)
            if seq != self._seq:
                return
            status, payload = result
            if status == "ok":
                on_ok(payload)
            elif on_err is not None:
                on_err(payload)

        worker = FuncWorker(fn)
        worker.signals.done.connect(handle)
        self._workers.add(worker)
        self._pool.start(worker)
