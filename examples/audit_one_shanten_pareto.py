"""M4.19: measure public-proxy Pareto dominance in unchanged full real games."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from mahtrain_core.ai_one_shanten_pareto_audit import PROTOCOL,cohort,study

BLOCKS={
    "historical-development":56000,
    "historical-holdout":57000,
    "fresh-development":58000,
    "fresh-holdout":59000,
}

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--block",choices=(*BLOCKS,"all"),default="all")
    p.add_argument("--seeds",type=int,default=4)
    p.add_argument("--output",type=Path)
    args=p.parse_args()
    if args.block=="all":
        if args.seeds!=4:
            raise ValueError("all-block protocol is frozen to four seeds/block")
        result=study()
    else:
        start=BLOCKS[args.block]
        result={
            "protocol":PROTOCOL,"observational_only":True,
            "block":args.block,"seed_start":start,
            "online_ai_modified":False,"result":cohort(start,args.seeds),
        }
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(
            json.dumps(result,ensure_ascii=False,indent=2)+"\n",
            encoding="utf8")
    names=BLOCKS if args.block=="all" else (args.block,)
    for name in names:
        r=(result[name.replace("-","_")] if args.block=="all"
           else result["result"])
        print("M4.19 PUBLIC ONE-SHANTEN PARETO OBSERVATION",json.dumps({
            "block":name,"independent_shuffles":r["independent_shuffle_seeds"],
            "complete_games":r["audited_real_games"],
            "original_discards":r["baseline_total_cuts"],
            "multiple_one_shanten":r[
                "baseline_one_shanten_multiple_cut_windows"],
            "selected_dominated":r["selected_dominated_windows"],
            "selected_nondominated":r["selected_nondominated_windows"],
            "fraction_dominated":r["dominated_window_fraction"],
            "mean_frontier_options":r["mean_frontier_options_per_window"],
            "comparisons":r["other_public_proxy_comparisons"],
            "largest_dominator_margins":r[
                "largest_observed_dominator_margins"],
            "per_seed":r["per_seed"],
        },ensure_ascii=False))
