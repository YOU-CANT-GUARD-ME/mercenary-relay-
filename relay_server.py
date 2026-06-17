"""
MERCENARY - Relay Server
Compatible with websockets 12+ and Python 3.14
"""
import asyncio
import json
import random
import string
import os
import websockets
from websockets.asyncio.server import serve

rooms = {}

def make_code():
    while True:
        code = ''.join(random.choices(string.digits, k=4))
        if code not in rooms:
            return code

async def handler(ws):
    room_code = None
    role = None
    try:
        async for raw in ws:
            msg = json.loads(raw)
            action = msg.get("action")

            if action == "host":
                room_code = make_code()
                rooms[room_code] = {"host": ws, "guest": None}
                role = "host"
                await ws.send(json.dumps({"action": "room_created", "code": room_code}))
                print(f"[+] Room {room_code} created", flush=True)

            elif action == "join":
                room_code = msg.get("code")
                if room_code not in rooms:
                    await ws.send(json.dumps({"action": "error", "msg": "Room not found"}))
                elif rooms[room_code]["guest"] is not None:
                    await ws.send(json.dumps({"action": "error", "msg": "Room is full"}))
                else:
                    rooms[room_code]["guest"] = ws
                    role = "guest"
                    await ws.send(json.dumps({"action": "joined", "code": room_code}))
                    host_ws = rooms[room_code]["host"]
                    await host_ws.send(json.dumps({"action": "guest_joined"}))
                    print(f"[+] Guest joined room {room_code}", flush=True)

            elif action == "state":
                if room_code and room_code in rooms:
                    room = rooms[room_code]
                    if role == "host" and room["guest"]:
                        await room["guest"].send(raw)
                    elif role == "guest" and room["host"]:
                        await room["host"].send(raw)

    except websockets.exceptions.ConnectionClosed:
        pass
    except Exception as e:
        print(f"[!] Handler error: {e}", flush=True)
    finally:
        if room_code and room_code in rooms:
            if role == "host":
                room = rooms[room_code]
                if room.get("guest"):
                    try:
                        await room["guest"].send(json.dumps({"action": "opponent_left"}))
                    except:
                        pass
                del rooms[room_code]
                print(f"[-] Room {room_code} closed", flush=True)
            elif role == "guest":
                if room_code in rooms:
                    rooms[room_code]["guest"] = None
                    host_ws = rooms[room_code].get("host")
                    if host_ws:
                        try:
                            await host_ws.send(json.dumps({"action": "opponent_left"}))
                        except:
                            pass

async def main():
    port = int(os.environ.get("PORT", 8765))
    print(f"Relay server starting on port {port}", flush=True)
    async with serve(handler, "0.0.0.0", port) as server:
        print(f"Relay server ready!", flush=True)
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())