import sys
import os
import logging
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QGroupBox, QPushButton, QLabel, 
                             QProgressBar, QTableWidget, QTableWidgetItem,
                             QMessageBox, QCheckBox, QHeaderView)
from PySide6.QtCore import Qt, QThread, Signal
from download_manager import DownloadManager
from file_monitor import FileMonitor
from video_downloader import VideoDownloader

# 配置日志
def setup_logging():
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
        
    log_file = os.path.join(log_dir, "app.log")
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    
    return logging.getLogger("VideoDownloader")

logger = setup_logging()

def check_hcnetsdk():
    """检查HCNetSDK是否存在"""
    sdk_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'HCNetSDK')
    dll_path = os.path.join(sdk_path, 'HCNetSDK.dll')
    
    logger.info(f"检查SDK路径: {sdk_path}")
    
    if not os.path.exists(sdk_path):
        logger.error(f"HCNetSDK文件夹不存在: {sdk_path}")
        return False, f"HCNetSDK文件夹不存在: {sdk_path}"
    
    if not os.path.exists(dll_path):
        logger.error(f"HCNetSDK.dll文件不存在: {dll_path}")
        return False, f"HCNetSDK.dll文件不存在: {dll_path}"
        
    logger.info("HCNetSDK检查通过")
    return True, "HCNetSDK检查通过"

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        logger.info("初始化主窗口")
        
        self.setWindowTitle("视频下载管理器")
        self.setMinimumSize(800, 600)
        
        # 检查SDK
        sdk_ok, sdk_msg = check_hcnetsdk()
        if not sdk_ok:
            QMessageBox.critical(self, "错误", f"海康威视SDK加载失败:\n{sdk_msg}")
            sys.exit(1)
            
        try:
            logger.info("初始化下载管理器")
            # 初始化下载管理器
            self.download_manager = DownloadManager()
            
            logger.info("初始化文件监控器")
            # 初始化文件监控器
            self.file_monitor = FileMonitor()
            self.file_monitor.new_file_detected.connect(self.on_new_file)
            
            # 初始化界面
            logger.info("初始化界面")
            self.init_ui()
            
            # 连接信号和槽
            self.connect_signals()
            
            # 启动文件监控
            logger.info("启动文件监控")
            self.file_monitor.start()
            
            # 初始化已完成列表显示
            self.update_completed_table()
            
        except Exception as e:
            logger.exception(f"初始化失败: {str(e)}")
            QMessageBox.critical(self, "初始化错误", f"程序初始化失败:\n{str(e)}")
            raise

    def init_ui(self):
        # 创建主窗口部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        # 当前下载状态组
        current_download_group = QGroupBox("当前下载状态")
        current_download_layout = QVBoxLayout()
        self.current_file_label = QLabel("无下载任务")
        self.current_channel_label = QLabel("")
        self.progress_bar = QProgressBar()
        current_download_layout.addWidget(self.current_file_label)
        current_download_layout.addWidget(self.current_channel_label)
        current_download_layout.addWidget(self.progress_bar)
        current_download_group.setLayout(current_download_layout)
        
        # 待下载队列组
        queue_group = QGroupBox("待下载队列")
        queue_layout = QVBoxLayout()
        self.queue_table = QTableWidget()
        self.queue_table.setColumnCount(3)
        self.queue_table.setHorizontalHeaderLabels(["文件名", "通道数", "状态"])
        queue_layout.addWidget(self.queue_table)
        queue_group.setLayout(queue_layout)
        
        # 已下载列表组
        completed_group = QGroupBox("已下载列表")
        completed_layout = QVBoxLayout()
        self.completed_table = QTableWidget()
        self.completed_table.setColumnCount(4)
        self.completed_table.setHorizontalHeaderLabels(["选择", "文件名", "完成时间", "通道数"])
        
        # 批量删除操作按钮
        delete_layout = QHBoxLayout()
        self.select_all_button = QPushButton("全选")
        self.select_none_button = QPushButton("取消全选")
        self.delete_selected_button = QPushButton("删除选中")
        self.delete_selected_button.setStyleSheet("QPushButton { background-color: #ff6b6b; color: white; }")
        
        delete_layout.addWidget(self.select_all_button)
        delete_layout.addWidget(self.select_none_button)
        delete_layout.addWidget(self.delete_selected_button)
        delete_layout.addStretch()
        
        completed_layout.addWidget(self.completed_table)
        completed_layout.addLayout(delete_layout)
        completed_group.setLayout(completed_layout)
        
        # 控制按钮组
        control_layout = QHBoxLayout()
        self.start_button = QPushButton("开始")
        self.pause_button = QPushButton("暂停")
        self.stop_button = QPushButton("停止")
        control_layout.addWidget(self.start_button)
        control_layout.addWidget(self.pause_button)
        control_layout.addWidget(self.stop_button)
        
        # 添加所有组件到主布局
        main_layout.addWidget(current_download_group)
        main_layout.addWidget(queue_group)
        main_layout.addWidget(completed_group)
        main_layout.addLayout(control_layout)

    def connect_signals(self):
        # 连接按钮信号
        self.start_button.clicked.connect(self.start_download)
        self.pause_button.clicked.connect(self.pause_download)
        self.stop_button.clicked.connect(self.stop_download)
        
        # 连接批量删除按钮信号
        self.select_all_button.clicked.connect(self.select_all_completed)
        self.select_none_button.clicked.connect(self.select_none_completed)
        self.delete_selected_button.clicked.connect(self.delete_selected_videos)
        
        # 连接下载管理器信号
        self.download_manager.progress_updated.connect(self.update_progress)
        self.download_manager.download_completed.connect(self.on_download_completed)
        self.download_manager.download_failed.connect(self.on_download_failed)
        self.download_manager.queue_updated.connect(self.update_queue_table)
        self.download_manager.completed_updated.connect(self.update_completed_table)

    def on_new_file(self, file_info):
        self.download_manager.add_task(file_info)

    def start_download(self):
        self.download_manager.start()
        self.start_button.setEnabled(False)
        self.pause_button.setEnabled(True)
        self.stop_button.setEnabled(True)

    def pause_download(self):
        self.download_manager.pause()
        self.start_button.setEnabled(True)
        self.pause_button.setEnabled(False)

    def stop_download(self):
        self.download_manager.stop()
        self.start_button.setEnabled(True)
        self.pause_button.setEnabled(False)
        self.stop_button.setEnabled(False)

    def update_progress(self, filename, channel, progress):
        self.current_file_label.setText(f"当前文件: {filename}")
        self.current_channel_label.setText(f"当前通道: {channel}")
        self.progress_bar.setValue(progress)

    def on_download_completed(self, filename, channel):
        self.update_completed_table()

    def on_download_failed(self, filename, channel, error):
        # 可以添加错误提示对话框
        pass

    def select_all_completed(self):
        """全选已完成列表中的所有项"""
        for row in range(self.completed_table.rowCount()):
            checkbox = self.completed_table.cellWidget(row, 0)
            if checkbox:
                checkbox.setChecked(True)

    def select_none_completed(self):
        """取消选择已完成列表中的所有项"""
        for row in range(self.completed_table.rowCount()):
            checkbox = self.completed_table.cellWidget(row, 0)
            if checkbox:
                checkbox.setChecked(False)

    def delete_selected_videos(self):
        """删除选中的视频文件夹"""
        selected_files = []
        for row in range(self.completed_table.rowCount()):
            checkbox = self.completed_table.cellWidget(row, 0)
            if checkbox and checkbox.isChecked():
                filename_item = self.completed_table.item(row, 1)
                if filename_item:
                    selected_files.append(filename_item.text())
        
        if not selected_files:
            QMessageBox.information(self, "提示", "请先选择要删除的视频文件！")
            return
        
        # 确认删除对话框
        reply = QMessageBox.question(
            self, 
            "确认删除", 
            f"您确定要删除选中的 {len(selected_files)} 个视频文件吗？\n\n"
            f"注意：这将删除文件夹及其所有内容，操作不可恢复！",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                # 调用下载管理器的删除方法
                success_count = self.download_manager.delete_video_files(selected_files)
                
                if success_count > 0:
                    QMessageBox.information(
                        self, 
                        "删除完成", 
                        f"成功删除了 {success_count} 个视频文件夹！"
                    )
                    # 更新界面
                    self.update_completed_table()
                else:
                    QMessageBox.warning(self, "删除失败", "没有成功删除任何文件！")
                    
            except Exception as e:
                logger.exception(f"批量删除失败: {str(e)}")
                QMessageBox.critical(self, "错误", f"删除过程中发生错误：\n{str(e)}")

    def update_queue_table(self):
        self.queue_table.setRowCount(0)
        for task in self.download_manager.queue:
            row = self.queue_table.rowCount()
            self.queue_table.insertRow(row)
            self.queue_table.setItem(row, 0, QTableWidgetItem(task['filename']))
            self.queue_table.setItem(row, 1, QTableWidgetItem(str(len(task['channels']))))
            self.queue_table.setItem(row, 2, QTableWidgetItem(task['status']))

    def update_completed_table(self):
        self.completed_table.setRowCount(0)
        for file_info in self.download_manager.completed_files:
            row = self.completed_table.rowCount()
            self.completed_table.insertRow(row)
            
            # 添加复选框
            checkbox = QCheckBox()
            self.completed_table.setCellWidget(row, 0, checkbox)
            
            # 添加文件信息
            self.completed_table.setItem(row, 1, QTableWidgetItem(file_info['filename']))
            self.completed_table.setItem(row, 2, QTableWidgetItem(file_info['completion_time']))
            self.completed_table.setItem(row, 3, QTableWidgetItem(str(len(file_info['channels']))))
        
        # 调整列宽
        header = self.completed_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)

    def closeEvent(self, event):
        self.download_manager.stop()
        self.file_monitor.stop()
        event.accept()

def main():
    logger.info("程序启动")
    
    # 创建 logs 目录（相对路径）
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
        logger.info(f"创建目录: {log_dir}")

    # 创建 record 目录（绝对路径）
    record_dir = r"E:\\积水识别项目\\视频下载模块\\record"
    if not os.path.exists(record_dir):
        os.makedirs(record_dir)
        logger.info(f"创建目录: {record_dir}")
            
    app = QApplication(sys.argv)
    
    try:
        logger.info("创建主窗口")
        window = MainWindow()
        window.show()
        
        logger.info("进入应用主循环")
        exit_code = app.exec()
        logger.info(f"程序退出，退出码: {exit_code}")
        sys.exit(exit_code)
    except Exception as e:
        logger.exception(f"程序运行出错: {str(e)}")
        QMessageBox.critical(None, "错误", f"程序运行失败:\n{str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main() 