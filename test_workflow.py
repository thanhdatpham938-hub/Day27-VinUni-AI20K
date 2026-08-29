"""
Script kiểm thử toàn diện cho Bước 3 & Bước 4:
- Rule 1 (Policy Override): increase_credit_limit (confidence = 0.96) -> Interrupted -> Human Review
- Rule 2 (Auto-Execute): send_email (confidence = 0.92 >= 0.85) -> Auto Execute
- Rule 3 (Escalate/Suggest): send_email (confidence = 0.82 < 0.85) -> Interrupted -> Human Review
"""

import uuid
from graph import churn_graph


def test_rule_1_policy_override():
    print("\n" + "="*60)
    print("TEST RULE 1: Policy Override (increase_credit_limit, conf = 0.96)")
    print("="*60)
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    state_input = {
        "customer_id": "CUST-VIP-01",
        "customer_data": {
            "customer_id": "CUST-VIP-01",
            "toi": 15000.0,
            "churn_probability": 0.85,
            "support_tickets_last_month": 4
        },
        "proposed_action": "",
        "confidence_score": 0.0,
        "reasoning": "",
        "human_decision": None
    }

    # Bước 1: Khởi chạy graph -> Bị chặn lại trước execute_high_risk_action
    churn_graph.invoke(state_input, config=config)
    snapshot = churn_graph.get_state(config)
    
    print(f"👉 Proposed Action: {snapshot.values.get('proposed_action')}")
    print(f"👉 Confidence Score: {snapshot.values.get('confidence_score')}")
    print(f"🛑 Next Step (phải là execute_high_risk_action): {snapshot.next}")
    assert "execute_high_risk_action" in snapshot.next, "Lỗi: Không ngắt tại Rule 1!"
    print("✅ RULE 1 (POLICY OVERRIDE) HOẠT ĐỘNG CHÍNH XÁC: Đã ngắt trước khi thực thi!")

    # Bước 2: Human Reviewer phê duyệt & Resume
    churn_graph.update_state(config, values={"human_decision": "approve", "reviewer_id": "operator_01"})
    final_res = churn_graph.invoke(None, config=config)
    print(f"👉 Kết quả sau khi Resume: {final_res.get('final_action')} (Status: {final_res.get('execution_status')})")


def test_rule_2_auto_execute():
    print("\n" + "="*60)
    print("TEST RULE 2: Auto-Execute (send_email, conf = 0.92 >= 0.85)")
    print("="*60)
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    state_input = {
        "customer_id": "CUST-STABLE-02",
        "customer_data": {
            "customer_id": "CUST-STABLE-02",
            "toi": 5000.0,
            "churn_probability": 0.10,
            "support_tickets_last_month": 0
        },
        "proposed_action": "",
        "confidence_score": 0.0,
        "reasoning": "",
        "human_decision": None
    }

    final_res = churn_graph.invoke(state_input, config=config)
    print(f"👉 Proposed Action: {final_res.get('proposed_action')}")
    print(f"👉 Confidence Score: {final_res.get('confidence_score')}")
    print(f"👉 Status: {final_res.get('execution_status')} (Decision: {final_res.get('human_decision')})")
    status = str(final_res.get('execution_status', '')).lower()
    assert status in ["auto_executed", "executed"], "Lỗi: Rule 2 không tự động thực thi!"
    print("✅ RULE 2 (AUTO-EXECUTE) HOẠT ĐỘNG CHÍNH XÁC!")


def test_rule_3_escalate_suggest():
    print("\n" + "="*60)
    print("TEST RULE 3: Escalate/Suggest (send_email, conf = 0.82 < 0.85)")
    print("="*60)
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    state_input = {
        "customer_id": "CUST-DOUBT-03",
        "customer_data": {
            "customer_id": "CUST-DOUBT-03",
            "toi": 4000.0,
            "churn_probability": 0.35,
            "support_tickets_last_month": 1 # Tạo độ tin cậy 0.82 < 0.85
        },
        "proposed_action": "",
        "confidence_score": 0.0,
        "reasoning": "",
        "human_decision": None
    }

    churn_graph.invoke(state_input, config=config)
    snapshot = churn_graph.get_state(config)
    
    print(f"👉 Proposed Action: {snapshot.values.get('proposed_action')}")
    print(f"👉 Confidence Score: {snapshot.values.get('confidence_score')}")
    print(f"🛑 Next Step (phải bị ép buộc review): {snapshot.next}")
    assert "execute_high_risk_action" in snapshot.next, "Lỗi: Rule 3 không ép buộc Human Review!"
    print("✅ RULE 3 (ESCALATE/SUGGEST) HOẠT ĐỘNG CHÍNH XÁC: Đã chuyển sang Human Review vì confidence < 0.85!")


if __name__ == "__main__":
    test_rule_1_policy_override()
    test_rule_2_auto_execute()
    test_rule_3_escalate_suggest()
