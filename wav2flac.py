import os
import subprocess
import argparse
import logging
import datetime
import uuid
import shutil
import platform
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from functools import partial

# 硬件加速配置
GPU_CONFIG = {
    "nvidia": {
        "hwaccel": "cuda",
        "hwaccel_output_format": "cuda",
        "codec": "flac",
        "extra_params": ["-hwaccel_device", "0"]
    },
    "amd": {
        "hwaccel": "d3d11va",
        "hwaccel_output_format": "d3d11",
        "codec": "flac",
        "extra_params": []
    },
    "intel": {
        "hwaccel": "qsv",
        "hwaccel_output_format": "qsv",
        "codec": "flac",
        "extra_params": ["-load_plugin", "hevc_hw"]
    }
}

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WAV_RAW_DIR = os.path.join(SCRIPT_DIR, "WAV_Raw")

def setup_logging(temp_log_path=None):
    """多进程安全的日志配置"""
    logger = logging.getLogger()
    if logger.handlers:
        return temp_log_path
    
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    
    if temp_log_path is None:
        log_date = datetime.datetime.now().strftime("%Y-%m-%d")
        temp_log_filename = f"temp_{log_date}_{uuid.uuid4().hex}.txt"
        temp_log_path = os.path.join(SCRIPT_DIR, temp_log_filename)
    
    file_handler = logging.FileHandler(temp_log_path, mode='a')
    file_handler.setFormatter(formatter)
    
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    
    return temp_log_path

def merge_logs(temp_log_path, log_date, file_handler):
    main_log_path = f"{log_date}.txt"
    try:
        file_handler.close()
        logging.getLogger().removeHandler(file_handler)
        if os.path.exists(temp_log_path):
            with open(temp_log_path, 'r') as src, open(main_log_path, 'a') as dest:
                dest.write(src.read() + '\n')
            os.remove(temp_log_path)
    except Exception as e:
        print(f"日志合并失败（保留临时文件 {temp_log_path}）: {str(e)}")

def detect_gpu_type():
    try:
        if platform.system() == "Windows":
            import wmi
            c = wmi.WMI()
            for gpu in c.Win32_VideoController():
                if "NVIDIA" in gpu.Name:
                    return "nvidia"
                elif "AMD" in gpu.Name:
                    return "amd"
                elif "Intel" in gpu.Name:
                    return "intel"
        elif platform.system() == "Linux":
            lspci = subprocess.check_output(["lspci"]).decode()
            if "NVIDIA" in lspci:
                return "nvidia"
            elif "AMD" in lspci:
                return "amd"
            elif "Intel" in lspci:
                return "intel"
        return "unknown"
    except Exception:
        return "unknown"

def build_ffmpeg_command(input_path, output_path, compression_level):
    gpu_type = detect_gpu_type()
    config = GPU_CONFIG.get(gpu_type, {})
    
    cmd = [
        'ffmpeg',
        '-hwaccel', config.get("hwaccel", "auto"),
        '-hwaccel_output_format', config.get("hwaccel_output_format", "nv12")
    ]
    
    if config.get("extra_params"):
        cmd.extend(config["extra_params"])
    
    cmd.extend([
        '-i', input_path,
        '-compression_level', str(compression_level),
        '-c:a', config.get("codec", "flac"),
        '-y',
        '-loglevel', 'error',
        output_path
    ])
    return cmd

def convert_wav_to_flac(input_path, compression_level=6):
    output_path = os.path.splitext(input_path)[0] + ".flac"
    
    if os.path.exists(output_path):
        logging.warning(f"文件已存在，跳过: {output_path}")
        return
    
    try:
        cmd = build_ffmpeg_command(input_path, output_path, compression_level)
        result = subprocess.run(
            cmd,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        
        if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
            raise RuntimeError("输出文件生成失败")
            
        logging.info(f"转换成功: {input_path} -> {output_path}")
        
        os.makedirs(WAV_RAW_DIR, exist_ok=True)
        dest_path = os.path.join(WAV_RAW_DIR, os.path.basename(input_path))
        if os.path.exists(dest_path):
            base, ext = os.path.splitext(os.path.basename(input_path))
            dest_path = os.path.join(WAV_RAW_DIR, f"{base}_{uuid.uuid4().hex[:6]}{ext}")
        shutil.move(input_path, dest_path)
        logging.info(f"移动原始文件到: {dest_path}")

    except subprocess.CalledProcessError as e:
        error_msg = f"FFmpeg错误: {e.stderr.decode().strip()}"
        logging.error(f"转换失败 {input_path}: {error_msg}")
    except Exception as e:
        logging.error(f"发生错误 {input_path}: {str(e)}")

def find_wav_files(root_dir):
    wav_files = []
    wav_raw_abs = os.path.abspath(WAV_RAW_DIR)
    try:
        for dirpath, dirnames, filenames in os.walk(root_dir):
            current_abs = os.path.abspath(dirpath)
            if current_abs == wav_raw_abs:
                dirnames[:] = []
                continue
            for filename in filenames:
                if filename.lower().endswith('.wav'):
                    wav_files.append(os.path.join(dirpath, filename))
        return wav_files
    except Exception as e:
        logging.error(f"目录扫描失败: {str(e)}")
        raise

def process_file(file_path, compression_level, log_path):
    """子进程任务入口"""
    setup_logging(log_path)
    convert_wav_to_flac(file_path, compression_level)


def main():
    os.makedirs(WAV_RAW_DIR, exist_ok=True)
    temp_log_path = setup_logging()  # 主进程初始化日志
    log_date = datetime.datetime.now().strftime("%Y-%m-%d")
    file_handler = logging.getLogger().handlers[0]  # 获取第一个文件handler
    
    try:
        parser = argparse.ArgumentParser(description='高性能WAV转FLAC工具（支持硬件加速）')
        parser.add_argument('input_dir', metavar='FOLDER', type=str, help='输入目录路径')
        parser.add_argument(
            '-c', '--compression',
            type=int,
            default=6,
            choices=range(0, 13),
            help='FLAC压缩级别 (0-12，默认:6)'
        )
        parser.add_argument(
            '-t', '--threads',
            type=int,
            default=os.cpu_count(),
            help='并发线程/进程数 (默认:CPU核心数)'
        )
        parser.add_argument(
            '--use-process',
            action='store_true',
            help='使用进程池替代线程池'
        )
        args = parser.parse_args()

        if not os.path.isdir(args.input_dir):
            raise ValueError(f"无效输入目录: {args.input_dir}")

        logging.info(f"检测到GPU类型: {detect_gpu_type().upper()}")
        wav_files = find_wav_files(args.input_dir)
        logging.info(f"找到 {len(wav_files)} 个待转换文件")

        Executor = ProcessPoolExecutor if args.use_process else ThreadPoolExecutor
        worker = partial(process_file, 
                       compression_level=args.compression,
                       log_path=temp_log_path)
        with Executor(max_workers=args.threads) as executor:
            list(executor.map(worker, wav_files))

    except Exception as e:
        logging.error(f"程序运行失败: {str(e)}")
    finally:
        merge_logs(temp_log_path, log_date, file_handler)

if __name__ == "__main__":
    main()
