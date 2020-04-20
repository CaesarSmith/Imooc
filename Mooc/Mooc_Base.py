'''
    Mooc 的虚基类：用于派生所有Mooc子类
'''

import os
from abc import ABC, abstractmethod
from Mooc.Mooc_Config import *
from Mooc.Mooc_Download import *
from Mooc.Mooc_Request import *
import m3u8
from urllib.parse import urljoin
from threading import Thread
from queue import Queue
import re
import subprocess
import time

__all__ = [
    "Mooc_Base"
]

class Mooc_Base(ABC):
    def __init__(self):
        self.__mode = None
        self.__cid = None
        self.__title = None
        self.__infos = None
        self.__rootDir = None

    @property
    def mode(self):
        '''下载模式: 用于选择性下载'''
        return self.__mode

    @mode.setter
    def mode(self, mode):
        self.__mode = mode

    @property
    def cid(self):
        '''课程的 ID'''
        return self.__cid
    
    @cid.setter
    def cid(self, cid):
        self.__cid = cid

    @property
    def title(self):
        '''课程的标题'''
        return self.__title
    
    @title.setter
    def title(self, title):
        self.__title = title

    @property
    def infos(self):
        '''解析后的课程信息'''
        return self.__infos

    @property
    def rootDir(self):
        return self.__rootDir

    @rootDir.setter
    def rootDir(self, rootDir):
        self.__rootDir = rootDir
    
    @infos.setter
    def infos(self, infos):
        self.__infos = infos

    @abstractmethod
    def _get_cid(self):
        pass
    
    @abstractmethod
    def _get_title(self):
        pass

    @abstractmethod
    def _get_infos(self):
        pass

    @abstractmethod
    def _download(self):
        pass

    @abstractmethod
    def set_mode(self):
        pass

    @abstractmethod
    def prepare(self, url):
        pass

    @abstractmethod
    def download(self):
        pass

    @classmethod
    def download_video(cls, video_url, video_name, video_dir):
        '''下载 MP4 视频文件'''
        succeed = True
        if not cls.judge_file_existed(video_dir, video_name, '.mp4'):
            if 'm3u8' in video_url:
                succeed = cls.download_m3u8_video(video_url, video_name, video_dir)
                print("\r  |-{}  [mp4]下载完成".format(cls.align(video_name,LENGTH)))
            else:
                try:
                    header =  request_head(video_url)
                    size = float(header['Content-Length']) / (1024*1024)
                    print("  |-{}  [mp4] 大小: {:.2f}M".format(cls.align(video_name,LENGTH), size))
                    aria2_download_file(video_url, video_name+'.mp4', video_dir)
                except DownloadFailed:
                    print("  |-{}  [mp4] 资源无法下载！".format(cls.align(video_name,LENGTH)))
                    succeed = False
        else:
            print("  |-{}  [mp4] 已经成功下载！".format(cls.align(video_name,LENGTH)))
        return succeed
    
    @classmethod
    def download_m3u8_video(cls, video_url, video_name, video_dir):
        tmpdir = os.path.join(video_dir, 'tmp')
        succeed = True
        if not (os.path.exists(tmpdir)):
            os.mkdir(tmpdir)

        os.chdir(tmpdir)
        
        m3u8Str = request_get(video_url)
        m3u8_obj = m3u8.loads(m3u8Str)
        
        urls = []
        for ts in m3u8_obj.files:
            urls.append(urljoin(video_url, ts))

        def consumer(threadID, queque, urls):
            length = len(urls)
            while True:
                url = queue.get()
                urlindex = urls.index(url)
                print('\r    子线程 %2d 正在下载第%2d/%2d个视频片段' % (threadID, urlindex + 1, length), end = '')         
                content = request_get_bytes(url)
                
                tsName = re.search('.+/(.+\.ts)', url).group(1)
                with open(tsName, 'wb') as f:
                    f.write(content)
                    f.close()

                queue.task_done()

        def producer(queue, urls):
            length = len(urls)
            read_list = []
            while queue.full() is False:
                for i in range(length):
                    if urls[i] not in read_list:
                        read_list.append(urls[i])
                        queue.put(urls[i])
                    else:
                        continue
        
        try:
            #aria2_download_file(urljoin(video_url, ts), ts)
            #用requests下载
            threadTotalNumber = 20
            queue = Queue(maxsize=threadTotalNumber)
            # lock = Lock()

            # 生产者队列，用于将各章节标题与URL放入队列供消费者爬取
            producer_thread = Thread(target=producer, args=(queue, urls))
            producer_thread.daemon = True
            producer_thread.start()

            for index in range(threadTotalNumber):
                consumer_thread = Thread(
                    target=consumer, args=(index, queue, urls))
                consumer_thread.daemon = True
                consumer_thread.start()

            queue.join()

            # 合并ts文件
            print('\r                     正在合并文件                   ', end='')
            files = m3u8_obj.files
            shell_cmds = []
            if len(files) < 100:
                filestr = ''
                for file in files:
                    filestr += file + '+'
                shell_cmds.append('copy /b ' + filestr[:-1] + ' "..\\' + video_name + '.mp4"')
            else:
                i = 0
                while i <= len(files) // 100:
                    filestr = ''
                    for file in files[i * 100: (i + 1) * 100]:
                        filestr += file + '+'
                    shell_cmds.append('copy /b ' + filestr[:-1] + ' "..\\' + video_name + '_part' + str(i) +'.mp4"')
                    i += 1
            for shell in shell_cmds:
                p = subprocess.run(shell, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout = 3)
                if p.returncode != 0:
                    print('\n', p.stdout.decode('gbk'))
                    print('合并文件失败, 请联系作者:')
                    os.system('pause')
                
            # 删除ts文件及临时文件夹
            for file in m3u8_obj.files:
                if os.path.exists(file):
                    os.remove(file)
            os.chdir('..')
            os.rmdir(tmpdir)
 
        
        except DownloadFailed:
            print("  |-{}  [mp4] 资源无法下载！".format(cls.align(video_name,LENGTH)))
            succeed = False
        return succeed
    




    @classmethod
    def download_pdf(cls, pdf_url, pdf_name, pdf_dir):
        '''下载 PDF '''
        succeed = True
        if not cls.judge_file_existed(pdf_dir, pdf_name, '.pdf'):
            try:
                aria2_download_file(pdf_url, pdf_name+'.pdf', pdf_dir)
                print("  |-{}  (pdf) 已经成功下载！".format(cls.align(pdf_name,LENGTH)))
            except DownloadFailed:
                print("  |-{}  (pdf) 资源无法下载！".format(cls.align(pdf_name,LENGTH)))
                succeed = False
        else:
            print("  |-{}  (pdf) 已经成功下载！".format(cls.align(pdf_name,LENGTH)))
        return succeed

    @classmethod
    def download_sub(cls, sub_url, sub_name, sub_dir):
        '''下载字幕'''
        succeed = True
        if not cls.judge_file_existed(sub_dir, sub_name, '.srt'):
            try:
                aria2_download_file(sub_url, sub_name+'.srt', sub_dir)
            except DownloadFailed:
                succeed = False
        return succeed

    @staticmethod
    def judge_file_existed(dirname, filename, fmt):
        '''
        judge_file_existed(dirname, filename, fmt) 
        判断在 dirname 目录下是否存在已下载成功的格式为 fmt 且文件名为 filename 的文件
        '''
        filepath = os.path.join(dirname, filename)
        exist1 = os.path.exists(filepath+fmt)
        exist2 = os.path.exists(filepath+fmt+'.aria2')
        return exist1 and not exist2

    @staticmethod
    def align(string, width):  #  对齐汉字字符窜，同时截断多余输出
        '''
        align(string, width) 根据width宽度居中对齐字符窜 string，主要用于汉字居中
        '''
        res = ""
        size = 0
        for ch in string:
            if (size+3 > width):
                break
            size += 1 if ord(ch) <= 127 else 2
            res += ch
        res += (width-size)*' '
        return res
