from PySide6.QtCore import QEventLoop, QThread, QTimer

from app import application
from app.events import Log


def test_completion_follows_all_logs_on_gui_thread(controller, monkeypatch, qapp):
    worker_threads = []
    received = []

    def operation(request, stop, report):
        worker_threads.append(QThread.currentThread())
        for index in range(1000):
            report(Log(str(index)))
        return application.RunResult(request, stopped=False)

    monkeypatch.setattr(application, "run_sorting", operation)
    controller.logMessage.connect(lambda text: received.append((text, QThread.currentThread())))
    controller.completed.connect(lambda dry: received.append(("complete", QThread.currentThread())))
    loop = QEventLoop()
    controller.start()
    controller._thread.finished.connect(loop.quit)
    QTimer.singleShot(5000, loop.quit)
    loop.exec()
    assert not controller.busy
    assert [text for text, _ in received] == [str(i) for i in range(1000)] + ["complete"]
    assert all(thread == qapp.thread() for _, thread in received)
    assert worker_threads[0] != qapp.thread()
