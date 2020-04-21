'''
    Mooc 下载功能模块：调用 aria2c.exe 下载文件
'''

import os
import re
import subprocess
from time import sleep
from Mooc.Mooc_Config import *
from time import time, sleep

__all__ = [
    "aria2_download_file", 'aria2_download_m3u8_video', "DownloadFailed"
]

RE_SPEED = re.compile(r'\d+MiB/(\d+)MiB\((\d+)%\).*?DL:(\d*?\.?\d*?)([KM])iB')
RE_AVESPEED = re.compile(r'\|\s*?([\S]*?)([KM])iB/s\|')

class DownloadFailed(Exception):
    pass

def aria2_download_file(url, filename, dirname='.'):
    cnt = 0
    while cnt < 3:
        try:
            cmd = aira2_cmd.format(url=url, dirname=dirname, filename=filename)
            p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, universal_newlines=True, encoding='utf8')
            lines = ''
            while p.poll() is None:
                line = p.stdout.readline().strip()
                if filename.endswith('.mp4') and line:
                    lines += line
                    match = RE_SPEED.search(line)
                    if match:
                        size, percent, speed, unit = match.groups()
                        percent = float(percent)
                        speed = float(speed)
                        if unit == 'K':
                            speed /= 1024
                        per = min(int(LENGTH*percent/100) , LENGTH)
                        print('\r  |-['+per*'*'+(LENGTH-per)*'.'+'] {:.0f}% {:.2f}M/s'.format(percent,speed),end=' (ctrl+c中断)')
            if p.returncode != 0:
                cnt += 1
                if cnt==1:
                    clear_files(dirname, filename)
                    sleep(0.16)
            else:
                if filename.endswith('.mp4'):
                    match = RE_AVESPEED.search(lines)
                    if match:
                        ave_speed, unit = match.groups()
                        ave_speed = float(ave_speed)
                        if unit == 'K':
                            ave_speed /= 1024
                    print('\r  |-['+LENGTH*'*'+'] {:.0f}% {:.2f}M/s'.format(100,ave_speed),end='  (完成)    \n')
                return
        finally:
            p.kill()   # 保证子进程已终止
    clear_files(dirname, filename)
    raise DownloadFailed("download failed")


# 如果将各个ts片段的url传进来，当视频片段较多(约>100)时会导致aria命令行过长，从而报错
# 所以这里将各个url写到urlFile里面，再将文件名传进来即可
def aria2_download_m3u8_video(video_name, video_dir, urlsFile, size=None):
    cnt = 0
    while cnt < 3:
        try:
            cmd = aira2_download_from_file.format(fileName=urlsFile)
            startTime = time()
            p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, universal_newlines=True, encoding='utf8')
            while p.poll() is None:
                # 如果调用p.stdout.read()就会一直阻塞到子进程调用完成，非常坑！！！
                line = p.stdout.readline().strip()
                # print('\r  |-[ ' + '*'*10 + '下载中,请稍后' + '*'*10 + ' ]', end=' (ctrl+c中断)')
                downloaded = sum([os.path.getsize(file) for file in os.listdir() if file.endswith('.ts')])

                if downloaded < size:
                    try:
                        percent = min((downloaded / size) * 100, 100)
                    except ZeroDivisionError:
                        percent = 0
                    speed = (downloaded/ (1024 * 1024) / (time() - startTime))
                    per = min(int(LENGTH*percent/100) , LENGTH)
                    print('\r  |-[' + per * '*' + (LENGTH - per) * '.' + '] {:.0f}% {:.2f}M/s'.format(percent, speed), end=' (ctrl+c中断)')
                else:
                    p.stdout.readlines()
            if p.returncode != 0:
                cnt += 1
                if cnt==1:
                    clear_ts()
                    sleep(0.16)
            else:
                ave_speed = size / (1024 * 1024) / (time() - startTime)
                print('\r  |-[' + '*'*10  + '下载完成,合并文件中' + '*'*10 + '] {:.0f}% {:.2f}M/s'.format(100, ave_speed), end='')
                merge_ts(video_name, video_dir, urlsFile)
                return
        except Exception as e:
            cnt += 1
            print(e)
        finally:
            p.kill()   # 保证子进程已终止
    clear_ts()
    raise DownloadFailed("download failed")


def clear_files(dirname, filename):
    filepath = os.path.join(dirname, filename)
    if os.path.exists(filepath):
        os.remove(filepath)
    if os.path.exists(filepath+'.aria2'):
        os.remove(filepath + '.aria2')

def clear_ts():
    pass

def merge_ts(video_name, video_dir, urlsFile):
    f = open(urlsFile, 'r')
    files = [re.search('.+/(.+\.ts)', file.strip()).group(1) for file in f.readlines()]
    f.close()

    #先将视频片段合并为稍大一点的文件，
    # 避免一次性合并所有文件导致的命令太长报错
    video_parts = []
    for i in range(len(files) // 100 + 1):
        shellStr = ''
        for file in files[i * 100:(i + 1) * 100]:
            shellStr += file + '+'

        cmd = 'copy /b ' + shellStr[:-1] + ' part_' + str(i)
        execute_cmd(cmd)
        video_parts.append('part_' + str(i))
    
    shellStr = ''
    for part in video_parts:
        shellStr += part + '+'
    
    cmd = 'copy /b ' + shellStr[:-1] + ' "' + os.path.join(video_dir, video_name) + '".mp4'
    execute_cmd(cmd)
    return


def execute_cmd(cmd):
    cnt = 0
    while cnt < 3:
        try:
            p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)

            while p.poll() is None:
                line = p.stdout.readline()

            if p.returncode != 0:
                print('命令执行失败,返回码:', p.returncode, '尝试第%d次' % (cnt + 1))
                print(stdout)
                cnt += 1
            return
        except Exception as e:
            print(e)
            return
        finally:
            p.kill()  # 保证子进程已终止
              
