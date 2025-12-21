import os
import time
from ctypes import *
from datetime import datetime
import platform
from HCNetSDK import *


class VideoDownloader:
    def __init__(self, device_ip='10.200.115.81', device_port=8000, username='admin', password='1234asdf'):
        # 配置海康威视SDK路径和DLL文件名称
        self.SDK_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), './HCNetSDK'))
        self.DLL_NAME = "HCNetSDK.dll"

        # 检查SDK文件夹是否存在
        if not os.path.exists(self.SDK_PATH):
            raise FileNotFoundError(f"HCNetSDK文件夹不存在: {self.SDK_PATH}")

        # 检查DLL文件是否存在
        dll_path = os.path.join(self.SDK_PATH, self.DLL_NAME)
        if not os.path.exists(dll_path):
            raise FileNotFoundError(f"HCNetSDK.dll文件不存在: {dll_path}")

        # 设备登录信息
        self.device_ip = create_string_buffer(device_ip.encode())
        self.device_port = c_ushort(device_port)
        self.username = create_string_buffer(username.encode())
        self.password = create_string_buffer(password.encode())

        # 用户ID
        self.lUserID = -1
        self.HCNetSDK = None

        # 初始化SDK
        self._init_sdk()

        # 登录设备
        self._login_device()

    def _init_sdk(self):
        """初始化SDK"""
        try:
            # 确保在Windows系统上运行
            if platform.system() != "Windows":
                raise OSError("此模块仅支持Windows系统")

            self.HCNetSDK = windll.LoadLibrary(os.path.join(self.SDK_PATH, self.DLL_NAME))
            print("成功加载DLL文件.")

            # 初始化SDK
            init_result = self.HCNetSDK.NET_DVR_Init()
            if init_result == 0:
                error_code = self.HCNetSDK.NET_DVR_GetLastError()
                raise Exception(f"初始化SDK失败，错误码：{error_code}")

            # 设置连接超时时间和重连功能
            self.HCNetSDK.NET_DVR_SetConnectTime(2000, 1)
            self.HCNetSDK.NET_DVR_SetReconnect(10000, 1)

        except OSError as e:
            print("加载DLL文件失败:", e)
            raise

    def _login_device(self):
        """登录设备"""
        # 设备信息结构体
        SERIALNO_LEN = 48

        class NET_DVR_DEVICEINFO_V30(Structure):
            _fields_ = [
                ("sSerialNumber", c_byte * SERIALNO_LEN),
                ("byAlarmInPortNum", c_byte),
                ("byAlarmOutPortNum", c_byte),
                ("byDiskNum", c_byte),
                ("byDVRType", c_byte),
                ("byChanNum", c_byte),
                ("byStartChan", c_byte),
                ("byAudioChanNum", c_byte),
                ("byIPChanNum", c_byte),
                ("byZeroChanNum", c_byte),
                ("byMainProto", c_byte),
                ("bySubProto", c_byte),
                ("bySupport", c_byte),
                ("bySupport1", c_byte),
                ("bySupport2", c_byte),
                ("wDevType", c_ushort),
                ("bySupport3", c_byte),
                ("byMultiStreamProto", c_byte),
                ("byStartDChan", c_byte),
                ("byStartDTalkChan", c_byte),
                ("byHighDChanNum", c_byte),
                ("bySupport4", c_byte),
                ("byLanguageType", c_byte),
                ("byVoiceInChanNum", c_byte),
                ("byStartVoiceInChanNo", c_byte),
                ("byRes3", c_byte * 2),
                ("byMirrorChanNum", c_byte),
                ("wStartMirrorChanNo", c_ushort),
                ("byRes2", c_byte * 2)
            ]

        DeviceInfo = NET_DVR_DEVICEINFO_V30()
        self.lUserID = self.HCNetSDK.NET_DVR_Login_V30(
            self.device_ip,
            self.device_port,
            self.username,
            self.password,
            byref(DeviceInfo)
        )

        # 判断是否登录成功
        if self.lUserID < 0:
            error_code = self.HCNetSDK.NET_DVR_GetLastError()
            print(f"登录设备失败，错误码：{error_code}")
            self.HCNetSDK.NET_DVR_Cleanup()
            raise Exception(f"登录设备失败，错误码：{error_code}")
        else:
            print("登录设备成功，用户ID:", self.lUserID)

    def download_video(self, lChannel, start_time, end_time, base_save_path="record", filename=None):
        """
        下载指定时间段的视频

        参数:
        lChannel (int): 通道号
        start_time (datetime): 录像开始时间
        end_time (datetime): 录像结束时间
        base_save_path (str): 保存文件的基础目录
        filename (str): 文件名，用于创建专属文件夹

        返回:
        bool: 是否下载成功
        """
        # 创建文件专属保存目录
        if filename:
            file_save_path = os.path.join(base_save_path, filename)
        else:
            file_save_path = base_save_path

        if not os.path.exists(file_save_path):
            os.makedirs(file_save_path)

        # 定义时间结构体
        class NET_DVR_TIME(Structure):
            _fields_ = [
                ("dwYear", c_ulong),
                ("dwMonth", c_ulong),
                ("dwDay", c_ulong),
                ("dwHour", c_ulong),
                ("dwMinute", c_ulong),
                ("dwSecond", c_ulong),
            ]

        # 转换时间
        start = NET_DVR_TIME(
            dwYear=start_time.year,
            dwMonth=start_time.month,
            dwDay=start_time.day,
            dwHour=start_time.hour,
            dwMinute=start_time.minute,
            dwSecond=start_time.second
        )

        end = NET_DVR_TIME(
            dwYear=end_time.year,
            dwMonth=end_time.month,
            dwDay=end_time.day,
            dwHour=end_time.hour,
            dwMinute=end_time.minute,
            dwSecond=end_time.second
        )

        # 根据时间生成文件名
        video_filename = "{}_{}{:02d}{:02d}_{:02d}{:02d}{:02d}_{:02d}{:02d}{:02d}.mp4".format(
            lChannel,
            start.dwYear, start.dwMonth, start.dwDay,
            start.dwHour, start.dwMinute, start.dwSecond,
            end.dwHour, end.dwMinute, end.dwSecond
        )
        save_path = os.path.join(file_save_path, video_filename)

        # 检查文件是否已存在
        if os.path.exists(save_path):
            print(f"文件已存在，跳过下载: {save_path}")
            return True

        # 转换保存路径为适合C接口的字符串格式
        sSavedFileName = create_string_buffer(save_path.encode('utf-8'))

        # 调用接口下载录像
        download_handle = self.HCNetSDK.NET_DVR_GetFileByTime(
            self.lUserID,
            lChannel,
            byref(start),
            byref(end),
            sSavedFileName
        )

        if download_handle < 0:
            error_code = self.HCNetSDK.NET_DVR_GetLastError()
            print(f"下载录像失败，错误码：{error_code}")
            return False

        # 开始下载
        NET_DVR_PLAYSTART = 1
        if not self.HCNetSDK.NET_DVR_PlayBackControl(download_handle, NET_DVR_PLAYSTART, 0, None):
            error_code = self.HCNetSDK.NET_DVR_GetLastError()
            print(f"启动下载失败，错误码：{error_code}")
            self.HCNetSDK.NET_DVR_StopGetFile(download_handle)
            return False

        # 检查下载进度
        status = 0
        while status != 100 and status != -1:
            status = self.HCNetSDK.NET_DVR_GetDownloadPos(download_handle)
            print(f"下载进度: {status}%")
            time.sleep(1)

        # 关闭下载句柄
        self.HCNetSDK.NET_DVR_StopGetFile(download_handle)

        if status == 100:
            print(f"下载完成: {save_path}")
            return True
        else:
            error_code = self.HCNetSDK.NET_DVR_GetLastError()
            print(f"下载失败，错误码：{error_code}")
            return False

    def __del__(self):
        """析构函数，释放资源"""
        if hasattr(self, 'lUserID') and self.lUserID >= 0:
            self.HCNetSDK.NET_DVR_Logout(self.lUserID)
        if hasattr(self, 'HCNetSDK'):
            self.HCNetSDK.NET_DVR_Cleanup()
        print("已释放海康威视SDK资源") 