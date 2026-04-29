import json
from pathlib import Path

from triage import triage


EVAL_PATH = Path("data/eval_cases.json")


def run_evals(use_llm: bool = False):
    cases = json.loads(EVAL_PATH.read_text(encoding="utf-8"))

    results = []
    total = 0

    for case in cases:
        result = triage(
            order_id=case["order_id"],
            customer_message=case["message"],
            use_llm=use_llm
        )

        decision_ok = result.decision in case["expected_decision"]

        risk_required = case.get("must_include_risk_flag")
        if risk_required:
            risk_ok = risk_required in result.risk_flags
        else:
            risk_ok = True

        json_valid = True
        bilingual_ok = bool(result.customer_reply_en.strip()) and bool(result.customer_reply_ar.strip())
        policy_basis_ok = len(result.policy_basis) > 0

        score = sum([
            json_valid,
            decision_ok,
            risk_ok,
            bilingual_ok,
            policy_basis_ok
        ])

        total += score

        results.append({
            "id": case["id"],
            "message": case["message"],
            "expected": case["expected_decision"],
            "actual": result.decision,
            "risk_flags": result.risk_flags,
            "score": f"{score}/5"
        })

    max_score = len(cases) * 5

    print("\nEvaluation Results")
    print("=" * 80)

    for row in results:
        print(f"\nCase {row['id']}")
        print(f"Message: {row['message']}")
        print(f"Expected: {row['expected']}")
        print(f"Actual: {row['actual']}")
        print(f"Risk flags: {row['risk_flags']}")
        print(f"Score: {row['score']}")

    print("\n" + "=" * 80)
    print(f"Total score: {total}/{max_score}")
    print(f"Percentage: {(total / max_score) * 100:.1f}%")


if __name__ == "__main__":
    # Default is deterministic fallback eval.
    # Change to True if you want to evaluate the LLM behavior.
    run_evals(use_llm=False)