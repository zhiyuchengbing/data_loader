import os
import time
from datetime import datetime, timedelta
from PySide6.QtCore import QThread, Signal
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class FileMonitor(QThread):
    new_file_detected = Signal(dict)  # 发送新文件信息

    def __init__(self, folder_path="F:\\baowen"):
        super().__init__()
        self.folder_path = folder_path
        self.observer = None
        self.is_running = False
        self.processed_files = set()

    def run(self):
        if not os.path.exists(self.folder_path):
            print(f"监控文件夹不存在: {self.folder_path}")
            return

        self.is_running = True
        event_handler = FileEventHandler(self)
        self.observer = Observer()
        self.observer.schedule(event_handler, self.folder_path, recursive=False)
        self.observer.start()

        # 处理已存在的文件
        self.process_existing_files()

        try:
            while self.is_running:
                time.sleep(1)
        except Exception as e:
            print(f"文件监控出错: {e}")
        finally:
            if self.observer:
                self.observer.stop()
                self.observer.join()

    def process_existing_files(self):
        """处理文件夹中已存在的文件"""
        for filename in os.listdir(self.folder_path):
            if filename.endswith('.txt') and filename not in self.processed_files:
                self.process_file(filename)

    def process_file(self, filename):
        """处理单个文件"""
        if filename in self.processed_files:
            return

        try:
            file_path = os.path.join(self.folder_path, filename)
            # 获取文件创建时间
            creation_time = datetime.fromtimestamp(os.path.getctime(file_path))
            # 计算过期时间（创建时间+6分钟）
            creation_time=creation_time-timedelta(minutes=6)
            expiration_time = creation_time + timedelta(minutes=6)

            # 发送文件信息
            file_info = {
                'filename': os.path.splitext(filename)[0],
                'start_time': creation_time,
                'end_time': expiration_time
            }
            self.new_file_detected.emit(file_info)
            self.processed_files.add(filename)

        except Exception as e:
            print(f"处理文件出错: {e}")

    def stop(self):
        """停止监控"""
        self.is_running = False
        if self.observer:
            self.observer.stop()
            self.observer.join()

class FileEventHandler(FileSystemEventHandler):
    def __init__(self, monitor):
        self.monitor = monitor

    def on_created(self, event):
        if not event.is_directory and event.src_path.endswith('.txt'):
            filename = os.path.basename(event.src_path)
            self.monitor.process_file(filename) 