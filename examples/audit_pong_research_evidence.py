r"""M4.51 local SAFE-report audit; zero additional paid Mahjong simulations.

At MahTrain root on Windows:
 python examples\audit_pong_research_evidence.py

Override any file with --m447/--m448/--m449/--m450 and use --out to set
the destination. Only aggregated SAFE JSON is read or written.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))

from mahtrain_core.ai_pong_evidence_gate import (
    audit_safe_reports,load_safe_json,
)
from mahtrain_core.ai_shadow_headtohead import _write_atomic


def main()->None:
    p=argparse.ArgumentParser(
        description="M4.51 audit four authentic M4.47..M4.50 aggregate-only studies; no candidate policy is promoted",
    )
    p.add_argument(
        "--m447",type=Path,
        default=Path("data/selfplay/m447-pong-pass-8/safe_pong_pass_branch_rollouts.json"),
    )
    p.add_argument(
        "--m448",type=Path,
        default=Path("data/selfplay/m448-pong-pass-24/safe_pong_pass_replication.json"),
    )
    p.add_argument(
        "--m449",type=Path,
        default=Path("data/selfplay/m449-pong-strata-24/safe_pong_actor_strata.json"),
    )
    p.add_argument(
        "--m450",type=Path,
        default=Path("data/selfplay/m450-phase-48/safe_pong_phase_confirmation.json"),
    )
    p.add_argument(
        "--out",type=Path,
        default=Path("data/selfplay/m451-pong-audit/safe_pong_evidence_gate.json"),
    )
    args=p.parse_args()
    report=audit_safe_reports({
        label:load_safe_json(getattr(args,label))
        for label in ("m447","m448","m449","m450")
    })
    output=args.out.resolve()
    sources=[getattr(args,label).resolve()
             for label in ("m447","m448","m449","m450")]
    if output in sources or any(source==output.parent for source in sources):
        raise ValueError("M4.51 must not overwrite a source SAFE study report")
    _write_atomic(output,report)
    print(json.dumps({
        "protocol":report["protocol"],
        "study_means":[v["conditional_peng_minus_pass_mean_points"] for v
                       in report["studies_in_natural_chronological_order"].values()],
        "reversals":report["mean_effect_sign_reversals_between_consecutive_studies"],
        "phase_claim_independently_supported":report["m450_predeclared_direction_supported"],
        "decision":report["recommendation"],
        "out":str(output),
    },ensure_ascii=False,allow_nan=False))


if __name__=="__main__":
    main()
