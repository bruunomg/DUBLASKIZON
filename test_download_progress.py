from duration_converter_tab import update_download_progress


class FakeProgress:
    def __init__(self):
        self.value = 0.0
        self.mode = "determinate"
        self.stopped = 0

    def cget(self, name):
        return self.value if name == "value" else self.mode

    def stop(self):
        self.stopped += 1

    def configure(self, **kwargs):
        self.mode = kwargs.get("mode", self.mode)
        self.value = float(kwargs.get("value", self.value))


def main():
    progress = FakeProgress()
    values = [
        update_download_progress(progress, "ffmpeg", 0, 0),
        update_download_progress(progress, "ffmpeg", 8 * 1048576, 0),
        update_download_progress(progress, "ffmpeg", 4 * 1048576, 100 * 1048576),
        update_download_progress(progress, "sox", 0, 0),
        update_download_progress(progress, "sox", 12 * 1048576, 0),
        update_download_progress(progress, "sox", 1, 1),
    ]
    assert values == sorted(values), values
    assert progress.mode == "determinate"
    assert progress.stopped == len(values)
    assert values[-1] == 99.0
    print("download_progress_ok")


if __name__ == "__main__":
    main()
