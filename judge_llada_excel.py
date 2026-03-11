#!/usr/bin/env python3
import argparse
import json
import os
import re
from dataclasses import dataclass
from typing import Optional

import pandas as pd


def auto_detect_columns(df: pd.DataFrame) -> tuple[str, str, Optional[str]]:
    cols = list(df.columns)

    def pick(patterns: list[str]) -> Optional[str]:
        for col in cols:
            low = str(col).lower()
            if all(re.search(p, low) for p in patterns):
                return col
        return None

    col20 = (
        pick([r"2[\._ ]?0", r"answer|回复|输出|response"]) or
        pick([r"2[\._ ]?0"]) 
    )
    col21 = (
        pick([r"2[\._ ]?1", r"answer|回复|输出|response"]) or
        pick([r"2[\._ ]?1"]) 
    )
    prompt_col = (
        pick([r"prompt|问题|question|query|指令|instruction"]) or None
    )

    if not col20 or not col21:
        raise ValueError(
            "无法自动识别2.0/2.1列，请用 --col20 和 --col21 显式指定。"
        )
    return col20, col21, prompt_col


@dataclass
class JudgeResult:
    winner: str  # 20|21|tie
    reason: str


class LLMJudge:
    def __init__(self, model: str, api_key: str, base_url: Optional[str] = None):
        from openai import OpenAI

        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model

    def judge(self, prompt: str, answer20: str, answer21: str) -> JudgeResult:
        system_prompt = (
            "你是严格、公正的中文评测员。请比较两个回答质量，维度包括：正确性、完整性、清晰度、安全性。"
            "如果难分高下可判定tie。"
            "只输出JSON，格式: {\"winner\":\"20|21|tie\",\"reason\":\"简短原因\"}。"
        )
        user_prompt = (
            f"用户问题:\n{prompt}\n\n"
            f"[模型2.0回答]\n{answer20}\n\n"
            f"[模型2.1回答]\n{answer21}\n"
        )
        rsp = self.client.chat.completions.create(
            model=self.model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        content = rsp.choices[0].message.content
        data = json.loads(content)
        winner = str(data.get("winner", "tie")).strip().lower()
        if winner not in {"20", "21", "tie"}:
            winner = "tie"
        reason = str(data.get("reason", ""))
        return JudgeResult(winner=winner, reason=reason)


class MockJudge:
    """无API时的本地兜底评估器，仅用于调试流程。"""

    def judge(self, prompt: str, answer20: str, answer21: str) -> JudgeResult:
        a20 = (answer20 or "").strip()
        a21 = (answer21 or "").strip()
        if len(a20) == len(a21):
            return JudgeResult("tie", "长度相同，mock判平")
        return (
            JudgeResult("20", "mock按长度更长判胜")
            if len(a20) > len(a21)
            else JudgeResult("21", "mock按长度更长判胜")
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="LLM-as-Judge 比较 llada2.0 与 llada2.1")
    parser.add_argument("--input", required=True, help="输入xlsx文件路径")
    parser.add_argument("--output", default=None, help="输出xlsx路径（默认覆盖输入文件）")
    parser.add_argument("--sheet", default=0, help="sheet名或索引")
    parser.add_argument("--col20", default=None, help="2.0回答列名")
    parser.add_argument("--col21", default=None, help="2.1回答列名")
    parser.add_argument("--prompt-col", default=None, help="问题/Prompt列名（可选）")
    parser.add_argument("--model", default=os.getenv("JUDGE_MODEL", "gpt-4o-mini"))
    parser.add_argument("--base-url", default=os.getenv("OPENAI_BASE_URL"))
    parser.add_argument("--mock", action="store_true", help="使用mock评测器，不调用LLM")
    args = parser.parse_args()

    in_path = args.input
    out_path = args.output or in_path

    df = pd.read_excel(in_path, sheet_name=args.sheet)

    col20, col21, auto_prompt = auto_detect_columns(df)
    col20 = args.col20 or col20
    col21 = args.col21 or col21
    prompt_col = args.prompt_col or auto_prompt

    if col20 not in df.columns or col21 not in df.columns:
        raise ValueError(f"列不存在: col20={col20}, col21={col21}")

    if args.mock:
        judge = MockJudge()
    else:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise EnvironmentError("未设置 OPENAI_API_KEY，无法调用LLM。可改用 --mock 测试流程。")
        judge = LLMJudge(model=args.model, api_key=api_key, base_url=args.base_url)

    winners = []
    reasons = []

    for _, row in df.iterrows():
        prompt = str(row.get(prompt_col, "")) if prompt_col else ""
        ans20 = "" if pd.isna(row[col20]) else str(row[col20])
        ans21 = "" if pd.isna(row[col21]) else str(row[col21])

        result = judge.judge(prompt, ans20, ans21)
        winners.append(result.winner)
        reasons.append(result.reason)

    df["winner"] = winners
    df["judge_reason"] = reasons
    df.to_excel(out_path, index=False)

    total = len(df)
    w20 = sum(1 for w in winners if w == "20")
    w21 = sum(1 for w in winners if w == "21")
    tie = sum(1 for w in winners if w == "tie")

    print("=== Win Rate ===")
    print(f"2.0 win rate: {w20/total:.2%} ({w20}/{total})")
    print(f"2.1 win rate: {w21/total:.2%} ({w21}/{total})")
    print(f"tie: {tie/total:.2%} ({tie}/{total})")
    print(f"输出文件: {out_path}")


if __name__ == "__main__":
    main()
