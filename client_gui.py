import asyncio
import threading
import tkinter as tk
from tkinter import scrolledtext
import pyaudio
import websockets
import numpy as np
import noisereduce as nr

# Настройки аудио
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 44100
CHUNK = 1024

# WebSocket URI (замените на ваш серверный адрес)
SERVER_URI = "wss://your-server-ip:8765"


class VoiceChatClient:
    def __init__(self, uri, gui):
        self.uri = uri
        self.gui = gui
        self.audio = pyaudio.PyAudio()
        self.stream_in = self.audio.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True,
                                         frames_per_buffer=CHUNK)
        self.stream_out = self.audio.open(format=FORMAT, channels=CHANNELS, rate=RATE, output=True,
                                          frames_per_buffer=CHUNK)
        self.running = True

    def apply_noise_suppression(self, data):
        # Преобразуем бинарные данные в numpy массив
        data_np = np.frombuffer(data, dtype=np.int16)

        # Применяем шумоподавление
        reduced_noise = nr.reduce_noise(y=data_np, sr=RATE)

        # Преобразуем обратно в бинарный формат
        return reduced_noise.astype(np.int16).tobytes()

    async def send_audio(self, websocket):
        while self.running:
            try:
                data = self.stream_in.read(CHUNK, exception_on_overflow=False)
                filtered_data = self.apply_noise_suppression(data)
                await websocket.send(filtered_data)
            except Exception as e:
                self.gui.display_message(f"Ошибка отправки аудио: {e}")
                self.running = False

    async def receive_audio(self, websocket):
        try:
            async for message in websocket:
                self.stream_out.write(message)
        except Exception as e:
            self.gui.display_message(f"Ошибка получения аудио: {e}")
            self.running = False

    async def run(self):
        try:
            async with websockets.connect(self.uri, ssl=True) as websocket:
                send_task = asyncio.create_task(self.send_audio(websocket))
                receive_task = asyncio.create_task(self.receive_audio(websocket))
                await asyncio.gather(send_task, receive_task)
        except Exception as e:
            self.gui.display_message(f"Ошибка подключения: {e}")

    def start(self):
        asyncio.run(self.run())

    def stop(self):
        self.running = False
        self.stream_in.stop_stream()
        self.stream_in.close()
        self.stream_out.stop_stream()
        self.stream_out.close()
        self.audio.terminate()


class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Голосовой Чат")

        self.text_area = scrolledtext.ScrolledText(root, wrap=tk.WORD, width=50, height=10, state='disabled')
        self.text_area.pack(padx=10, pady=10)

        self.connect_button = tk.Button(root, text="Подключиться", command=self.connect)
        self.connect_button.pack(pady=5)

        self.disconnect_button = tk.Button(root, text="Отключиться", command=self.disconnect, state=tk.DISABLED)
        self.disconnect_button.pack(pady=5)

        self.client = None
        self.thread = None

    def display_message(self, message):
        self.text_area.config(state='normal')
        self.text_area.insert(tk.END, message + "\n")
        self.text_area.see(tk.END)
        self.text_area.config(state='disabled')

    def connect(self):
        self.client = VoiceChatClient(SERVER_URI, self)
        self.thread = threading.Thread(target=self.client.start, daemon=True)
        self.thread.start()
        self.display_message("Подключение к серверу...")
        self.connect_button.config(state=tk.DISABLED)
        self.disconnect_button.config(state=tk.NORMAL)

    def disconnect(self):
        if self.client:
            self.client.stop()
            self.display_message("Отключено от сервера.")
        self.connect_button.config(state=tk.NORMAL)
        self.disconnect_button.config(state=tk.DISABLED)


def main():
    root = tk.Tk()
    app = App(root)
    root.protocol("WM_DELETE_WINDOW", app.disconnect)
    root.mainloop()


if __name__ == "__main__":
    main()
