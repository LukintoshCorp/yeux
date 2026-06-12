import asyncio
import websockets
import json

async def send_data():
    uri = "ws://localhost:8765"
    async with websockets.connect(uri) as ws:
        x = 0

        while True:
            x += 10
            if x > 1200:
                x = 0

            data = {
                "x": x,
                "y": 500,
                "blink": False
            }

            await ws.send(json.dumps(data))
            await asyncio.sleep(0.016)

asyncio.run(send_data())