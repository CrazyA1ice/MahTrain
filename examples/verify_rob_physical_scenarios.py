"""M4.01 physically complete constructed Hu stress. NOT shuffled prevalence."""
from __future__ import annotations
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from mahtrain_core.ai_rob_physical_scenarios import stress_report

if __name__=="__main__":
    output=stress_report()
    assert output["calibrated_rob_probability"] is None
    for case in output["constructed_cases"]:
        print("M4.01 PHYSICAL VERIFIED",json.dumps(case,ensure_ascii=False))
    if len(sys.argv)>1:
        target=Path(sys.argv[1])
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(json.dumps(output,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        print("Written constructed stress audit:",target)
