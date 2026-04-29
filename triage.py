import json
import os
import re
from typing import Optional, Dict, Any

import pandas as pd
import requests
from dotenv import load_dotenv
from pydantic import ValidationError

from schemas import TriageResult
from rag import PolicyRetriever, format_policy_context


load_dotenv()

ORDERS_PATH = "data/orders.csv"

retriever = PolicyRetriever()


def load_orders() -> pd.DataFrame:
    return pd.read_csv(ORDERS_PATH)


def get_order_context(order_id: Optional[str]) -> Dict[str, Any]:
    if not order_id:
        return {
            "found": False,
            "message": "No order ID provided."
        }

    df = load_orders()
    row = df[df["order_id"].str.upper() == order_id.upper()]

    if row.empty:
        return {
            "found": False,
            "message": f"Order ID {order_id} was not found in the mock order table."
        }

    return {
        "found": True,
        **row.iloc[0].to_dict()
    }


def detect_language(text: str) -> str:
    arabic_chars = re.findall(r"[\u0600-\u06FF]", text)
    latin_chars = re.findall(r"[A-Za-z]", text)

    if arabic_chars and latin_chars:
        return "mixed"
    if arabic_chars:
        return "ar"
    if latin_chars:
        return "en"
    return "unknown"


def extract_json(text: str) -> str:
    """
    Extracts the first JSON object from an LLM response.
    """
    text = text.strip()

    if text.startswith("```"):
        text = re.sub(r"^```json", "", text, flags=re.IGNORECASE).strip()
        text = re.sub(r"^```", "", text).strip()
        text = re.sub(r"```$", "", text).strip()

    start = text.find("{")
    end = text.rfind("}")

    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found in model response.")

    return text[start:end + 1]


def build_prompt(
    order_id: str,
    customer_message: str,
    order_context: Dict[str, Any],
    policy_context: str
) -> str:
    schema = TriageResult.model_json_schema()

    return f"""
You are a multilingual customer support triage assistant for Mumzworld, an e-commerce platform for mothers and families in the GCC.

Your task:
Classify the customer's return/refund/exchange/order issue using ONLY:
1. the provided mock order context
2. the provided return policy context

Do not invent policy rules.
Do not approve compensation that is not supported by policy.
If the order is missing, the request is unclear, or the policy does not support a confident decision, return decision="uncertain".
For rash, allergy, injury, choking, burning smell, smoke, electrical issue, or child safety risk, return decision="escalate".
Do not provide medical advice.

Return ONLY valid JSON matching the provided schema.
Do not include markdown.
Do not include comments outside the JSON.

Customer order ID:
{order_id}

Customer message:
{customer_message}

Order context:
{json.dumps(order_context, ensure_ascii=False, indent=2)}

Relevant policy context:
{policy_context}

JSON schema:
{json.dumps(schema, ensure_ascii=False, indent=2)}
""".strip()


def call_openrouter(prompt: str) -> TriageResult:
    api_key = os.getenv("OPENROUTER_API_KEY")
    model = os.getenv("MODEL_NAME", "qwen/qwen-2.5-72b-instruct")

    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY is missing. Using fallback instead.")

    url = "https://openrouter.ai/api/v1/chat/completions"

    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "You output only valid JSON. You are careful, policy-grounded, and honest about uncertainty."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.1
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:8501",
        "X-Title": "Mumzworld Return Triage Assistant"
    }

    response = requests.post(url, headers=headers, json=payload, timeout=60)
    response.raise_for_status()

    raw_text = response.json()["choices"][0]["message"]["content"]
    json_text = extract_json(raw_text)

    return TriageResult.model_validate_json(json_text)


def fallback_triage(
    order_id: str,
    customer_message: str,
    order_context: Dict[str, Any],
    policy_context: str
) -> TriageResult:
    """
    Simple deterministic fallback so the demo still runs without an API key.
    This is not meant to replace the LLM. It also helps make evals reproducible.
    """
    text = customer_message.lower()
    lang = detect_language(customer_message)

    is_prompt_injection = any(x in text for x in [
        "ignore previous",
        "ignore all",
        "override",
        "approve my refund",
        "give me coupon",
        "تجاهل",
        "وافق",
        "قسيمة"
    ])

    safety = any(x in text for x in [
        "rash", "allergy", "allergic", "injury", "choking", "burning", "smoke",
        "electric", "unsafe", "طفح", "حساسية", "اختناق", "إصابة", "حرق", "دخان", "كهرباء"
    ])

    damaged = any(x in text for x in [
        "damaged", "broken", "defective", "not working", "cracked",
        "مكسور", "تالف", "خربان", "لا يعمل", "مكسورة"
    ])

    wrong_item = any(x in text for x in [
        "wrong item", "wrong product", "incorrect item",
        "منتج غلط", "منتج خطأ", "وصلني شيء آخر", "غلط"
    ])

    change_mind = any(x in text for x in [
        "changed my mind", "do not want", "don't want", "unopened", "unused",
        "غيرت رأيي", "لا أريده", "غير مستخدم", "لم أفتحه"
    ])

    if not order_context.get("found"):
        return TriageResult(
            intent="return_request",
            decision="uncertain",
            confidence=0.78,
            language_detected=lang,
            reason_category="missing_or_unknown_order",
            policy_basis=[
                "Policy says missing or unknown order IDs should return uncertain and ask for more information."
            ],
            missing_information=["Valid order ID"],
            risk_flags=[],
            customer_reply_en="I can help with this, but I need a valid order ID first so I can check the return eligibility.",
            customer_reply_ar="يمكنني مساعدتك في ذلك، لكن أحتاج أولاً إلى رقم طلب صحيح للتحقق من أهلية الإرجاع."
        )

    delivery_days = int(order_context.get("delivery_days_ago", 999))
    category = str(order_context.get("category", ""))

    if is_prompt_injection:
        return TriageResult(
            intent="unsupported_policy_override",
            decision="uncertain",
            confidence=0.86,
            language_detected=lang,
            reason_category="prompt_injection_or_unsupported_request",
            policy_basis=[
                "Policy says the assistant must not ignore instructions or approve unsupported compensation."
            ],
            missing_information=["Clear return reason"],
            risk_flags=["prompt_injection", "unsupported_compensation_request"],
            customer_reply_en="I cannot approve a refund or coupon without a valid policy-supported reason. Please share what issue you are facing with the item.",
            customer_reply_ar="لا يمكنني الموافقة على استرداد أو قسيمة بدون سبب واضح مدعوم بالسياسة. يرجى توضيح المشكلة التي تواجهها مع المنتج."
        )

    if safety:
        return TriageResult(
            intent="safety_complaint",
            decision="escalate",
            confidence=0.91,
            language_detected=lang,
            reason_category="possible_health_or_safety_issue",
            policy_basis=[
                "Policy says health, allergy, injury, choking, smoke, electrical, or safety issues must be escalated.",
                "The assistant must not provide medical advice."
            ],
            missing_information=["Photos if available", "Batch number if available", "More details about the issue"],
            risk_flags=["health_safety_issue", "human_review_required", "do_not_give_medical_advice"],
            customer_reply_en="I'm sorry to hear this. Because this may involve a health or safety concern, I’ll escalate it to our support team for urgent review. Please stop using the product and share photos, batch details, and any other relevant information if available.",
            customer_reply_ar="نأسف لسماع ذلك. لأن الأمر قد يتعلق بمشكلة صحية أو سلامة، سيتم تصعيد الطلب إلى فريق الدعم للمراجعة العاجلة. يرجى التوقف عن استخدام المنتج ومشاركة الصور ورقم التشغيلة وأي تفاصيل متاحة."
        )

    if damaged or wrong_item:
        if delivery_days <= 7:
            return TriageResult(
                intent="return_refund_or_exchange",
                decision="refund" if damaged else "exchange",
                confidence=0.88,
                language_detected=lang,
                reason_category="damaged_or_wrong_item",
                policy_basis=[
                    "Damaged or defective items are eligible for refund or exchange within 7 days.",
                    "Wrong items are eligible for exchange or refund within 7 days.",
                    f"Order was delivered {delivery_days} days ago."
                ],
                missing_information=["Photo of the item if available"],
                risk_flags=[],
                customer_reply_en="I'm sorry about the issue with your order. Based on the delivery date and return policy, this appears eligible for support. Please upload a photo of the item so we can continue processing the request.",
                customer_reply_ar="نأسف للمشكلة التي حدثت في طلبك. بناءً على تاريخ التسليم وسياسة الإرجاع، يبدو أن الطلب مؤهل للمساعدة. يرجى رفع صورة للمنتج حتى نتمكن من متابعة معالجة الطلب."
            )
        else:
            return TriageResult(
                intent="late_damaged_or_wrong_item_request",
                decision="escalate",
                confidence=0.74,
                language_detected=lang,
                reason_category="late_request",
                policy_basis=[
                    "Damaged/wrong-item requests are normally eligible within 7 days.",
                    "Late requests should be escalated or rejected depending on the case."
                ],
                missing_information=["Photo of item", "Reason for late reporting"],
                risk_flags=["late_request"],
                customer_reply_en="This request appears to be outside the normal return window, so I’ll escalate it for human review. Please share photos and any details about why the issue was reported late.",
                customer_reply_ar="يبدو أن هذا الطلب خارج فترة الإرجاع المعتادة، لذلك سيتم تصعيده للمراجعة من قبل فريق الدعم. يرجى مشاركة الصور وأي تفاصيل حول سبب الإبلاغ المتأخر."
            )

    if change_mind:
        hygiene_category = category in ["diapers", "baby_feeding", "personal_care"]

        if delivery_days <= 14 and not hygiene_category:
            return TriageResult(
                intent="change_of_mind_return",
                decision="store_credit",
                confidence=0.83,
                language_detected=lang,
                reason_category="change_of_mind",
                policy_basis=[
                    "Change-of-mind returns are eligible for store credit within 14 days if unopened and unused.",
                    f"Order was delivered {delivery_days} days ago."
                ],
                missing_information=["Confirmation that item is unopened and unused"],
                risk_flags=[],
                customer_reply_en="This may be eligible for store credit if the item is unopened, unused, and in original packaging. Please confirm the item condition.",
                customer_reply_ar="قد يكون هذا الطلب مؤهلاً لرصيد في المتجر إذا كان المنتج غير مفتوح وغير مستخدم وفي عبوته الأصلية. يرجى تأكيد حالة المنتج."
            )

        return TriageResult(
            intent="change_of_mind_return",
            decision="reject",
            confidence=0.79,
            language_detected=lang,
            reason_category="not_eligible_change_of_mind",
            policy_basis=[
                "Change-of-mind returns are limited to 14 days.",
                "Opened hygiene and baby care items are not returnable unless damaged, defective, or wrongly delivered."
            ],
            missing_information=[],
            risk_flags=["policy_restriction"],
            customer_reply_en="Based on the policy, this item does not appear eligible for a change-of-mind return. If the item was damaged, defective, or wrongly delivered, please share more details.",
            customer_reply_ar="بناءً على السياسة، لا يبدو أن هذا المنتج مؤهل للإرجاع بسبب تغيير الرأي. إذا كان المنتج تالفاً أو معيباً أو تم تسليمه بالخطأ، يرجى مشاركة المزيد من التفاصيل."
        )

    return TriageResult(
        intent="unclear_or_unsupported",
        decision="uncertain",
        confidence=0.65,
        language_detected=lang,
        reason_category="unclear_request",
        policy_basis=[
            "Policy says unclear or unsupported requests should return uncertain and ask for clarification."
        ],
        missing_information=["Clear reason for return, refund, or exchange"],
        risk_flags=[],
        customer_reply_en="I need a bit more information to help. Please tell us whether the item is damaged, wrong, unopened, or if there is another issue.",
        customer_reply_ar="أحتاج إلى مزيد من المعلومات للمساعدة. يرجى توضيح ما إذا كان المنتج تالفاً أو خاطئاً أو غير مفتوح أو إذا كانت هناك مشكلة أخرى."
    )


def triage(order_id: str, customer_message: str, use_llm: bool = True) -> TriageResult:
    order_context = get_order_context(order_id)

    retrieval_query = f"{customer_message}\n{json.dumps(order_context, ensure_ascii=False)}"
    policy_results = retriever.retrieve(retrieval_query, top_k=4)
    policy_context = format_policy_context(policy_results)

    prompt = build_prompt(
        order_id=order_id,
        customer_message=customer_message,
        order_context=order_context,
        policy_context=policy_context
    )

    if use_llm:
        try:
            return call_openrouter(prompt)
        except Exception as e:
            print(f"[WARN] LLM failed, using fallback. Reason: {e}")

    return fallback_triage(
        order_id=order_id,
        customer_message=customer_message,
        order_context=order_context,
        policy_context=policy_context
    )