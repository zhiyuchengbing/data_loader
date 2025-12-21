import json
import os
import time
import shutil
import csv
from datetime import datetime
from PySide6.QtCore import QObject, Signal, QThread
from video_downloader import VideoDownloader


class DownloadManager(QObject):
    progress_updated = Signal(str, int, int)  # 文件名, 通道号, 进度
    download_completed = Signal(str, int)  # 文件名, 通道号
    download_failed = Signal(str, int, str)  # 文件名, 通道号, 错误信息
    queue_updated = Signal()
    completed_updated = Signal()

    def __init__(self):
        super().__init__()
        self.queue = []
        self.current_task = None
        self.completed_files = []
        self.deleted_files = []  # 新增：记录已删除的文件列表
        self.downloader = VideoDownloader()
        self.is_running = False
        self.is_paused = False
        self.download_thread = None
        self.csv_file_path = "data/dropdata.csv"  # CSV文件路径
        self._ensure_data_directory()  # 确保data目录存在
        self.load_completed_files()
        self.load_deleted_files_from_csv()  # 从CSV加载删除记录
        # 扫描现有的视频文件夹
        self.scan_existing_videos()
    
    def _ensure_data_directory(self):
        """确保data目录存在"""
        data_dir = os.path.dirname(self.csv_file_path)
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)
            print(f"创建目录: {data_dir}")
    
    def load_deleted_files_from_csv(self):
        """从CSV文件加载已删除文件记录"""
        if os.path.exists(self.csv_file_path):
            try:
                with open(self.csv_file_path, 'r', encoding='utf-8', newline='') as f:
                    reader = csv.DictReader(f)
                    self.deleted_files = [row['filename'] for row in reader]
                print(f"从CSV加载了 {len(self.deleted_files)} 个已删除文件记录")
            except Exception as e:
                print(f"从CSV加载已删除文件记录失败: {e}")
                self.deleted_files = []
        else:
            print(f"CSV文件不存在，创建新文件: {self.csv_file_path}")
            self._create_csv_header()
    
    def _create_csv_header(self):
        """创建CSV文件头"""
        try:
            with open(self.csv_file_path, 'w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['filename', 'deleted_time', 'operation'])
            print(f"创建 CSV 文件: {self.csv_file_path}")
        except Exception as e:
            print(f"创建 CSV 文件失败: {e}")
    
    def save_deleted_file_to_csv(self, filename):
        """保存删除文件记录到CSV"""
        try:
            # 检查文件是否已存在于记录中
            if filename in self.deleted_files:
                return
            
            # 添加到内存列表
            self.deleted_files.append(filename)
            
            # 追加到CSV文件
            with open(self.csv_file_path, 'a', encoding='utf-8', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    filename, 
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 
                    'delete'
                ])
            print(f"已将删除记录保存到CSV: {filename}")
        except Exception as e:
            print(f"保存删除记录到CSV失败: {e}")

    def load_completed_files(self):
        """加载已下载文件记录"""
        if os.path.exists('completed_files.json'):
            try:
                with open('completed_files.json', 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # 兼容旧版本数据格式
                    if isinstance(data, list):
                        self.completed_files = data
                    else:
                        self.completed_files = data.get('completed_files', [])
                        # 不再从 JSON 加载 deleted_files，改为从 CSV 加载
            except Exception as e:
                print(f"加载已下载文件记录失败: {e}")

    def save_completed_files(self):
        """保存已下载文件记录（只保存已完成文件，删除记录保存在CSV中）"""
        try:
            with open('completed_files.json', 'w', encoding='utf-8') as f:
                json.dump(self.completed_files, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存已下载文件记录失败: {e}")

    def add_task(self, file_info):
        """添加下载任务"""
        filename = file_info['filename']
        print(f"尝试添加任务: {filename}")
        print(f"已删除列表: {self.deleted_files}")
        
        # 检查是否已下载
        if self._is_downloaded(filename):
            print(f"任务 {filename} 已被跳过（已下载或已删除）")
            return False

        task = {
            'filename': filename,
            'channels': [33, 34, 35, 36],  # 四个通道
            'start_time': file_info['start_time'],
            'end_time': file_info['end_time'],
            'status': 'pending',
            'current_channel': None,
            'progress': 0
        }
        self.queue.append(task)
        print(f"任务 {filename} 已添加到下载队列")
        self.queue_updated.emit()
        return True

    def _is_downloaded(self, filename):
        """检查文件是否已下载或已删除"""
        # 检查是否在已删除列表中（首先检查）
        if filename in self.deleted_files:
            print(f"文件 {filename} 在已删除列表中，跳过下载")
            return True
        
        # 检查是否在已完成列表中
        for file_info in self.completed_files:
            if file_info['filename'] == filename:
                return True

        # 检查文件是否实际存在
        file_save_path = os.path.join("record", filename)
        if os.path.exists(file_save_path):
            # 检查四个通道的文件是否都存在
            channels = [33, 34, 35, 36]
            all_files_exist = True

            for channel in channels:
                # 这里需要根据实际的文件命名规则来检查
                # 暂时简单检查文件夹是否存在
                if not os.path.exists(file_save_path):
                    all_files_exist = False
                    break

            if all_files_exist:
                # 如果文件存在但不在记录中，添加到记录
                self.completed_files.append({
                    'filename': filename,
                    'channels': [33, 34, 35, 36],
                    'completion_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                })
                self.save_completed_files()
                return True

        return False

    def start(self):
        """开始下载"""
        if not self.is_running:
            self.is_running = True
            self.is_paused = False
            self.download_thread = DownloadThread(self)
            self.download_thread.start()

    def pause(self):
        """暂停下载"""
        self.is_paused = True

    def stop(self):
        """停止下载"""
        self.is_running = False
        if self.download_thread:
            self.download_thread.wait()
        self.save_completed_files()

    def get_next_task(self):
        """获取下一个下载任务"""
        if self.current_task is None and self.queue:
            self.current_task = self.queue.pop(0)
            return self.current_task
        return None

    def mark_channel_completed(self, filename, channel):
        """标记通道下载完成"""
        # 更新当前任务状态
        if self.current_task and self.current_task['filename'] == filename:
            if channel in self.current_task['channels']:
                self.current_task['channels'].remove(channel)
                if not self.current_task['channels']:
                    # 所有通道下载完成
                    self.completed_files.append({
                        'filename': filename,
                        'channels': [33, 34, 35, 36],
                        'completion_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    })
                    self.current_task = None
                    self.completed_updated.emit()
                    self.save_completed_files()

    def delete_video_files(self, filenames):
        """
        批量删除视频文件夹及其记录
        
        Args:
            filenames (list): 要删除的文件名列表
            
        Returns:
            int: 成功删除的文件夹数量
        """
        success_count = 0
        
        for filename in filenames:
            try:
                # 构建文件夹路径
                folder_path = os.path.join("record", filename)
                
                # 删除文件夹及其所有内容
                if os.path.exists(folder_path):
                    shutil.rmtree(folder_path)
                    print(f"已删除文件夹: {folder_path}")
                    success_count += 1
                else:
                    print(f"文件夹不存在: {folder_path}")
                
                # 从已完成记录中移除
                self.completed_files = [
                    file_info for file_info in self.completed_files 
                    if file_info['filename'] != filename
                ]
                
                # 保存到CSV文件中
                self.save_deleted_file_to_csv(filename)
                
            except Exception as e:
                print(f"删除文件夹 {filename} 时出错: {str(e)}")
                continue
        
        # 保存更新后的记录
        if success_count > 0:
            self.save_completed_files()
            self.completed_updated.emit()
            
        return success_count

    def scan_existing_videos(self):
        """
        扫描 record 文件夹中已存在的视频文件夹，并添加到已完成列表中
        """
        record_path = "record"
        print(f"开始扫描视频文件夹: {record_path}")
        
        if not os.path.exists(record_path):
            print(f"{record_path} 文件夹不存在")
            return
        
        try:
            # 获取所有子文件夹
            existing_folders = []
            for item in os.listdir(record_path):
                item_path = os.path.join(record_path, item)
                if os.path.isdir(item_path):
                    existing_folders.append(item)
            
            print(f"找到 {len(existing_folders)} 个子文件夹")
            
            # 检查哪些文件夹不在已完成列表中
            existing_filenames = {file_info['filename'] for file_info in self.completed_files}
            print(f"已记录的文件夹数量: {len(existing_filenames)}")
            
            new_videos_found = 0
            for folder_name in existing_folders:
                # 检查是否在已完成列表中或已删除列表中
                if (folder_name not in existing_filenames and 
                    folder_name not in self.deleted_files):
                    # 直接添加到已完成列表，不检查具体视频文件
                    folder_path = os.path.join(record_path, folder_name)
                    self.completed_files.append({
                        'filename': folder_name,
                        'channels': [33, 34, 35, 36],  # 默认四个通道
                        'completion_time': self._get_folder_creation_time(folder_path)
                    })
                    new_videos_found += 1
                    print(f"添加新文件夹: {folder_name}")
                elif folder_name in self.deleted_files:
                    print(f"跳过已删除的文件夹: {folder_name}")
            
            if new_videos_found > 0:
                print(f"扫描到 {new_videos_found} 个新的视频文件夹")
                self.save_completed_files()
                self.completed_updated.emit()
            else:
                print("没有发现新的视频文件夹")
                
        except Exception as e:
            print(f"扫描文件夹时出错: {str(e)}")
    
    def _get_folder_creation_time(self, folder_path):
        """获取文件夹创建时间"""
        try:
            creation_time = os.path.getctime(folder_path)
            return datetime.fromtimestamp(creation_time).strftime('%Y-%m-%d %H:%M:%S')
        except:
            return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


class DownloadThread(QThread):
    def __init__(self, manager):
        super().__init__()
        self.manager = manager

    def run(self):
        while self.manager.is_running:
            if self.manager.is_paused:
                self.msleep(1000)
                continue

            task = self.manager.get_next_task()
            if task is None:
                self.msleep(1000)
                continue

            filename = task['filename']
            channels = task['channels'].copy()  # 创建副本避免迭代时修改

            for channel in channels:
                if not self.manager.is_running or self.manager.is_paused:
                    break

                try:
                    # 更新状态为下载中
                    task['current_channel'] = channel
                    task['status'] = 'downloading'
                    self.manager.queue_updated.emit()

                    # 更新界面进度
                    self.manager.progress_updated.emit(filename, channel, 0)

                    # 开始下载
                    success = self.manager.downloader.download_video(
                        channel,
                        task['start_time'],
                        task['end_time'],
                        "record",  # base_save_path
                        task['filename']  # filename参数
                    )

                    if success:
                        self.manager.mark_channel_completed(filename, channel)
                        self.manager.download_completed.emit(filename, channel)
                        # 更新完成进度
                        self.manager.progress_updated.emit(filename, channel, 100)
                    else:
                        self.manager.download_failed.emit(filename, channel, "下载失败")

                except Exception as e:
                    print(f"下载出错: {str(e)}")
                    self.manager.download_failed.emit(filename, channel, str(e))

                # 下载完成后等待一小段时间再开始下一个
                self.msleep(2000) 