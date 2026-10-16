"""Standalone M3 four-player opening + no-claims turn-loop DEMONSTRATION.

NOT a playable four-human room or three-AI game; the response window is
explicitly skipped. Use this script only for data/rule skeleton verification.

    python examples/four_player_opening_demo.py --seed 42 --turns 8
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mahtrain_core import FourPlayerOpening, format_hand  # noqa: E402

DIRECTIONS={"clockwise":"顺时针","counterclockwise":"逆时针","opposite":"对家"}
SUIT_LABELS={"m":"万","s":"条","p":"筒"}


def choose_exchange(hand: list[str]) -> list[str]:
    return next(
        [tile for tile in hand if tile.startswith(suit)][:3]
        for suit in "msp"
        if len([tile for tile in hand if tile.startswith(suit)]) >= 3
    )


def main() -> None:
    parser=argparse.ArgumentParser(description="四人血战开局状态机演示（非完整对战）")
    parser.add_argument("--seed",type=int,default=42)
    parser.add_argument("--turns",type=int,default=8)
    args=parser.parse_args()
    if not 1 <= args.turns <= 50:
        parser.error("--turns must be between 1 and 50")
    game=FourPlayerOpening(args.seed)
    print(f"【M3演示】庄家座位：{game.dealer}；换牌方向："
          f"{DIRECTIONS[game.exchange_direction]}；剩余牌墙：55张")
    print("【已发牌】庄14张，闲家13张，先看牌再各自密封换三张。")
    for seat in range(4):
        hand=game.private_view(seat)["hand"]
        print(f"  {seat}号座位（仅可信演示代码可查看）：{format_hand(hand)}")
        game.select_exchange(seat,choose_exchange(hand))
    print("【换三张完成】四家选牌统一交换，未发生额外摸牌。")
    for seat in range(4):
        hand=game.private_view(seat)["hand"]
        choice=min("msp",key=lambda s:(sum(t.startswith(s) for t in hand),"msp".index(s)))
        if game.private_view(seat)["tianque"]:
            print(f"  {seat}号换牌后符合天缺条件。")
        game.select_missing(seat,choice)
    print("【同时定缺完成】",", ".join(
        f"{i}号缺{SUIT_LABELS[game.missing_suits[i]]}" for i in range(4)
    ))
    for index in range(args.turns):
        if game.phase=="await_draw":
            game.draw(game.turn)
        if game.phase not in ("dealer_discard","await_discard"):
            break
        seat=game.turn
        cut=game.private_view(seat)["hand"][0]
        game.discard(seat,cut)
        print(f"  第{index+1}次切牌：座位{seat}切{cut}；"
              f"弃后牌墙余{game.public_state()['wall_count']}张")
        # EXPLICITLY not a real response resolution: no peng/gang/ron here.
        game.pass_all_claims_demo()
    game.debug_tile_counts()
    print("【守恒检查】108张牌始终完整。")
    print("【限制】本演示跳过碰/杠/胡响应，不提供AI、计番、血战结算。")


if __name__=="__main__":
    main()
