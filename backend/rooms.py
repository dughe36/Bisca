"""Room manager for Bisca multiplayer."""
import asyncio
import random
import string
import uuid
from typing import Dict, List, Optional
from fastapi import WebSocket

from game import BiscaGame


def gen_code() -> str:
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=5))


class Room:
    def __init__(self, code: str, host_id: str):
        self.id = str(uuid.uuid4())
        self.code = code
        self.host_id = host_id
        self.players: List[dict] = []  # {user_id, username, connected}
        self.status = "waiting"  # waiting|playing|finished
        self.chat: List[dict] = []
        self.game: Optional[BiscaGame] = None
        self.connections: Dict[str, WebSocket] = {}
        self.lock = asyncio.Lock()

    def add_player(self, user_id: str, username: str):
        if any(p["user_id"] == user_id for p in self.players):
            return
        if len(self.players) >= 8:
            raise ValueError("Stanza piena")
        if self.status != "waiting":
            raise ValueError("Partita già iniziata")
        self.players.append({"user_id": user_id, "username": username, "connected": False})

    def remove_player(self, user_id: str):
        if self.status == "waiting":
            self.players = [p for p in self.players if p["user_id"] != user_id]
            if self.host_id == user_id and self.players:
                self.host_id = self.players[0]["user_id"]

    def start_game(self, user_id: str):
        if user_id != self.host_id:
            raise ValueError("Solo l'host può iniziare la partita")
        if len(self.players) < 3:
            raise ValueError("Servono almeno 3 giocatori")
        if len(self.players) > 8:
            raise ValueError("Massimo 8 giocatori")
        pids = [p["user_id"] for p in self.players]
        self.game = BiscaGame(pids, dealer_index=0)
        self.game.start_round()
        self.status = "playing"

    def to_public(self, viewer_id: Optional[str] = None) -> dict:
        return {
            "id": self.id,
            "code": self.code,
            "host_id": self.host_id,
            "status": self.status,
            "players": [{"user_id": p["user_id"], "username": p["username"], "connected": p["connected"]} for p in self.players],
            "chat": self.chat[-50:],
            "game": self.game.public_state(viewer_id) if self.game else None,
        }


class RoomManager:
    def __init__(self):
        self.rooms: Dict[str, Room] = {}  # by code
        self.rooms_by_id: Dict[str, Room] = {}

    def create(self, host_id: str, host_name: str) -> Room:
        for _ in range(20):
            code = gen_code()
            if code not in self.rooms:
                break
        else:
            raise RuntimeError("Impossibile generare codice")
        room = Room(code, host_id)
        room.add_player(host_id, host_name)
        self.rooms[code] = room
        self.rooms_by_id[room.id] = room
        return room

    def get_by_code(self, code: str) -> Optional[Room]:
        return self.rooms.get(code.upper())

    def get_by_id(self, room_id: str) -> Optional[Room]:
        return self.rooms_by_id.get(room_id)

    def delete(self, room: Room):
        self.rooms.pop(room.code, None)
        self.rooms_by_id.pop(room.id, None)


room_manager = RoomManager()
