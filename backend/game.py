"""Bisca game engine (pure logic, no I/O)."""
import random
from typing import List, Dict, Optional
import uuid

SUITS = ["denari", "coppe", "spade", "bastoni"]
SUIT_RANK = {"denari": 4, "coppe": 3, "spade": 2, "bastoni": 1}
# Values: 1 asso .. 7 sette, 8 fante, 9 cavallo, 10 re
VALUES = list(range(1, 11))
VALUE_LABEL = {1: "A", 2: "2", 3: "3", 4: "4", 5: "5", 6: "6", 7: "7", 8: "F", 9: "C", 10: "R"}


def make_deck() -> List[dict]:
    deck = []
    for s in SUITS:
        for v in VALUES:
            deck.append({"suit": s, "value": v, "id": f"{s}-{v}"})
    return deck


def card_rank(card: dict, re_denari_as_zero: bool = False) -> int:
    """Higher = stronger. Re di Denari can be played as '0 di denari' → rank between Asso Denari and Re Coppe."""
    if card["suit"] == "denari" and card["value"] == 10 and re_denari_as_zero:
        return 400  # between Re Coppe (310) and Asso Denari (401)
    return SUIT_RANK[card["suit"]] * 100 + card["value"]


def max_cards_for(n_players: int) -> int:
    return min(8, 40 // n_players)  # cap: 8 rounds max even with 3 players for gameplay length; adjust as desired
    # Per user example: 8 players -> 5 cards. 40//8=5 ✓
    # For 3 players 40//3=13, capping at 8 keeps rounds reasonable but user says "primo turno max possibile"
    # We'll uncap to follow rules exactly.


def max_cards_strict(n_players: int) -> int:
    return 40 // n_players


class BiscaGame:
    """Manages a single game session with rounds and iterative final elimination."""

    def __init__(self, player_ids: List[str], dealer_index: int = 0):
        self.player_ids = list(player_ids)  # seating order (clockwise)
        self.eliminated: List[str] = []
        self.scores: Dict[str, int] = {p: 0 for p in player_ids}
        self.dealer_index = dealer_index  # index in current active list
        self.round_number = 0
        self.phase = "starting"  # starting|bidding|playing|trick_reveal|round_end|final_elim|finished|re_denari_choice
        # round state
        self.cards_per_hand = 0
        self.hands: Dict[str, List[dict]] = {}
        self.bids: Dict[str, Optional[int]] = {}
        self.bid_order: List[str] = []
        self.current_bidder_idx = 0
        self.tricks_won: Dict[str, int] = {}
        self.current_trick: List[dict] = []  # [{player_id, card, effective_rank}]
        self.trick_leader_id: Optional[str] = None
        self.current_player_id: Optional[str] = None
        self.is_final_round = False  # 1-card round with hidden own card
        self.pending_re_denari: Optional[dict] = None
        self.last_trick_winner: Optional[str] = None
        self.winner: Optional[str] = None
        self.log: List[str] = []
        # elimination iteration mode
        self.in_final_elim_phase = False

    def active_players(self) -> List[str]:
        return [p for p in self.player_ids if p not in self.eliminated]

    def start_round(self):
        actives = self.active_players()
        n = len(actives)
        if n <= 1:
            self.phase = "finished"
            self.winner = actives[0] if actives else None
            return

        # After main game finished, iterative 1-card elimination
        if self.in_final_elim_phase:
            self.cards_per_hand = 1
            self.is_final_round = True
        else:
            self.round_number += 1
            if self.round_number == 1:
                self.cards_per_hand = max_cards_strict(n)
            else:
                self.cards_per_hand = max(1, self.cards_per_hand - 1)
            self.is_final_round = (self.cards_per_hand == 1)

        # Deal
        deck = make_deck()
        random.shuffle(deck)
        self.hands = {}
        for p in actives:
            self.hands[p] = [deck.pop() for _ in range(self.cards_per_hand)]
        # Remaining deck is discarded (unknown)

        # Bidding order: start from player after dealer, dealer last
        self.dealer_index = self.dealer_index % n
        dealer_id = actives[self.dealer_index]
        order = []
        for i in range(1, n + 1):
            idx = (self.dealer_index + i) % n
            order.append(actives[idx])
        self.bid_order = order  # dealer is last
        self.bids = {p: None for p in actives}
        self.current_bidder_idx = 0
        self.tricks_won = {p: 0 for p in actives}
        self.current_trick = []
        # first trick leader = player after dealer
        self.trick_leader_id = actives[(self.dealer_index + 1) % n]
        self.current_player_id = self.trick_leader_id
        self.pending_re_denari = None
        self.phase = "bidding"
        self.log.append(f"Turno {self.round_number}: {self.cards_per_hand} carte a testa.")

    def can_dealer_bid(self, value: int) -> bool:
        """Dealer cannot pick a bid that makes sum(all bids) == cards_per_hand."""
        other_sum = sum(v for v in self.bids.values() if v is not None)
        return (other_sum + value) != self.cards_per_hand

    def place_bid(self, player_id: str, bid: int) -> Optional[str]:
        if self.phase != "bidding":
            return "Non è la fase di dichiarazione."
        expected = self.bid_order[self.current_bidder_idx]
        if player_id != expected:
            return "Non è il tuo turno di dichiarare."
        if bid < 0 or bid > self.cards_per_hand:
            return f"Devi dichiarare tra 0 e {self.cards_per_hand}."
        # dealer constraint (dealer is last)
        if self.current_bidder_idx == len(self.bid_order) - 1:
            if not self.can_dealer_bid(bid):
                return "Il mazziere non può dichiarare un numero che rende la somma uguale alle carte in mano."
        self.bids[player_id] = bid
        self.current_bidder_idx += 1
        if self.current_bidder_idx >= len(self.bid_order):
            self.phase = "playing"
            self.log.append("Dichiarazioni completate. Inizia il gioco.")
        return None

    def _effective_rank_for_played(self, card: dict, re_denari_as_zero: bool) -> int:
        return card_rank(card, re_denari_as_zero)

    def play_card(self, player_id: str, card_id: str, re_denari_as_zero: Optional[bool] = None) -> Optional[str]:
        if self.phase not in ("playing",):
            return "Non è la fase di gioco."
        if player_id != self.current_player_id:
            return "Non è il tuo turno."
        hand = self.hands.get(player_id, [])
        card = next((c for c in hand if c["id"] == card_id), None)
        if not card:
            return "Carta non nella tua mano."

        # In final 1-card round: player doesn't know own card. That's fine—they still "play" it. The card_id is preselected (their only card).
        # Re di denari special
        is_re_denari = (card["suit"] == "denari" and card["value"] == 10)
        if is_re_denari and re_denari_as_zero is None:
            # need choice
            self.pending_re_denari = {"player_id": player_id, "card": card}
            self.phase = "re_denari_choice"
            return None

        rank_used = self._effective_rank_for_played(card, bool(re_denari_as_zero))
        # remove from hand
        self.hands[player_id] = [c for c in hand if c["id"] != card_id]
        self.current_trick.append({
            "player_id": player_id,
            "card": card,
            "effective_rank": rank_used,
            "re_denari_as_zero": bool(re_denari_as_zero) if is_re_denari else False,
        })
        self.pending_re_denari = None
        self.phase = "playing"
        # advance
        actives = self.active_players()
        cur_idx = actives.index(player_id)
        next_idx = (cur_idx + 1) % len(actives)
        # check trick complete: when trick has len == active_players
        if len(self.current_trick) == len(actives):
            # resolve
            winner_play = max(self.current_trick, key=lambda x: x["effective_rank"])
            self.tricks_won[winner_play["player_id"]] += 1
            self.last_trick_winner = winner_play["player_id"]
            self.log.append(f"Presa vinta da {winner_play['player_id']}")
            self.phase = "trick_reveal"
            self.trick_leader_id = winner_play["player_id"]
            self.current_player_id = None
        else:
            self.current_player_id = actives[next_idx]
        return None

    def resolve_re_denari(self, player_id: str, as_zero: bool) -> Optional[str]:
        if self.phase != "re_denari_choice" or not self.pending_re_denari:
            return "Nessuna scelta Re di Denari pendente."
        if self.pending_re_denari["player_id"] != player_id:
            return "Non è la tua scelta."
        card = self.pending_re_denari["card"]
        # Now play it for real
        return self.play_card(player_id, card["id"], re_denari_as_zero=as_zero)

    def continue_after_trick(self) -> Optional[str]:
        """Called by server to progress after trick reveal."""
        if self.phase != "trick_reveal":
            return "Non c'è una presa da risolvere."
        self.current_trick = []
        # if hands empty -> end of round
        actives = self.active_players()
        if all(len(self.hands[p]) == 0 for p in actives):
            self._end_round()
        else:
            self.current_player_id = self.last_trick_winner
            self.phase = "playing"
        return None

    def _end_round(self):
        actives = self.active_players()
        # score sballi
        for p in actives:
            diff = abs((self.bids[p] or 0) - self.tricks_won[p])
            self.scores[p] += diff
        self.log.append(f"Fine turno. Punteggi aggiornati.")
        if self.in_final_elim_phase:
            # Eliminate ALL players with highest score
            max_score = max(self.scores[p] for p in actives)
            to_eliminate = [p for p in actives if self.scores[p] == max_score]
            # Only eliminate if not all tied — need to still leave someone
            if len(to_eliminate) < len(actives):
                for p in to_eliminate:
                    self.eliminated.append(p)
                self.log.append(f"Eliminati {len(to_eliminate)} giocatori.")
            else:
                # everyone tied — replay
                self.log.append("Tutti in parità. Si ripete il round da 1 carta.")
            # check winner
            remaining = self.active_players()
            if len(remaining) <= 1:
                self.phase = "finished"
                self.winner = remaining[0] if remaining else None
                return
            # rotate dealer within remaining
            self.dealer_index = (self.dealer_index + 1) % len(remaining)
            self.phase = "round_end"
        else:
            # Move to next round: cards_per_hand - 1
            if self.cards_per_hand == 1:
                # last regular round: check if final elim phase should start
                # But per rules: first round with 1 card is played once, then eliminate top score → then iterate 1-card rounds
                # After this 1-card round, eliminate top score(s) then continue 1-card rounds
                max_score = max(self.scores[p] for p in actives)
                to_eliminate = [p for p in actives if self.scores[p] == max_score]
                if len(to_eliminate) < len(actives):
                    for p in to_eliminate:
                        self.eliminated.append(p)
                self.in_final_elim_phase = True
                remaining = self.active_players()
                if len(remaining) <= 1:
                    self.phase = "finished"
                    self.winner = remaining[0] if remaining else None
                    return
                self.dealer_index = (self.dealer_index + 1) % len(remaining)
                self.phase = "round_end"
            else:
                # dealer rotates
                self.dealer_index = (self.dealer_index + 1) % len(actives)
                self.phase = "round_end"

    def public_state(self, viewer_id: Optional[str] = None) -> dict:
        """Serialize game state visible to a specific viewer."""
        actives = self.active_players()
        hands_view = {}
        for p in actives:
            if self.is_final_round:
                # In final round: viewer sees everyone else's card face-up, but NOT their own
                if p == viewer_id:
                    hands_view[p] = [{"hidden": True, "id": c["id"]} for c in self.hands.get(p, [])]
                else:
                    hands_view[p] = self.hands.get(p, [])
            else:
                if p == viewer_id:
                    hands_view[p] = self.hands.get(p, [])
                else:
                    hands_view[p] = [{"hidden": True} for _ in self.hands.get(p, [])]
        dealer_id = actives[self.dealer_index % len(actives)] if actives else None
        return {
            "phase": self.phase,
            "round_number": self.round_number,
            "cards_per_hand": self.cards_per_hand,
            "is_final_round": self.is_final_round,
            "in_final_elim_phase": self.in_final_elim_phase,
            "dealer_id": dealer_id,
            "player_order": self.player_ids,
            "active_players": actives,
            "eliminated": self.eliminated,
            "scores": self.scores,
            "hands": hands_view,
            "hand_counts": {p: len(self.hands.get(p, [])) for p in actives},
            "bids": self.bids,
            "bid_order": self.bid_order,
            "current_bidder": self.bid_order[self.current_bidder_idx] if self.phase == "bidding" and self.current_bidder_idx < len(self.bid_order) else None,
            "tricks_won": self.tricks_won,
            "current_trick": self.current_trick,
            "current_player": self.current_player_id,
            "pending_re_denari": self.pending_re_denari,
            "winner": self.winner,
            "log": self.log[-10:],
        }
