import json
import os
from typing import TypedDict, Optional, Dict, Any
from datetime import datetime
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from models import AuditEntry

AUDIT_LOG_FILE = os.path.join(os.path.dirname(__file__), "audit_log.json")


# =====================================================================
# BƯỚC 1 - ĐỊNH NGHĨA GRAPH STATE
# =====================================================================
class GraphState(TypedDict, total=False):
    """
    GraphState lưu trữ xuyên suốt workflow:
    - customer_id: Mã khách hàng
    - proposed_action: Hành động đề xuất (send_email, increase_credit_limit, ...)
    - confidence_score: Điểm tin cậy (0.0 -> 1.0)
    - reasoning: Lập luận của AI Agent
    - human_decision: Quyết định từ con người ("approve", "reject", "edit", "auto_approved")
    - customer_data: Dữ liệu bổ sung (TOI, churn probability, ...)
    - final_action: Hành động cuối cùng sau review
    - reviewer_id: ID người duyệt (ví dụ "operator_01")
    - execution_status: Trạng thái thực thi ("auto_executed", "executed", "aborted", "executed_edited")
    """
    customer_id: str
    proposed_action: str
    confidence_score: float
    reasoning: str
    human_decision: Optional[str]
    customer_data: Optional[Dict[str, Any]]
    final_action: Optional[str]
    reviewer_id: Optional[str]
    execution_status: Optional[str]


# =====================================================================
# BƯỚC 2 - AGENT REASONING NODE
# =====================================================================
def evaluate_customer(state: GraphState) -> Dict[str, Any]:
    """
    Đánh giá Total Operating Income (TOI) và Churn Probability của khách hàng.
    Output:
    - proposed_action: 'send_email' (low-risk) hoặc 'increase_credit_limit' (high-risk)
    - confidence_score: 0.0 -> 1.0
    - reasoning: Chuỗi lập luận chi tiết
    """
    customer_data = state.get("customer_data", {})
    customer_id = state.get("customer_id", "CUST001")
    
    toi = float(customer_data.get("toi", 5000.0))
    churn_prob = float(customer_data.get("churn_probability", 0.3))
    support_tickets = int(customer_data.get("support_tickets_last_month", 0))

    if churn_prob >= 0.5 or support_tickets >= 3:
        proposed_action = "increase_credit_limit"
        confidence_score = 0.96 if toi >= 3000 else 0.72
        reasoning = (
            f"Customer has high churn probability ({churn_prob*100:.0f}%) "
            f"and TOI of ${toi:,.2f}. Increasing the credit limit may improve retention, "
            f"but involves financial risk requiring Human-in-the-Loop review."
        )
    else:
        proposed_action = "send_email"
        confidence_score = 0.92 if support_tickets == 0 else 0.82
        reasoning = (
            f"Customer has moderate churn probability ({churn_prob*100:.0f}%) "
            f"and no high-risk financial action is required."
        )

    return {
        "proposed_action": proposed_action,
        "confidence_score": confidence_score,
        "reasoning": reasoning,
    }


# =====================================================================
# BƯỚC 3 - CONFIDENCE ROUTING VÀ HARD RULES
# =====================================================================
def route_action(state: GraphState) -> str:
    """
    Conditional Edge Function xác định bước tiếp theo:
    - Rule 1 (Policy Override): proposed_action == 'increase_credit_limit' -> 'execute_high_risk_action'
    - Rule 2 (Auto-Execute): confidence_score >= 0.85 & low-risk -> 'execute_low_risk_action'
    - Rule 3 (Escalate/Suggest): confidence_score < 0.85 -> 'execute_high_risk_action'
    """
    proposed_action = state.get("proposed_action", "send_email")
    confidence_score = state.get("confidence_score", 1.0)
    
    if proposed_action == "increase_credit_limit":
        return "execute_high_risk_action"
        
    if confidence_score >= 0.85:
        return "execute_low_risk_action"
        
    return "execute_high_risk_action"


# =====================================================================
# BƯỚC 6 - GHI AUDIT LOG & XỬ LÝ QUYẾT ĐỊNH
# =====================================================================
def execute_low_risk_action(state: GraphState) -> Dict[str, Any]:
    """Tự động thực thi hành động rủi ro thấp (send_email)."""
    proposed = state.get("proposed_action", "send_email")
    return {
        "final_action": proposed,
        "human_decision": "auto_approved",
        "reviewer_id": "SYSTEM_AUTO",
        "execution_status": "auto_executed",
    }


def execute_high_risk_action(state: GraphState) -> Dict[str, Any]:
    """
    [BƯỚC 6] Thực thi hành động sau khi có Human Review (Approve / Reject / Edit):
    - Approve: Execute action (ví dụ: increase_credit_limit được phép thực hiện).
    - Reject: Abort action (không thực hiện proposed action).
    - Edit: Thực hiện action sau khi đã được human operator chỉnh sửa.
    """
    decision = (state.get("human_decision") or "approve").lower()
    proposed = state.get("proposed_action", "increase_credit_limit")
    reviewer_id = state.get("reviewer_id", "operator_01")
    
    if decision == "approve":
        final_action = proposed
        status = "executed"
    elif decision == "reject":
        final_action = "none (aborted by reviewer)"
        status = "aborted"
    elif decision == "edit":
        final_action = state.get("final_action", proposed)
        status = "executed_edited"
    else:
        final_action = proposed
        status = "executed"

    return {
        "final_action": final_action,
        "execution_status": status,
    }


def log_audit_entry(state: GraphState) -> Dict[str, Any]:
    """
    [BƯỚC 6] Khởi tạo AuditEntry và append vào file audit_log.json cục bộ.
    Đảm bảo mọi quyết định quan trọng của Agent và Human đều được truy vết.
    """
    decision = state.get("human_decision", "auto_approved")
    action_performed = state.get("final_action") or state.get("proposed_action") or "none"
    
    entry = AuditEntry(
        timestamp=datetime.now().isoformat(timespec="seconds"),
        agent_id="churn-risk-agent",
        customer_id=state.get("customer_id", "UNKNOWN"),
        action=action_performed,
        confidence=state.get("confidence_score", 0.0),
        reviewer_id=state.get("reviewer_id", "SYSTEM_AUTO"),
        decision=decision
    )
    
    logs = []
    if os.path.exists(AUDIT_LOG_FILE):
        try:
            with open(AUDIT_LOG_FILE, "r", encoding="utf-8") as f:
                logs = json.load(f)
        except Exception:
            logs = []
            
    logs.append(entry.model_dump())
    
    with open(AUDIT_LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(logs, f, ensure_ascii=False, indent=2)
        
    return {}


# =====================================================================
# BƯỚC 4 - COMPILE GRAPH VỚI INTERRUPTS & CHECKPOINTER
# =====================================================================
def build_and_compile_graph():
    """
    Xây dựng StateGraph và compile với MemorySaver() checkpointer + interrupt_before.
    """
    builder = StateGraph(GraphState)
    
    builder.add_node("evaluate_customer", evaluate_customer)
    builder.add_node("execute_low_risk_action", execute_low_risk_action)
    builder.add_node("execute_high_risk_action", execute_high_risk_action)
    builder.add_node("log_audit_entry", log_audit_entry)
    
    builder.set_entry_point("evaluate_customer")
    
    builder.add_conditional_edges(
        "evaluate_customer",
        route_action,
        {
            "execute_low_risk_action": "execute_low_risk_action",
            "execute_high_risk_action": "execute_high_risk_action"
        }
    )
    
    builder.add_edge("execute_low_risk_action", "log_audit_entry")
    builder.add_edge("execute_high_risk_action", "log_audit_entry")
    builder.add_edge("log_audit_entry", END)
    
    memory = MemorySaver()
    
    compiled_graph = builder.compile(
        checkpointer=memory,
        interrupt_before=["execute_high_risk_action"]
    )
    return compiled_graph


churn_graph = build_and_compile_graph()
