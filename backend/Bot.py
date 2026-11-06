"""Bot per Bisca: giocatori automatici a regole.

I bot NON barano: usano solo le informazioni che vedrebbe un giocatore umano
(la propria mano; nel round finale da 1 carta vedono le carte degli altri ma non la propria).
"""
import logging
from typing import List, Optional, Tuple

from game import BiscaGame, make_deck, card_rank

logger = logging.getLogger("bisca.bot")

BOT_PREFIX = "bot-"
BOT_NAMES = ["Ugo", "1ns3tt0C4mməll0", "rwuca", "Sara", "Sarco", "Trafalga", "Luciano", "Rita"]

_DECK = make_deck()


def is_bot(user_id: str) -> bool:
    return str(user_id).startswith(BOT_PREFIX)


def _beat_prob(rank: int, unseen_ranks: List[int]) -> float:
    """Probabilità che una carta sconosciuta a caso sia più debole di `rank`."""
    if not unseen_ranks:
        return 1.0
    return sum(1 for r in unseen_ranks if r < rank) / len(unseen_ranks)


# ---------- Dichiarazione ----------
def _nearest_legal_bid(game: BiscaGame, target: int) -> int:
    k = game.cards_per_hand
    is_dealer = game.current_bidder_idx == len(game.bid_order) - 1
    for b in sorted(range(k + 1), key=lambda b: (abs(b - target), b)):
        if not is_dealer or game.can_dealer_bid(b):
            return b
    return 0


def choose_bid(game: BiscaGame, bot_id: str) -> int:
    n = len(game.active_players())
    if game.is_final_round:
        # round da 1 carta: vedo le carte degli altri, non la mia
        visible = [c for p, h in game.hands.items() if p != bot_id for c in h]
        vis_ids = {c["id"] for c in visible}
        unseen = [card_rank(c) for c in _DECK if c["id"] not in vis_ids]
        best_other = max((card_rank(c) for c in visible), default=0)
        p_win = sum(1 for r in unseen if r > best_other) / len(unseen)
        target = 1 if p_win >= 0.5 else 0
    else:
        hand = game.hands[bot_id]
        hand_ids = {c["id"] for c in hand}
        unseen = [card_rank(c) for c in _DECK if c["id"] not in hand_ids]
        # prese attese: ogni carta vince se batte le n-1 carte avversarie
        expected = sum(_beat_prob(card_rank(c), unseen) ** (n - 1) for c in hand)
        target = round(expected)
    return _nearest_legal_bid(game, target)


# ---------- Gioco della carta ----------
def _variants(card: dict) -> List[Tuple[str, Optional[bool], int]]:
    """Modi di giocare una carta: (card_id, re_denari_as_zero, rank effettivo)."""
    if card["suit"] == "denari" and card["value"] == 10:
        return [
            (card["id"], False, card_rank(card, False)),
            (card["id"], True, card_rank(card, True)),
        ]
    return [(card["id"], None, card_rank(card))]


def choose_play(game: BiscaGame, bot_id: str) -> Tuple[str, Optional[bool], int]:
    hand = game.hands[bot_id]
    n = len(game.active_players())
    trick = game.current_trick
    need = (game.bids[bot_id] or 0) - game.tricks_won[bot_id]  # prese ancora da fare
    remaining = len(hand)  # prese ancora da giocare (questa inclusa)
    options = [v for c in hand for v in _variants(c)]

    cur_max = max((t["effective_rank"] for t in trick), default=0)
    left_after = n - len(trick) - 1  # giocatori che giocano dopo di me
    seen = {c["id"] for c in hand} | {t["card"]["id"] for t in trick}
    unseen = [card_rank(c) for c in _DECK if c["id"] not in seen]

    def win_prob(rank: int) -> float:
        if rank < cur_max:
            return 0.0
        if left_after == 0:
            return 1.0
        return _beat_prob(rank, unseen) ** left_after

    if need > 0:
        if need >= remaining:  # devo vincere tutte le prese rimaste
            return max(options, key=lambda o: o[2])
        likely = [o for o in options if win_prob(o[2]) >= 0.5]
        if likely:
            return min(likely, key=lambda o: o[2])  # la carta più bassa che vince
        return min(options, key=lambda o: o[2])  # presa persa: tengo le carte forti

    # ho già le prese dichiarate: evito di vincerne altre
    safe = [o for o in options if win_prob(o[2]) <= 0.3]
    if safe:
        return max(safe, key=lambda o: o[2])  # mi scarico della carta più alta che perde
    return min(options, key=lambda o: o[2])


# ---------- Entry point ----------
def bot_move(game: BiscaGame) -> bool:
    """Se tocca a un bot, fa la sua mossa. Restituisce True se ha agito."""
    if game.phase == "bidding" and game.current_bidder_idx < len(game.bid_order):
        pid = game.bid_order[game.current_bidder_idx]
        if is_bot(pid):
            err = game.place_bid(pid, choose_bid(game, pid))
            if err:
                logger.warning("bot %s bid error: %s", pid, err)
            return err is None
    elif game.phase == "playing" and game.current_player_id:
        pid = game.current_player_id
        if is_bot(pid):
            card_id, as_zero, _ = choose_play(game, pid)
            err = game.play_card(pid, card_id, as_zero)
            if err:
                logger.warning("bot %s play error: %s", pid, err)
            return err is None
    return False
