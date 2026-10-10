"""Run the evaluation questions against one or more agents and compare scores.

    python evals/run_evals.py                                   # all agents
    python evals/run_evals.py --agents base_agent graphrag_agent
    python evals/run_evals.py --only std-hashing join-lines-customers

Writes a markdown report to evals/results/. Uses real Gemini and BigQuery
calls, so it costs a little each run (a few cents with small data).
"""

from __future__ import annotations

import argparse
import asyncio
import importlib
import sys
import time
from datetime import datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "agents"))

from google.adk.runners import InMemoryRunner  # noqa: E402
from google.genai import types  # noqa: E402

DEFAULT_AGENTS = ["base_agent", "rag_agent", "graph_agent", "graphrag_agent"]


async def ask(agent, question: str) -> tuple[str, list[str]]:
    runner = InMemoryRunner(agent=agent, app_name=agent.name)
    session = await runner.session_service.create_session(app_name=agent.name, user_id="eval")
    message = types.Content(role="user", parts=[types.Part(text=question)])
    answer, tools = "", []
    async for event in runner.run_async(user_id="eval", session_id=session.id, new_message=message):
        for call in event.get_function_calls() or []:
            tools.append(call.name)
        if event.is_final_response() and event.content and event.content.parts:
            answer = "".join(p.text or "" for p in event.content.parts)
    return answer, tools


def score(q: dict, answer: str, tools: list[str]) -> tuple[bool, list[str]]:
    text = answer.lower()
    missing = []
    for item in q.get("expect_all", []):
        alternatives = [a.strip().lower() for a in item.split("|")]
        if not any(a in text for a in alternatives):
            missing.append(item)
    tool_ok = not q.get("expect_tools") or any(t in tools for t in q["expect_tools"])
    if not tool_ok:
        missing.append(f"tool:{'/'.join(q['expect_tools'])}")
    return not missing, missing


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--agents", nargs="*", default=DEFAULT_AGENTS)
    parser.add_argument("--only", nargs="*", help="question ids to run")
    args = parser.parse_args()

    questions = yaml.safe_load((ROOT / "evals" / "questions.yaml").read_text())["questions"]
    if args.only:
        questions = [q for q in questions if q["id"] in args.only]

    results: dict[str, dict[str, tuple[bool, list[str], list[str]]]] = {}
    for name in args.agents:
        agent = importlib.import_module(f"{name}.agent").root_agent
        results[name] = {}
        for q in questions:
            start = time.time()
            try:
                answer, tools = await ask(agent, q["question"])
            except Exception as exc:  # keep going; record the failure
                answer, tools = f"ERROR: {exc}", []
            ok, missing = score(q, answer, tools)
            results[name][q["id"]] = (ok, missing, tools)
            print(f"[{name}] {q['id']}: {'PASS' if ok else 'FAIL'} "
                  f"({time.time() - start:.0f}s) tools={sorted(set(tools))} missing={missing}")

    # markdown report
    lines = ["# Evaluation results", "", f"Run: {datetime.now():%Y-%m-%d %H:%M}", ""]
    header = "| Question | Category | " + " | ".join(args.agents) + " |"
    lines += [header, "|" + "---|" * (len(args.agents) + 2)]
    for q in questions:
        cells = ["PASS" if results[a][q["id"]][0] else "fail" for a in args.agents]
        lines.append(f"| {q['id']} | {q['category']} | " + " | ".join(cells) + " |")
    totals = [sum(results[a][q['id']][0] for q in questions) for a in args.agents]
    lines.append("| **Total** | | " + " | ".join(f"**{t}/{len(questions)}**" for t in totals) + " |")
    report = "\n".join(lines)
    out_dir = ROOT / "evals" / "results"
    out_dir.mkdir(exist_ok=True)
    out = out_dir / f"results_{datetime.now():%Y%m%d_%H%M%S}.md"
    out.write_text(report + "\n")
    print("\n" + report + f"\n\nSaved: {out}")


if __name__ == "__main__":
    asyncio.run(main())
