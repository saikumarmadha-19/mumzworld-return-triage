import json
import streamlit as st

from triage import triage


st.set_page_config(
    page_title="Mumzworld Return Triage Assistant",
    page_icon="🍼",
    layout="wide"
)

st.title("🍼 Mumzworld Multilingual Return Triage Assistant")

st.markdown("""
This prototype triages customer return, refund, exchange, and escalation requests in English or Arabic.
It uses mock order data, a mock return policy, lightweight retrieval, LLM structured output, and schema validation.
""")

with st.sidebar:
    st.header("Settings")
    use_llm = st.checkbox("Use LLM via OpenRouter if API key is available", value=True)
    st.markdown("---")
    st.markdown("Example order IDs:")
    st.code("MW1001\nMW1002\nMW1003\nMW1005\nMW1008")

col1, col2 = st.columns([1, 2])

with col1:
    order_id = st.text_input("Order ID", value="MW1001")

with col2:
    customer_message = st.text_area(
        "Customer message",
        value="The stroller arrived damaged and I want a refund.",
        height=140
    )

if st.button("Triage Request", type="primary"):
    if not customer_message.strip():
        st.error("Please enter a customer message.")
    else:
        with st.spinner("Triaging request..."):
            result = triage(order_id=order_id.strip(), customer_message=customer_message.strip(), use_llm=use_llm)

        st.subheader("Decision")
        st.metric("Decision", result.decision)
        st.metric("Confidence", f"{result.confidence:.2f}")

        st.subheader("Structured JSON Output")
        st.json(json.loads(result.model_dump_json()))

        st.subheader("Suggested Customer Reply - English")
        st.write(result.customer_reply_en)

        st.subheader("Suggested Customer Reply - Arabic")
        st.write(result.customer_reply_ar)