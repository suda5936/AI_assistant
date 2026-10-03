#!/usr/bin/env python3
"""하네스 측정 리포트.

입력
- .harness/logs/events.jsonl : 훅 실행 기록 (check_edit, guard_*, quality_gate)
- workplace/<프로젝트>/docs/reviews, docs/qa : 리뷰·QA 판정 문서

출력 (마크다운)
- 훅별 통과/실패/차단 횟수, 수정 시 자동 검사가 잡아낸 비율
- 역할별로 피드백·차단을 받은 횟수
- 자주 위반된 규칙
- 프로젝트별 리뷰·QA 반려율

사용법: python3 scripts/harness_report.py [--project 이름] [--out 파일]
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG = ROOT / ".harness" / "logs" / "events.jsonl"
RULE_CODE = re.compile(r"\b([A-Z]{1,4}\d{3,4})\b")


def load_events() -> list[dict]:
    if not LOG.exists():
        return []
    rows = []
    for line in LOG.read_text(encoding="utf-8").splitlines():
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def rule_key(detail: str) -> str:
    match = RULE_CODE.search(detail)
    if match:
        return match.group(1)
    text = re.sub(r"^\S+:\d+(:\d+)?:?\s*", "", detail)
    return text.split(".")[0][:40]


def verdicts(project: Path) -> dict[str, Counter]:
    result: dict[str, Counter] = {}
    for kind in ("reviews", "qa"):
        counter: Counter = Counter()
        for doc in sorted((project / "docs" / kind).glob("*.md")):
            first = doc.read_text(encoding="utf-8").splitlines()[:1]
            if first and "반려" in first[0]:
                counter["반려"] += 1
            elif first and "통과" in first[0]:
                counter["통과"] += 1
        result[kind] = counter
    return result


def in_project(event: dict, name: str | None) -> bool:
    if not name:
        return True
    target = f"workplace/{name}/"
    text = json.dumps(event, ensure_ascii=False)
    return target in text or name in event.get("projects", [])


def build(project_name: str | None) -> str:
    events = [e for e in load_events() if in_project(e, project_name)]
    out = [f"# 하네스 리포트{f' — {project_name}' if project_name else ''}", ""]
    if not events:
        out.append("기록된 훅 이벤트가 없습니다.")
        return "\n".join(out)

    by_hook: dict[str, Counter] = defaultdict(Counter)
    by_role: dict[str, Counter] = defaultdict(Counter)
    rules: Counter = Counter()
    for e in events:
        by_hook[e["hook"]][e["status"]] += 1
        if e["status"] in ("fail", "block"):
            by_role[e.get("role", "main")][e["hook"]] += 1
        if e["hook"] == "check_edit" and e["status"] == "fail":
            rules.update(rule_key(d) for d in e.get("details", []))

    out += ["## 훅 실행 결과", "", "| 훅 | 통과 | 실패 | 차단 | 포기 |", "|---|---|---|---|---|"]
    for hook, c in sorted(by_hook.items()):
        out.append(f"| {hook} | {c['pass']} | {c['fail']} | {c['block']} | {c['gave_up']} |")

    edits = by_hook.get("check_edit", Counter())
    total = edits["pass"] + edits["fail"]
    if total:
        rate = edits["fail"] / total
        caught = f"**{edits['fail']}회({rate:.0%})**"
        out += ["", f"- 파일 수정 {total}회 중 {caught}를 자동 검사가 잡아 되돌려 보냈다."]
    gate = by_hook.get("quality_gate", Counter())
    if gate["fail"]:
        out.append(f"- 품질 게이트가 '끝났다'는 선언을 **{gate['fail']}회** 거부했다.")
    blocks = sum(by_hook[h]["block"] for h in ("guard_write", "guard_bash"))
    if blocks:
        out.append(f"- 역할을 벗어난 쓰기·명령을 **{blocks}회** 차단했다.")

    if by_role:
        out += ["", "## 역할별 피드백·차단", "", "| 역할 | 훅 | 횟수 |", "|---|---|---|"]
        for role, c in sorted(by_role.items()):
            for hook, n in c.most_common():
                out.append(f"| {role} | {hook} | {n} |")

    if rules:
        out += ["", "## 자주 위반된 규칙", "", "| 규칙 | 횟수 |", "|---|---|"]
        out += [f"| {rule} | {n} |" for rule, n in rules.most_common(10)]

    projects = (
        [ROOT / "workplace" / project_name]
        if project_name
        else sorted(p for p in (ROOT / "workplace").glob("*") if (p / "docs").is_dir())
    )
    rows = []
    for project in projects:
        v = verdicts(project)
        if sum(v["reviews"].values()) + sum(v["qa"].values()):
            r, q = v["reviews"], v["qa"]
            rows.append(
                f"| {project.name} | {r['통과']} | {r['반려']} | {q['통과']} | {q['반려']} |"
            )
    if rows:
        out += ["", "## 리뷰·QA 판정", ""]
        out += ["| 프로젝트 | 리뷰 통과 | 리뷰 반려 | QA 통과 | QA 반려 |", "|---|---|---|---|---|"]
        out += rows
    return "\n".join(out) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", help="workplace 아래 프로젝트 이름")
    parser.add_argument("--out", help="결과를 저장할 파일 경로")
    args = parser.parse_args()
    report = build(args.project)
    if args.out:
        Path(args.out).write_text(report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
