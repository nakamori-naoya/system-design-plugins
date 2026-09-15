#!/usr/bin/env python3
"""依頼、参照資料、grillの決定と未決を根拠状態付きで束ねる。"""
import argparse, json
from pathlib import Path

p=argparse.ArgumentParser()
p.add_argument("--input", required=True)
p.add_argument("--output", required=True)
a=p.parse_args()
source=json.loads(Path(a.input).read_text(encoding="utf-8"))
allowed={"request","referenced_artifacts","grill","provider_resolution"}
if set(source)-allowed or not isinstance(source.get("request"), str):
    raise SystemExit("[error] ground入力schemaが不正")
grill=source.get("grill")
if not isinstance(grill, dict) or grill.get("status")!="completed":
    raise SystemExit("[error] grillが完了していない")
decisions=grill.get("decisions")
opened=grill.get("open_questions")
if not isinstance(decisions, list) or not isinstance(opened, list):
    raise SystemExit("[error] decisions/open_questionsが不正")
for item in decisions:
    if set(item)!={"id","question","answer","rationale"}:
        raise SystemExit("[error] decision schemaが不正")
for item in opened:
    if set(item)!={"id","question","state","reason"} or item["state"] not in {"open","withdrawn"}:
        raise SystemExit("[error] open question schemaが不正")
out={
  "schema_version":1,
  "status":"unresolved" if any(x["state"]=="open" for x in opened) else "grounded",
  "request":{"value":source["request"],"state":"provided"},
  "referenced_artifacts":source.get("referenced_artifacts",[]),
  "decisions":[dict(x, evidence_state="agreed") for x in decisions],
  "open_questions":[dict(x, evidence_state="unresolved") for x in opened],
}
if "provider_resolution" in source:
    out["provider_resolution"]=source["provider_resolution"]
Path(a.output).write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

