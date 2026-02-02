import sounddevice as sd
import numpy as np
import websockets
import asyncio
import json
from queue import Queue, Empty
import sys

# 音频配置参数
input_sample_rate = 48000
output_sample_rate = 16000
channels = 1
sample_bits = 16
audio_queue = Queue()

def audio_callback(indata, frames, time, status):
    """音频输入回调函数"""
    if status:
        print(status, file=sys.stderr)
    audio_queue.put(indata.copy())

def downsample_buffer(buffer, input_sr, output_sr):
    """下采样音频数据"""
    if input_sr == output_sr:
        return buffer
    ratio = input_sr / output_sr
    new_length = int(np.round(len(buffer) / ratio))
    resampled = np.zeros(new_length, dtype=np.float32)

    for i in range(new_length):
        start = int(np.round(i * ratio))
        end = int(np.round((i + 1) * ratio))
        end = min(end, len(buffer))
        resampled[i] = np.mean(buffer[start:end])

    return resampled

def encode_pcm(audio_data):
    """将音频数据编码为PCM格式"""
    int_data = (audio_data * 32767).astype('<i2')  # 小端16位有符号整数
    return int_data.tobytes()

async def send_audio(websocket, stop_event: asyncio.Event):
    """发送音频数据的协程"""
    while not stop_event.is_set():

        await asyncio.sleep(0.5)  # 每500ms发送一次
        chunks = []

        # 从队列中获取所有可用的音频块
        while True:
            try:
                chunks.append(audio_queue.get_nowait())
            except Empty:
                break

        if chunks:
            # 合并并处理音频数据
            audio_data = np.concatenate(chunks)
            resampled = downsample_buffer(audio_data.flatten(),
                                        input_sample_rate,
                                        output_sample_rate)
            pcm_data = encode_pcm(resampled)
            await websocket.send(pcm_data)

async def receive_messages(websocket, stop_event: asyncio.Event, callback):
    
    """接收消息的协程"""
    while not stop_event.is_set():
        try:
            response = await websocket.recv()
            try:
                res_json = json.loads(response)
                if res_json.get('code') == 0:
                    data = res_json.get('data', 'No speech recognized')
                    print(data)
                    if callback:
                        await callback(data)
            except json.JSONDecodeError:
                print("Received non-JSON response:", response)
        except websockets.exceptions.ConnectionClosed:
            print("Connection closed")
async def transcribe_audio(lang='auto', sv=False, callback=None, stop_event=None):
    """主转录函数"""
    params = []
    if lang and lang != 'auto':
        params.append(f'lang={lang}')
    if sv:
        params.append('sv=1')

    query = '?' + '&'.join(params) if params else ''
    uri = f"ws://127.0.0.1:6006/ws/transcribe{query}"

    # stop_event = asyncio.Event()
    stream = None

    try:
        # 初始化音频输入流
        stream = sd.InputStream(
            samplerate=input_sample_rate,
            channels=channels,
            dtype='float32',
            callback=audio_callback,
            blocksize=4096
        )

        with stream:
            async with websockets.connect(uri) as websocket:
                # 创建并运行发送和接收任务
                send_task = asyncio.create_task(send_audio(websocket, stop_event))
                recv_task = asyncio.create_task(receive_messages(websocket, stop_event, callback))
                await asyncio.gather(send_task, recv_task, return_exceptions=True)
                print("send_task和recv_task开启")

                while not stop_event.is_set():
                    await asyncio.sleep(0.1)
                    if send_task.done() or recv_task.done():
                        break
                print("send_task和recv_task关闭")
                send_task.cancel()
                recv_task.cancel()


    except KeyboardInterrupt:
        print("\nRecording stopped")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        # stop_event.set()
        if stream and stream.active:
            stream.close()

async def print_callback(data):
    """示例回调函数"""
    print("Transcription:", data)

if __name__ == "__main__":
    try:
        asyncio.run(transcribe_audio(
            lang='auto',
            sv=False,
            callback=print_callback
        ))
    except KeyboardInterrupt:
        print("\nProgram terminated")