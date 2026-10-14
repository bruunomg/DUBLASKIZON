"""Read a scene's output without allowing the UI worker to wait forever."""
import queue
import threading
import time

class SceneTimeout(RuntimeError):
    pass

def scene_lines(process, seconds=0, cancelled=lambda:False):
    if not seconds:
        yield from process.stdout
        return
    messages=queue.Queue()
    def read():
        try:
            for line in process.stdout: messages.put(line)
        finally:messages.put(None)
    reader=threading.Thread(target=read,daemon=True);reader.start()
    deadline=time.monotonic()+seconds
    while True:
        if cancelled() or time.monotonic()>deadline:
            process.kill()
            reader.join(timeout=5)
            if cancelled():return
            raise SceneTimeout(f'Cena excedeu {seconds:g} segundos; pulada por demora, áudio anterior preservado.')
        try:line=messages.get(timeout=.1)
        except queue.Empty:continue
        if line is None:return
        yield line
