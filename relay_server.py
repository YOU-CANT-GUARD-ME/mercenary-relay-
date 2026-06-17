"""
MERCENARY - Relay Server
Uses aiohttp to handle both HTTP health checks and WebSocket connections.
"""
import asyncio
import json
import random
import string
import os
from aiohttp import web
import aiohttp

rooms = {}

def make_code():
    while True:
        code = ''.join(random.choices(string.digits, k=4))
        if code not in rooms:
            return code

async def health(request):
    return web.Response(text="OK")

async def websocket_handler(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)

    room_code = None
    role = None

    try:
        async for msg in ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                data = json.loads(msg.data)
                action = data.get("action")

                if action == "host":
                    room_code = make_code()
                    rooms[room_code] = {"host": ws, "guest": None}
                    role = "host"
                    await ws.send_str(json.dumps({"action": "room_created", "code": room_code}))
                    print(f"[+] Room {room_code} created", flush=True)

                elif action == "join":
                    room_code = data.get("code")
                    if room_code not in rooms:
                        await ws.send_str(json.dumps({"action": "error", "msg": "Room not found"}))
                    elif rooms[room_code]["guest"] is not None:
                        await ws.send_str(json.dumps({"action": "error", "msg": "Room is full"}))
                    else:
                        rooms[room_code]["guest"] = ws
                        role = "guest"
                        await ws.send_str(json.dumps({"action": "joined", "code": room_code}))
                        host_ws = rooms[room_code]["host"]
                        await host_ws.send_str(json.dumps({"action": "guest_joined"}))
                        print(f"[+] Guest joined room {room_code}", flush=True)

                elif action == "state":
                    if room_code and room_code in rooms:
                        room = rooms[room_code]
                        if role == "host" and room["guest"]:
                            await room["guest"].send_str(msg.data)
                        elif role == "guest" and room["host"]:
                            await room["host"].send_str(msg.data)

            elif msg.type == aiohttp.WSMsgType.ERROR:
                print(f"[!] WS error: {ws.exception()}", flush=True)

    finally:
        if room_code and room_code in rooms:
            if role == "host":
                room = rooms[room_code]
                if room.get("guest"):
                    try:
                        await room["guest"].send_str(json.dumps({"action": "opponent_left"}))
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
                            await host_ws.send_str(json.dumps({"action": "opponent_left"}))
                        except:
                            pass

    return ws

app = web.Application()
app.router.add_get("/", health)
app.router.add_get("/ws", websocket_handler)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8765))
    print(f"Starting on port {port}", flush=True)
    web.run_app(app, host="0.0.0.0", port=port)