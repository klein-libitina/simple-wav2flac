#  这是一个简单的wav2flac程序
# 怎么使用
You can run the program by typing the following command in the command line

```javascript
python wav2flac5.py /path/to/input -c 8 -t 8 --use-process
```
###以下是命令行参数 -c 12 -t 8 --use-process 的详细说明：

####1. -c 12（压缩级别）
        作用：设置 FLAC 文件的压缩级别。

        取值范围：0 到 12（0 为最低压缩，12 为最高压缩）。

        低级别（如 0-5）：压缩速度快，但文件体积较大。

        高级别（如 6-12）：压缩速度慢，但文件体积更小。

        默认值：8（平衡压缩速度和文件大小）。

        示例：-c 12 表示使用最高压缩级别，生成最小体积的 FLAC 文件。

####2. -t 8（并发线程/进程数）
        作用：指定程序并行处理任务的线程或进程数量。

        默认值：os.cpu_count()（自动检测当前系统的 CPU 核心数）。

        适用场景：

        线程池（默认）：适合 I/O 密集型任务（如文件读写）。

        进程池（需配合 --use-process）：适合 CPU 密集型任务（如音视频编码）。

        示例：-t 8 表示使用 8 个线程或进程并行处理文件，加快转换速度。

####3. --use-process（使用进程池）
        作用：强制程序使用进程池（ProcessPoolExecutor）替代默认的线程池（ThreadPoolExecutor）。

        适用场景：

        CPU 密集型任务：例如音频编码，进程池可绕过 Python 的全局解释器锁（GIL），充分利用多核 CPU。

        稳定性要求高：进程间内存隔离，单个进程崩溃不会影响其他进程。

        示例：--use-process 表示启用进程池，通常与 -t 参数配合使用（如 -t 8）。
