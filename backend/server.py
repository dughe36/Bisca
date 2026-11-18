"""Bisca — FastAPI server with auth, rooms, and WebSocket game sync."""
from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

import os
import uuid
import json
import logging
import asyncio
from datetime import datetime, timezone
from typing import Optional, List

from fastapi import FastAPI, APIRouter, HTTPException, Request, Response, Depends, WebSocket, WebSocketDisconnect
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field

from auth import (
    hash_password, verify_password, create_access_token, decode_token,
    current_user, set_auth_cookie, clear_auth_cookie,
)
from rooms import room_manager, Room


mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

app = FastAPI(title="Bisca")
api = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("bisca")


# ---------- Models ----------
class RegisterIn(BaseModel):
    username: str
    password: str


class LoginIn(BaseModel):
    username: str
    password: str


class BidIn(BaseModel):
    bid: int


class PlayCardIn(BaseModel):
    card_id: str
    re_denari_as_zero: Optional[bool] = None


class ChatIn(BaseModel):
    text: str


# ---------- Auth helpers ----------
async def get_user(request: Request):
    return await current_user(request, db)


# ---------- Auth Endpoints ----------
@api.post("/auth/register")
async def register(payload: RegisterIn, response: Response):
    username = payload.username.strip().lower()
    if len(username) < 3 or len(username) > 20:
        raise HTTPException(400, "Username tra 3 e 20 caratteri")
    if len(payload.password) < 4:
        raise HTTPException(400, "Password troppo corta (min 4)")
    existing = await db.users.find_one({"username": username})
    if existing:
        raise HTTPException(400, "Username già in uso")
    user = {
        "id": str(uuid.uuid4()),
        "username": username,
        "password_hash": hash_password(payload.password),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "stats": {"games_played": 0, "wins": 0, "total_points": 0},
    }
    await db.users.insert_one(user)
    token = create_access_token(user["id"], user["username"])
    set_auth_cookie(response, token)
    user.pop("_id", None); user.pop("password_hash", None)
    return {"user": user, "token": token}


@api.post("/auth/login")
async def login(payload: LoginIn, response: Response):
    username = payload.username.strip().lower()
    user = await db.users.find_one({"username": username})
    if not user or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(401, "Username o password non validi")
    token = create_access_token(user["id"], user["username"])
    set_auth_cookie(response, token)
    user.pop("_id", None); user.pop("password_hash", None)
    return {"user": user, "token": token}


@api.post("/auth/logout")
async def logout(response: Response):
    clear_auth_cookie(response)
    return {"ok": True}


@api.get("/auth/me")
async def me(user=Depends(get_user)):
    return user


@api.get("/leaderboard")
async def leaderboard():
    cursor = db.users.find({}, {"_id": 0, "password_hash": 0}).sort([("stats.wins", -1)]).limit(20)
    return [u async for u in cursor]


# ---------- Room endpoints ----------
@api.post("/rooms/create")
async def create_room(user=Depends(get_user)):
    room = room_manager.create(user["id"], user["username"])
    return {"code": room.code, "id": room.id}


@api.post("/rooms/{code}/join")
async def join_room(code: str, user=Depends(get_user)):
    room = room_manager.get_by_code(code.upper())
    if not room:
        raise HTTPException(404, "Stanza non trovata")
    try:
        room.add_player(user["id"], user["username"])
    except ValueError as e:
        raise HTTPException(400, str(e))
    await broadcast_room(room)
    return {"code": room.code, "id": room.id}


@api.get("/rooms/{code}")
async def get_room(code: str, user=Depends(get_user)):
    room = room_manager.get_by_code(code.upper())
    if not room:
        raise HTTPException(404, "Stanza non trovata")
    return room.to_public(viewer_id=user["id"])


# ---------- WebSocket ----------
async def broadcast_room(room: Room):
    """Send tailored state to each connected player."""
    dead = []
    for uid, ws in list(room.connections.items()):
        try:
            state = room.to_public(viewer_id=uid)
            await ws.send_json({"type": "state", "state": state})
        except Exception:
            dead.append(uid)
    for uid in dead:
        room.connections.pop(uid, None)


async def record_game_end(room: Room):
    """Persist stats when game finishes."""
    if not room.game or room.status == "finished":
        return
    room.status = "finished"
    winner = room.game.winner
    for p in room.players:
        uid = p["user_id"]
        inc = {"stats.games_played": 1}
        if uid == winner:
            inc["stats.wins"] = 1
        inc["stats.total_points"] = int(room.game.scores.get(uid, 0))
        await db.users.update_one({"id": uid}, {"$inc": inc})


@app.websocket("/api/ws/{code}")
async def ws_room(websocket: WebSocket, code: str, token: str = ""):
    # authenticate via query token
    await websocket.accept()
    try:
        payload = decode_token(token)
        user_id = payload["sub"]
        username = payload.get("username", "player")
    except Exception:
        await websocket.send_json({"type": "error", "message": "Auth fallita"})
        await websocket.close()
        return

    room = room_manager.get_by_code(code.upper())
    if not room:
        await websocket.send_json({"type": "error", "message": "Stanza non trovata"})
        await websocket.close()
        return

    # If player not in room and status waiting, add
    if not any(p["user_id"] == user_id for p in room.players):
        try:
            room.add_player(user_id, username)
        except ValueError as e:
            await websocket.send_json({"type": "error", "message": str(e)})
            await websocket.close()
            return

    room.connections[user_id] = websocket
    for p in room.players:
        if p["user_id"] == user_id:
            p["connected"] = True
    await broadcast_room(room)

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except Exception:
                continue
            mtype = msg.get("type")
            async with room.lock:
                try:
                    if mtype == "start_game":
                        room.start_game(user_id)
                    elif mtype == "leave":
                        room.remove_player(user_id)
                    elif mtype == "chat":
                        text = str(msg.get("text", ""))[:200]
                        if text.strip():
                            room.chat.append({"user_id": user_id, "username": username, "text": text, "ts": datetime.now(timezone.utc).isoformat()})
                    elif mtype == "bid" and room.game:
                        err = room.game.place_bid(user_id, int(msg.get("bid", -1)))
                        if err:
                            await websocket.send_json({"type": "error", "message": err})
                    elif mtype == "play_card" and room.game:
                        err = room.game.play_card(user_id, msg.get("card_id"), msg.get("re_denari_as_zero"))
                        if err:
                            await websocket.send_json({"type": "error", "message": err})
                    elif mtype == "re_denari_choice" and room.game:
                        err = room.game.resolve_re_denari(user_id, bool(msg.get("as_zero", False)))
                        if err:
                            await websocket.send_json({"type": "error", "message": err})
                    elif mtype == "continue_trick" and room.game:
                        err = room.game.continue_after_trick()
                        if err:
                            await websocket.send_json({"type": "error", "message": err})
                    elif mtype == "next_round" and room.game:
                        if room.game.phase == "round_end":
                            room.game.start_round()
                    else:
                        pass
                except ValueError as e:
                    await websocket.send_json({"type": "error", "message": str(e)})
            # auto-advance trick after 3s? We'll let clients trigger continue_trick.
            if room.game and room.game.phase == "finished":
                await record_game_end(room)
            await broadcast_room(room)
    except WebSocketDisconnect:
        room.connections.pop(user_id, None)
        for p in room.players:
            if p["user_id"] == user_id:
                p["connected"] = False
        if room.status == "waiting":
            room.remove_player(user_id)
            if not room.players:
                room_manager.delete(room)
                return
        await broadcast_room(room)


# ---------- Health ----------
@api.get("/")
async def root():
    return {"status": "ok", "service": "bisca"}


app.include_router(api)

# CORS — allow_credentials with wildcard is invalid; use FRONTEND_URL if set
_origins_env = os.environ.get("CORS_ORIGINS", "*")
_frontend = os.environ.get("FRONTEND_URL")
if _origins_env == "*" and _frontend:
    allowed_origins = [_frontend, "http://localhost:3000"]
else:
    allowed_origins = _origins_env.split(",") if _origins_env != "*" else ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    try:
        await db.users.create_index("username", unique=True)
    except Exception as e:
        logger.warning(f"index create: {e}")


@app.on_event("shutdown")
async def shutdown():
    client.close()
