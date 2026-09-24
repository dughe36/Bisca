"""End-to-end Bisca backend test: HTTP + WebSocket full game happy path."""
import asyncio, json, os, sys, time, uuid, random
import requests
import websockets

BASE = "https://bisca-online.preview.emergentagent.com"
API = BASE + "/api"
WS_BASE = BASE.replace("https://", "wss://").replace("http://", "ws://") + "/api/ws"

results = {"passed": [], "failed": []}

def log_pass(name): print(f"PASS: {name}"); results["passed"].append(name)
def log_fail(name, err): print(f"FAIL: {name} :: {err}"); results["failed"].append({"name": name, "err": str(err)})


def register(username, password):
    r = requests.post(f"{API}/auth/register", json={"username": username, "password": password}, timeout=10)
    return r


def login(username, password):
    r = requests.post(f"{API}/auth/login", json={"username": username, "password": password}, timeout=10)
    return r


def test_http():
    # register 3 users with unique names
    tag = uuid.uuid4().hex[:6]
    users = []
    for i in range(3):
        u = f"tuser{tag}{i}"
        r = register(u, "testpass")
        if r.status_code != 200:
            log_fail(f"register {u}", f"{r.status_code} {r.text}")
            return None
        d = r.json()
        users.append({"username": u, "password": "testpass", "token": d["token"], "id": d["user"]["id"]})
    log_pass("register 3 users")

    # login existing
    r = login(users[0]["username"], "testpass")
    if r.status_code != 200:
        log_fail("login existing", r.text); return None
    log_pass("login existing user")

    # me with Bearer
    r = requests.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {users[0]['token']}"}, timeout=10)
    if r.status_code != 200 or r.json().get("username") != users[0]["username"]:
        log_fail("auth/me bearer", r.text); return None
    log_pass("auth/me with Bearer")

    # me with cookie
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"username": users[1]["username"], "password": "testpass"}, timeout=10)
    r2 = s.get(f"{API}/auth/me", timeout=10)
    if r2.status_code != 200:
        log_fail("auth/me cookie", r2.text)
    else:
        log_pass("auth/me with cookie")

    # leaderboard
    r = requests.get(f"{API}/leaderboard", timeout=10)
    if r.status_code != 200 or not isinstance(r.json(), list):
        log_fail("leaderboard", r.text); return None
    log_pass("leaderboard returns list")

    # create room requires auth
    r = requests.post(f"{API}/rooms/create", timeout=10)
    if r.status_code == 200:
        log_fail("rooms/create requires auth", "returned 200 without auth")
    else:
        log_pass("rooms/create rejects unauth")

    # create room with auth
    r = requests.post(f"{API}/rooms/create", headers={"Authorization": f"Bearer {users[0]['token']}"}, timeout=10)
    if r.status_code != 200:
        log_fail("rooms/create auth", r.text); return None
    code = r.json()["code"]
    log_pass(f"rooms/create -> {code}")

    # join room bad code
    r = requests.post(f"{API}/rooms/BADXYZ/join", headers={"Authorization": f"Bearer {users[1]['token']}"}, timeout=10)
    if r.status_code != 404:
        log_fail("join bad code -> 404", r.status_code)
    else:
        log_pass("join bad code returns 404")

    # join real room
    r = requests.post(f"{API}/rooms/{code}/join", headers={"Authorization": f"Bearer {users[1]['token']}"}, timeout=10)
    if r.status_code != 200:
        log_fail("join valid", r.text); return None
    log_pass("player2 joined room")

    return {"users": users, "code": code}


async def ws_connect(code, token):
    return await websockets.connect(f"{WS_BASE}/{code}?token={token}", open_timeout=10)


async def recv_state(ws, timeout=1.2, quiet=0.15):
    end = time.time() + timeout
    last_state = None
    while time.time() < end:
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=quiet)
        except asyncio.TimeoutError:
            if last_state is not None:
                return last_state
            continue
        msg = json.loads(raw)
        if msg.get("type") == "state":
            last_state = msg["state"]
        elif msg.get("type") == "error":
            print(f"  WS error: {msg}")
    return last_state


async def drain_all(wss, timeout=1.0, quiet=0.15):
    async def _one(ws):
        return await recv_state(ws, timeout=timeout, quiet=quiet)
    keys = list(wss.keys())
    results = await asyncio.gather(*(_one(wss[k]) for k in keys))
    return dict(zip(keys, results))


async def run_game(data):
    users = data["users"]
    code = data["code"]

    # user2 (third) must join via WS since only 2 in room
    wss = {}
    for u in users:
        wss[u["id"]] = await ws_connect(code, u["token"])
    # initial state broadcast
    states = await drain_all(wss, timeout=1.5)
    host_state = states[users[0]["id"]]
    if not host_state:
        log_fail("initial ws state", "no state"); return
    if len(host_state.get("players", [])) < 3:
        log_fail("3 players in room", f"players={host_state.get('players')}"); return
    log_pass("3 users connected via WS")

    # chat
    await wss[users[0]["id"]].send(json.dumps({"type": "chat", "text": "hello"}))
    states = await drain_all(wss)
    if not any(m.get("text") == "hello" for m in (states[users[0]["id"]] or {}).get("chat", [])):
        log_fail("chat message appended", str(states[users[0]["id"]].get("chat")))
    else:
        log_pass("chat broadcast")

    # start game (host = users[0])
    await wss[users[0]["id"]].send(json.dumps({"type": "start_game"}))
    states = await drain_all(wss, timeout=1.5)
    s0 = states[users[0]["id"]]
    if s0.get("status") != "playing" or (s0.get("game") or {}).get("phase") != "bidding":
        log_fail("start_game -> bidding", f"status={s0.get('status')} phase={(s0.get('game') or {}).get('phase')}")
        return
    log_pass("start_game -> playing/bidding")

    async def latest_state(uid):
        # try to peek any pending, else return last known via a lightweight receive
        try:
            raw = await asyncio.wait_for(wss[uid].recv(), timeout=0.3)
            m = json.loads(raw)
            if m.get("type") == "state":
                return m["state"]
        except asyncio.TimeoutError:
            pass
        return None

    async def get_fresh_state(uid, base=None):
        st = await latest_state(uid)
        return st or base

    async def full_round(base_states):
        """Complete a round: bidding then playing until round_end. Returns final states."""
        cur_states = base_states
        # bidding loop
        for _ in range(20):
            game = cur_states[users[0]["id"]].get("game") or {}
            if game.get("phase") != "bidding":
                break
            bidder = game.get("current_bidder")
            cph = game.get("cards_per_hand", 1)
            bid_order = game.get("bid_order", [])
            is_dealer = bidder == bid_order[-1] if bid_order else False
            # simple bid: 0 for everyone; if dealer's 0 would make sum==cph and sum without dealer already == cph, pick 1
            other_sum = sum(v for k, v in (game.get("bids") or {}).items() if v is not None and k != bidder)
            bid = 0
            if is_dealer and (other_sum + 0) == cph:
                bid = 1 if cph >= 1 else 0
            await wss[bidder].send(json.dumps({"type": "bid", "bid": bid}))
            cur_states = await drain_all(wss)
        game = cur_states[users[0]["id"]].get("game") or {}
        if game.get("phase") != "playing":
            log_fail("bidding complete -> playing", f"phase={game.get('phase')}")
            return cur_states
        log_pass(f"bidding complete (round cph={game.get('cards_per_hand')})")

        # playing loop
        for _ in range(100):
            game = cur_states[users[0]["id"]].get("game") or {}
            phase = game.get("phase")
            if phase == "round_end":
                break
            if phase == "playing":
                cp = game.get("current_player")
                if not cp: break
                # viewer=cp sees own hand fully (unless final round: hidden flag, still has id)
                cp_state = cur_states[cp].get("game") or {}
                my_hand = (cp_state.get("hands") or {}).get(cp, [])
                if not my_hand:
                    log_fail("current player has empty hand", cp); return cur_states
                card_id = my_hand[0].get("id")
                if not card_id:
                    log_fail("card missing id", str(my_hand[0])); return cur_states
                # If it's Re di Denari and NOT final round → send with re_denari_as_zero=False for simplicity
                payload = {"type": "play_card", "card_id": card_id}
                if card_id == "denari-10":
                    payload["re_denari_as_zero"] = False
                await wss[cp].send(json.dumps(payload))
                cur_states = await drain_all(wss)
            elif phase == "re_denari_choice":
                pending = game.get("pending_re_denari") or {}
                pid = pending.get("player_id")
                await wss[pid].send(json.dumps({"type": "re_denari_choice", "as_zero": False}))
                cur_states = await drain_all(wss)
                log_pass("re_denari_choice resolved")
            elif phase == "trick_reveal":
                await wss[users[0]["id"]].send(json.dumps({"type": "continue_trick"}))
                cur_states = await drain_all(wss)
            else:
                break
        game = cur_states[users[0]["id"]].get("game") or {}
        if game.get("phase") != "round_end":
            log_fail("round -> round_end", f"phase={game.get('phase')}")
        else:
            log_pass(f"round finished (cph={game.get('cards_per_hand')})")
        return cur_states

    # Play successive rounds until finished (or cap)
    cur = states
    saw_final_round = False
    saw_final_elim = False
    for i in range(30):
        game = cur[users[0]["id"]].get("game") or {}
        if game.get("phase") == "finished":
            break
        if game.get("is_final_round"):
            saw_final_round = True
            # verify hidden own card
            for u in users:
                if u["id"] not in game.get("active_players", []): continue
                st = cur[u["id"]].get("game") or {}
                own = (st.get("hands") or {}).get(u["id"], [])
                if own and not own[0].get("hidden"):
                    log_fail("final round own card hidden", str(own))
                    break
            else:
                log_pass("final round: own card hidden")
        if game.get("in_final_elim_phase"):
            saw_final_elim = True
        cur = await full_round(cur)
        game = cur[users[0]["id"]].get("game") or {}
        if game.get("phase") == "finished":
            break
        # advance next round
        await wss[users[0]["id"]].send(json.dumps({"type": "next_round"}))
        cur = await drain_all(wss, timeout=1.5)

    game = cur[users[0]["id"]].get("game") or {}
    if game.get("phase") == "finished" and game.get("winner"):
        log_pass(f"game finished, winner={game['winner']}")
    else:
        log_fail("game finished", f"phase={game.get('phase')} winner={game.get('winner')}")
    if saw_final_round:
        log_pass("saw is_final_round with hidden own card")
    if saw_final_elim:
        log_pass("saw in_final_elim_phase")

    # Verify stats updated for at least one player
    await asyncio.sleep(0.5)
    r = requests.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {users[0]['token']}"}, timeout=10)
    if r.status_code == 200:
        gp = r.json().get("stats", {}).get("games_played", 0)
        if gp >= 1:
            log_pass(f"user stats.games_played={gp}")
        else:
            log_fail("stats.games_played updated", f"gp={gp}")

    for ws in wss.values():
        try: await ws.close()
        except: pass


async def main():
    data = test_http()
    if not data:
        return
    await run_game(data)


if __name__ == "__main__":
    asyncio.run(main())
    print(f"\n===\nPASSED: {len(results['passed'])}\nFAILED: {len(results['failed'])}")
    for f in results["failed"]:
        print(f"  - {f}")
