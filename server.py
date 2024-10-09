import asyncio
import websockets
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("voicechat_server")

clients = set()

async def handler(websocket, path):
    clients.add(websocket)
    logger.info(f"Клиент подключён: {websocket.remote_address}")
    try:
        async for message in websocket:
            # Рассылаем полученное сообщение всем остальным клиентам
            for client in clients:
                if client != websocket:
                    await client.send(message)
    except websockets.exceptions.ConnectionClosed as e:
        logger.info(f"Клиент отключился: {websocket.remote_address}")
    finally:
        clients.remove(websocket)

async def main():
    server = await websockets.serve(handler, "localhost", 8765)
    logger.info("WebSocket сервер запущен на ws://localhost:8765")
    await server.wait_closed()

if __name__ == "__main__":
    asyncio.run(main())
