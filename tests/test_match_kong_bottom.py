"""M3.51: paid kong is part of round scores; authentic last wall tile +1 fan."""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from mahtrain_core.four_player import FourPlayerOpening
from mahtrain_core.rules import score_win
from mahtrain_core.match_archive import MatchArchive

PLAIN = ["m1", "m2", "m3", "m4", "m5", "m6", "m7", "m8", "m9",
         "p2", "p3", "p4", "p5", "p5"]


class OfficialKongAndBottomTests(unittest.TestCase):
    def test_bottom_events_add_exactly_one_fan_before_cap(self):
        normal = score_win(PLAIN, missing_suit="s", cap=6)
        sea = score_win(PLAIN, missing_suit="s", cap=6,
                        context={"sea_bottom_draw": True})
        river = score_win(PLAIN, missing_suit="s", cap=6,
                          context={"river_bottom_ron": True})
        self.assertEqual(sea["raw_fan"], normal["raw_fan"] + 1)
        self.assertEqual(river["raw_fan"], normal["raw_fan"] + 1)
        self.assertEqual(sea["bonuses"]["sea_bottom_draw"], 1)
        self.assertEqual(river["bonuses"]["river_bottom_ron"], 1)
        self.assertEqual(sea["multiplier"], 2 * normal["multiplier"])
        self.assertEqual(river["multiplier"], 2 * normal["multiplier"])
        with self.assertRaises(ValueError):
            score_win(PLAIN, missing_suit="s", cap=6, context={
                "sea_bottom_draw": True, "river_bottom_ron": True})

    def test_only_the_actual_final_draw_marks_the_last_discard(self):
        game = FourPlayerOpening(17, kong_base=100)
        seat = (game.dealer + 1) % 4  # valid nondealer 13-tile hand
        before = len(game._wall)
        # Preserve the 108 physical tiles; move mock earlier wall tiles to
        # the discard river so that the final legal draw can be exercised.
        prior = game._wall[:-1]
        game._wall = game._wall[-1:]
        game._discards.extend({"seat": 0, "tile": tile, "index": n + 1}
                              for n, tile in enumerate(prior))
        game.phase, game.turn = "await_draw", seat
        tile = game.draw(seat)
        self.assertEqual(before - 1, len(prior))
        self.assertEqual(game.public_state()["wall_count"], 0)
        self.assertTrue(game._last_wall_draw[seat])
        game.discard(seat, tile, from_draw=True)
        self.assertTrue(game.public_state()["pending_discard"]["last_wall_discard"])
        self.assertFalse(game._last_wall_draw[seat])
        self.assertFalse(any(game._last_wall_draw))

    def test_kong_paid_live_and_reversed_without_double_count(self):
        game = FourPlayerOpening(42, room_coefficient=100, kong_base=100)
        game._pending_kong_price(0, "an_gang")
        state = game.public_state()
        self.assertEqual(state["kong_ledger"]["balances"], [600, -200, -200, -200])
        self.assertEqual(state["settled_balances"], [600, -200, -200, -200])
        self.assertEqual(state["combined_balances"], state["settled_balances"])
        self.assertTrue(state["kong_included"])
        game.kong_ledger.void(1, reason="kong_discard_ron")
        self.assertEqual(game.public_state()["settled_balances"], [0, 0, 0, 0])
        self.assertEqual(len(game.kong_ledger.public_state()["entries"]), 6)

    def test_new_archives_include_kong_but_old_trials_do_not(self):
        with tempfile.TemporaryDirectory() as temp:
            archive = MatchArchive(Path(temp) / "matches.sqlite3")
            game = FourPlayerOpening(42, kong_base=100)
            opening = game.public_state()
            game._pending_kong_price(0, "an_gang")
            game.phase = "finished"
            official = archive.save_completed(
                game.public_state(), [], opening, ["challenge"] * 3)
            record = archive.detail(official)["report"]
            self.assertTrue(record["kong_included"])
            self.assertEqual(record["settled_balances"], [600, -200, -200, -200])
            self.assertEqual(record["kong_balances"], [600, -200, -200, -200])
            old = {**game.public_state(), "kong_included": False}
            archive.save_completed(old, [], opening, ["challenge"] * 3)
            board = archive.four_seat_scorecard()
            self.assertEqual(board["valid_games"], 2)
            self.assertEqual(board["kong_included_games"], 1)
            self.assertEqual(board["seats"][0]["kong_total"], 600)
            self.assertEqual(board["seats"][0]["settled_total"], 600)
            self.assertEqual(sorted(x["score"] for x in board["trend"]), [0, 600])


if __name__ == "__main__":
    unittest.main()
