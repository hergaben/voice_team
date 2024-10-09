import asyncio
import threading
import tkinter as tk
from tkinter import scrolledtext
import pyaudio
import websockets
import numpy as np
import noisereduce as nr
import logging
import time

# Настройки аудио
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 44100
CHUNK = 256  # Уменьшили размер CHUNK для уменьшения задержки

# WebSocket URI (замените на ваш серверный адрес)
SERVER_URI = "wss://gamekatalog.ru/ws/"

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


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
        # try:
        #     # Преобразуем бинарные данные в numpy массив
        #     data_np = np.frombuffer(data, dtype=np.int16)
        #
        #     # Применяем шумоподавление
        #     reduced_noise = nr.reduce_noise(y=data_np, sr=RATE)
        #
        #     # Преобразуем обратно в бинарный формат
        #     return reduced_noise.astype(np.int16).tobytes()
        # except Exception as e:
        #     logging.error(f"Ошибка при шумоподавлении: {e}")
        return data  # Возвращаем необработанные данные в случае ошибки

    async def send_audio(self, websocket):
        while self.running:
            try:
                data = self.stream_in.read(CHUNK, exception_on_overflow=False)
                filtered_data = self.apply_noise_suppression(data)
                await websocket.send(filtered_data)
            except Exception as e:
                logging.error(f"Ошибка отправки аудио: {e}")
                self.gui.display_message(f"Ошибка отправки аудио: {e}")
                self.running = False
                await websocket.close()

    async def receive_audio(self, websocket):
        try:
            async for message in websocket:
                self.stream_out.write(message)
        except websockets.exceptions.ConnectionClosed as e:
            logging.warning(f"WebSocket соединение закрыто: {e}")
            self.gui.display_message("Соединение с сервером закрыто.")
            self.running = False
        except Exception as e:
            logging.error(f"Ошибка получения аудио: {e}")
            self.gui.display_message(f"Ошибка получения аудио: {e}")
            self.running = False

    async def run(self):
        try:
            async with websockets.connect(self.uri, ssl=True) as websocket:
                logging.info("Подключено к серверу WebSocket.")
                self.gui.display_message("Подключено к серверу.")
                send_task = asyncio.create_task(self.send_audio(websocket))
                receive_task = asyncio.create_task(self.receive_audio(websocket))
                await asyncio.gather(send_task, receive_task)
        except Exception as e:
            logging.error(f"Ошибка подключения: {e}")
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

        self.ping_interval = 5  # интервал пинга в секундах
        self.ping_task = None

    def display_message(self, message):
        self.text_area.config(state='normal')
        self.text_area.insert(tk.END, message + "\n")
        self.text_area.see(tk.END)
        self.text_area.config(state='disabled')

    # Добавьте новый метод для отправки пинга
    async def send_ping(self):
        while self.client:
            timestamp = int(time.time() * 1000)  # Временная метка в миллисекундах
            await self.client.websocket.send(f"PING:{timestamp}")
            await asyncio.sleep(self.ping_interval)

    # Обработка ответа пинга
    async def receive_audio(self, websocket):
        try:
            async for message in websocket:
                if message.startswith("PONG:"):
                    # Измеряем пинг
                    timestamp = message.split(":")[1]
                    ping_time = int(time.time() * 1000) - int(timestamp)
                    self.display_message(f"Пинг: {ping_time} мс")
                else:
                    self.stream_out.write(message)
        except Exception as e:
            self.display_message(f"Ошибка получения аудио: {e}")
            self.running = False

    def connect(self):
        self.client = VoiceChatClient(SERVER_URI, self)
        self.ping_task = asyncio.create_task(self.send_ping())
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
