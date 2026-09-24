"""Bisca backend smoke test — REST + WebSocket."""
import asyncio, json, uuid, httpx, websockets, sys

BASE = "http://localhost:8001"
WS_BASE = "ws://localhost:8001"

results = {"passed": [], "failed": []}

def ok(name, ev=""): results["passed"].append(name); print(f"PASS: {name}")
def fail(name, ev=""): results["failed"].append({"name": name, "evidence": ev}); print(f"FAIL: {name} :: {ev}")

async def recv_state(ws, timeout=5):
    """Consume messages until we get a state (or error)."""
    end = asyncio.get_event_loop().time() + timeout
    last_state = None
    while asyncio.get_event_loop().time() < end:
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=0.5)
            m = json.loads(raw)
            if m.get("type") == "state": last_state = m["state"]
            elif m.get("type") == "error": print(f"  WS error: {m}")
        except asyncio.TimeoutError:
            if last_state: return last_state
    return last_state

async def drain(ws, ms=400):
    try:
        while True:
            raw = await asyncio.wait_for(ws.recv(), timeout=ms/1000)
            m = json.loads(raw)
            if m.get("type") == "error": print(f"  drain err: {m.get('message')}")
    except asyncio.TimeoutError:
        pass

async def main():
    async with httpx.AsyncClient(base_url=BASE, timeout=15) as c:
        # 1. Register user
        u1 = f"u{uuid.uuid4().hex[:8]}"
        u2 = f"u{uuid.uuid4().hex[:8]}"
        u3 = f"u{uuid.uuid4().hex[:8]}"
        r = await c.post("/api/auth/register", json={"username": u1, "password": "pass1234"})
        if r.status_code == 200 and "token" in r.json():
            ok("register u1")
            t1 = r.json()["token"]
        else:
            fail("register u1", f"{r.status_code} {r.text}"); return

        # 2. Duplicate register -> 400
        r = await c.post("/api/auth/register", json={"username": u1, "password": "pass1234"})
        (ok if r.status_code == 400 else fail)("duplicate register 400", f"{r.status_code}")

        # 3. Login existing
        r = await c.post("/api/auth/login", json={"username": u1, "password": "pass1234"})
        (ok if r.status_code == 200 else fail)("login existing", f"{r.status_code}")

        # 4. Wrong password -> 401
        r = await c.post("/api/auth/login", json={"username": u1, "password": "WRONG"})
        (ok if r.status_code == 401 else fail)("wrong password 401", f"{r.status_code}")

        # 5. /me
        r = await c.get("/api/auth/me", headers={"Authorization": f"Bearer {t1}"})
        (ok if r.status_code == 200 and r.json().get("username") == u1 else fail)("auth/me", f"{r.status_code} {r.text[:100]}")

        # register u2, u3
        r = await c.post("/api/auth/register", json={"username": u2, "password": "pass1234"}); t2 = r.json()["token"]
        r = await c.post("/api/auth/register", json={"username": u3, "password": "pass1234"}); t3 = r.json()["token"]
        ok("register u2/u3")

        # 6. Create room
        r = await c.post("/api/rooms/create", headers={"Authorization": f"Bearer {t1}"})
        if r.status_code == 200 and len(r.json().get("code", "")) == 5:
            code = r.json()["code"]; ok(f"create room {code}")
        else:
            fail("create room", f"{r.status_code} {r.text}"); return

        # 7. Join room u2, u3
        r = await c.post(f"/api/rooms/{code}/join", headers={"Authorization": f"Bearer {t2}"})
        (ok if r.status_code == 200 else fail)("u2 join", f"{r.status_code}")
        r = await c.post(f"/api/rooms/{code}/join", headers={"Authorization": f"Bearer {t3}"})
        (ok if r.status_code == 200 else fail)("u3 join", f"{r.status_code}")

        # 8. Get room state
        r = await c.get(f"/api/rooms/{code}", headers={"Authorization": f"Bearer {t1}"})
        if r.status_code == 200 and len(r.json().get("players", [])) == 3:
            ok("GET room has 3 players")
        else:
            fail("GET room", f"{r.status_code} players={len(r.json().get('players',[]))}")

        # 9. Leaderboard
        r = await c.get("/api/leaderboard")
        (ok if r.status_code == 200 and isinstance(r.json(), list) else fail)("leaderboard", f"{r.status_code}")

    # ---- WebSocket flow ----
    ws1 = await websockets.connect(f"{WS_BASE}/api/ws/{code}?token={t1}")
    ws2 = await websockets.connect(f"{WS_BASE}/api/ws/{code}?token={t2}")
    ws3 = await websockets.connect(f"{WS_BASE}/api/ws/{code}?token={t3}")
    await asyncio.sleep(0.5)
    await drain(ws1); await drain(ws2); await drain(ws3)

    # host starts game
    await ws1.send(json.dumps({"type": "start_game"}))
    await asyncio.sleep(0.5)
    s1 = await recv_state(ws1, 3)
    if s1 and s1["game"]["phase"] == "bidding":
        ok("start_game -> bidding phase")
    else:
        fail("start_game", f"state={s1}"); 
        for w in (ws1,ws2,ws3): await w.close()
        return
    game = s1["game"]
    dealer = game["dealer_id"]
    bid_order = game["bid_order"]
    current_bidder = game["current_bidder"]
    # dealer must be last in bid_order, current_bidder = player after dealer
    if bid_order[-1] == dealer and current_bidder == bid_order[0]:
        ok("dealer bids last & current_bidder is after dealer")
    else:
        fail("bid order", f"dealer={dealer} order={bid_order} cur={current_bidder}")

    # players -> ws map
    pid_map = {}
    for tk, w in [(t1,ws1),(t2,ws2),(t3,ws3)]:
        # decode sub from token would need JWT; simpler: use rest /me
        pass
    # Get user IDs from room GET
    async with httpx.AsyncClient(base_url=BASE, timeout=10) as c:
        r = await c.get(f"/api/rooms/{code}", headers={"Authorization": f"Bearer {t1}"})
        players = r.json()["players"]
    uname_to_uid = {p["username"]: p["user_id"] for p in players}
    tok_ws = {uname_to_uid[u1]: (ws1,t1), uname_to_uid[u2]: (ws2,t2), uname_to_uid[u3]: (ws3,t3)}

    # 10. Chat test
    await ws1.send(json.dumps({"type": "chat", "text": "ciao"}))
    await asyncio.sleep(0.4)
    st = await recv_state(ws2, 2)
    if st and any(m["text"] == "ciao" for m in st.get("chat", [])):
        ok("chat broadcast")
    else:
        fail("chat", f"chat={st.get('chat') if st else None}")

    # 11. Dealer illegal bid test
    # bid 0 for first two, then dealer tries to bid such that sum == cards_per_hand
    cards = game["cards_per_hand"]
    print(f"  cards_per_hand={cards}")
    # non-dealers bid 0
    for pid in bid_order[:-1]:
        ws, _ = tok_ws[pid]
        await ws.send(json.dumps({"type": "bid", "bid": 0}))
        await asyncio.sleep(0.3)
    await drain(ws1); await drain(ws2); await drain(ws3)
    # dealer tries illegal bid = cards (sum would become cards)
    dws, _ = tok_ws[dealer]
    await dws.send(json.dumps({"type": "bid", "bid": cards}))
    # Should receive error
    got_err = False
    try:
        for _ in range(10):
            raw = await asyncio.wait_for(dws.recv(), timeout=1.0)
            m = json.loads(raw)
            if m.get("type") == "error" and "mazziere" in m.get("message","").lower():
                got_err = True; break
    except asyncio.TimeoutError: pass
    (ok if got_err else fail)("dealer illegal bid rejected", f"got_err={got_err}")

    # dealer bids a legal value (0 is legal since sum=0, needs !=cards; 0!=cards works)
    legal_bid = 0 if cards != 0 else 1
    await dws.send(json.dumps({"type": "bid", "bid": legal_bid}))
    await asyncio.sleep(0.5)
    await drain(ws1); await drain(ws2); await drain(ws3)

    # 12. Auto-play: bids 0 everywhere (already partial), play first card each turn
    # Now proceed to playing phase. Loop and play cards.
    last_state = None
    steps = 0
    finished = False
    while steps < 400:
        steps += 1
        # get freshest state from ws1
        try:
            raw = await asyncio.wait_for(ws1.recv(), timeout=1.5)
            m = json.loads(raw)
            if m.get("type") == "state":
                last_state = m["state"]
            elif m.get("type") == "error":
                pass
        except asyncio.TimeoutError:
            pass
        if not last_state: continue
        g = last_state.get("game")
        if not g: continue
        phase = g["phase"]
        if phase == "finished":
            finished = True; break
        if phase == "bidding":
            cb = g["current_bidder"]
            if cb:
                ws, _ = tok_ws[cb]
                # legal bid: if dealer, ensure sum != cards
                bid_val = 0
                if cb == g["dealer_id"]:
                    other_sum = sum(v for v in g["bids"].values() if v is not None)
                    if other_sum + 0 == g["cards_per_hand"]:
                        bid_val = 1 if g["cards_per_hand"] != 1 else 0
                await ws.send(json.dumps({"type": "bid", "bid": bid_val}))
                await asyncio.sleep(0.15)
        elif phase == "playing":
            cp = g["current_player"]
            if cp:
                ws, tk = tok_ws[cp]
                # need viewer's hand
                # request room state via REST for that user
                async with httpx.AsyncClient(base_url=BASE, timeout=10) as c:
                    rr = await c.get(f"/api/rooms/{code}", headers={"Authorization": f"Bearer {tk}"})
                gg = rr.json().get("game") or {}
                hand = gg.get("hands",{}).get(cp,[])
                # in final round, cards for viewer are hidden; still send card_id
                card = hand[0] if hand else None
                if card and card.get("id"):
                    msg = {"type": "play_card", "card_id": card["id"]}
                    await ws.send(json.dumps(msg))
                    await asyncio.sleep(0.15)
        elif phase == "re_denari_choice":
            pend = g.get("pending_re_denari") or {}
            pid = pend.get("player_id")
            if pid:
                ws, _ = tok_ws[pid]
                await ws.send(json.dumps({"type": "re_denari_choice", "as_zero": False}))
                await asyncio.sleep(0.15)
        elif phase == "trick_reveal":
            await ws1.send(json.dumps({"type": "continue_trick"}))
            await asyncio.sleep(0.15)
        elif phase == "round_end":
            await ws1.send(json.dumps({"type": "next_round"}))
            await asyncio.sleep(0.15)

    if finished and last_state["game"]["winner"]:
        ok(f"full game finished, winner={last_state['game']['winner']}")
    else:
        fail("full game finished", f"finished={finished} phase={last_state['game']['phase'] if last_state else None} steps={steps}")

    # 13. Check leaderboard winner stats
    if finished:
        await asyncio.sleep(1)
        async with httpx.AsyncClient(base_url=BASE, timeout=10) as c:
            r = await c.get("/api/leaderboard")
            lb = r.json()
        winner_uid = last_state["game"]["winner"]
        winner_username = next((u for u,uid in uname_to_uid.items() if uid==winner_uid), None)
        entry = next((u for u in lb if u["username"] == winner_username), None)
        if entry and entry["stats"]["wins"] >= 1 and entry["stats"]["games_played"] >= 1:
            ok(f"winner stats updated: {entry['stats']}")
        else:
            fail("winner stats", f"entry={entry}")

    for w in (ws1,ws2,ws3):
        try: await w.close()
        except: pass

    print("\n=== SUMMARY ===")
    print(f"Passed: {len(results['passed'])}")
    print(f"Failed: {len(results['failed'])}")
    for f in results['failed']: print(f"  - {f}")

asyncio.run(main())
