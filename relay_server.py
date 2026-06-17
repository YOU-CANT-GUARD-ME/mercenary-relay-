"""
MERCENARY - Relay Server
Run this on any public server (Railway, Render, VPS, etc.)
Players connect to this to find each other.
"""
import asyncio
import json
import random
import string
import websockets

rooms = {}  # room_code -> {host: ws, guest: ws}

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

            # ── HOST creates a room ──────────────────────────────────────────
            if action == "host":
                room_code = make_code()
                rooms[room_code] = {"host": ws, "guest": None}
                role = "host"
                await ws.send(json.dumps({"action": "room_created", "code": room_code}))
                print(f"[+] Room {room_code} created")

            # ── GUEST joins a room ───────────────────────────────────────────
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
                    # Tell host that guest connected
                    host_ws = rooms[room_code]["host"]
                    await host_ws.send(json.dumps({"action": "guest_joined"}))
                    print(f"[+] Guest joined room {room_code}")

            # ── GAME STATE relay ─────────────────────────────────────────────
            elif action == "state":
                if room_code and room_code in rooms:
                    room = rooms[room_code]
                    # Forward to the other player
                    if role == "host" and room["guest"]:
                        await room["guest"].send(raw)
                    elif role == "guest" and room["host"]:
                        await room["host"].send(raw)

    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        # Clean up room
        if room_code and room_code in rooms:
            if role == "host":
                # Notify guest if present
                room = rooms[room_code]
                if room.get("guest"):
                    try:
                        await room["guest"].send(json.dumps({"action": "opponent_left"}))
                    except:
                        pass
                del rooms[room_code]
                print(f"[-] Room {room_code} closed")
            elif role == "guest":
                rooms[room_code]["guest"] = None
                host_ws = rooms[room_code].get("host")
                if host_ws:
                    try:
                        await host_ws.send(json.dumps({"action": "opponent_left"}))
                    except:
                        pass

async def main():
    port = 8765
    print(f"Relay server running on port {port}")
    async with websockets.serve(handler, "0.0.0.0", port):
        await asyncio.Future()  # run forever

if __name__ == "__main__":
    asyncio.run(main())