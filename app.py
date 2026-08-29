import streamlit as st
import json
import os
import uuid
import pandas as pd
from graph import build_and_compile_graph, AUDIT_LOG_FILE
from models import CustomerData

# =====================================================================
# BƯỚC 5 - XÂY DỰNG STREAMLIT APPROVAL INTERFACE
# =====================================================================

st.set_page_config(
    page_title="Human-in-the-Loop Approval Dashboard | LangGraph",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 1. Khởi tạo compiled graph trong session_state để tránh tạo lại khi rerun
if "graph" not in st.session_state:
    st.session_state.graph = build_and_compile_graph()

if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())

if "edit_mode" not in st.session_state:
    st.session_state.edit_mode = False


# Dữ liệu khách hàng thử nghiệm
SAMPLE_PRESETS = {
    "CUST001 (Rủi ro cao -> increase_credit_limit [Cần Duyệt])": CustomerData(
        customer_id="CUST001",
        customer_name="Trần Văn Nam",
        toi=15000.0,
        churn_probability=0.85,
        credit_score=720,
        support_tickets_last_month=4,
        tenure_months=6
    ),
    "CUST002 (Rủi ro thấp -> send_email [Auto Execute])": CustomerData(
        customer_id="CUST002",
        customer_name="Nguyễn Thị Mai",
        toi=4500.0,
        churn_probability=0.15,
        credit_score=780,
        support_tickets_last_month=0,
        tenure_months=24
    ),
    "CUST003 (Confidence thấp 0.82 -> send_email [Escalate Duyệt])": CustomerData(
        customer_id="CUST003",
        customer_name="Lê Hoàng Long",
        toi=3500.0,
        churn_probability=0.35,
        credit_score=680,
        support_tickets_last_month=1,
        tenure_months=12
    ),
    "Nhập tùy chỉnh khách hàng": None
}


# Sidebar điều khiển
with st.sidebar:
    st.image("https://api.iconify.design/heroicons:shield-check-solid.svg?color=%234F46E5", width=42)
    st.title("HITL Review Portal")
    st.caption("Day 27: Human-in-the-Loop LangGraph")
    st.divider()
    
    reviewer_id = st.text_input("👤 Reviewer ID (Operator):", value="operator_01")
    
    st.markdown("### 🧵 Checkpoint Config")
    st.code(f"Thread ID: {st.session_state.thread_id[:8]}...", language="text")
    if st.button("🔄 Tạo phiên làm việc mới (Reset)", use_container_width=True):
        st.session_state.thread_id = str(uuid.uuid4())
        st.session_state.edit_mode = False
        st.rerun()

    st.divider()
    st.markdown("""
    **Quy tắc điều phối (Routing):**
    - ⚡ `send_email` + conf $\ge 0.85 \\rightarrow$ **Auto Execute**
    - 🛑 `increase_credit_limit` $\\rightarrow$ **Policy Override (Duyệt)**
    - ⚠️ conf $< 0.85 \\rightarrow$ **Escalate/Suggest (Duyệt)**
    """)


# Tabs chính
tab_review, tab_audit, tab_docs = st.tabs([
    "🎯 Review & Approval Interface",
    "📋 Audit Log Viewer (audit_log.json)",
    "📐 Workflow Architecture"
])


# =====================================================================
# TAB 1: STREAMLIT APPROVAL INTERFACE
# =====================================================================
with tab_review:
    st.title("Human Approval Interface")
    st.markdown("*Bảng điều khiển dành cho Human Operator phê duyệt các pending actions bị tạm dừng bởi LangGraph.*")

    col_form, col_action = st.columns([1, 1], gap="large")

    with col_form:
        st.subheader("1. Chọn hoặc Nhập Khách hàng")
        selected_option = st.selectbox("Chọn hồ sơ mẫu:", list(SAMPLE_PRESETS.keys()))
        preset_data = SAMPLE_PRESETS[selected_option]

        with st.form("customer_input_form"):
            c_id = st.text_input("Customer ID:", value=preset_data.customer_id if preset_data else "CUST001")
            c_name = st.text_input("Customer Name:", value=preset_data.customer_name if preset_data else "Khách Hàng A")
            
            c1, c2 = st.columns(2)
            with c1:
                toi_val = st.number_input("Total Operating Income (TOI) ($):", min_value=500.0, max_value=100000.0, value=preset_data.toi if preset_data else 15000.0, step=500.0)
                churn_val = st.slider("Churn Probability:", min_value=0.0, max_value=1.0, value=preset_data.churn_probability if preset_data else 0.85, step=0.05)
            with c2:
                tickets_val = st.number_input("Support Tickets (Tháng gần nhất):", min_value=0, max_value=10, value=preset_data.support_tickets_last_month if preset_data else 4)
                tenure_val = st.number_input("Tenure (Tháng gắn bó):", min_value=1, max_value=120, value=preset_data.tenure_months if preset_data else 6)

            submit_eval = st.form_submit_button("🚀 Gửi dữ liệu vào Workflow", use_container_width=True, type="primary")

        if submit_eval:
            st.session_state.thread_id = str(uuid.uuid4())
            st.session_state.edit_mode = False
            
            customer_data = CustomerData(
                customer_id=c_id,
                customer_name=c_name,
                toi=toi_val,
                churn_probability=churn_val,
                support_tickets_last_month=tickets_val,
                tenure_months=tenure_val
            )
            
            config = {"configurable": {"thread_id": st.session_state.thread_id}}
            initial_state = {
                "customer_id": c_id,
                "customer_data": customer_data.model_dump(),
                "proposed_action": "",
                "confidence_score": 0.0,
                "reasoning": "",
                "human_decision": None
            }
            
            with st.spinner("AI Agent đang phân tích..."):
                st.session_state.graph.invoke(initial_state, config=config)
            st.rerun()

    with col_action:
        st.subheader("2. Action Card & Approval")
        
        config = {"configurable": {"thread_id": st.session_state.thread_id}}
        current_state = st.session_state.graph.get_state(config)

        if not current_state or not current_state.values:
            st.info("👈 Hãy chọn hồ sơ khách hàng và nhấn **'Gửi dữ liệu vào Workflow'** để bắt đầu.")
        else:
            state_val = current_state.values
            next_nodes = current_state.next

            # TRƯỜNG HỢP GRAPH TẠM DỪNG (INTERRUPTED) -> HIỂN THỊ ACTION CARD
            if "execute_high_risk_action" in next_nodes:
                c_id_display = state_val.get("customer_id", "CUST001")
                prop_action = state_val.get("proposed_action", "N/A")
                conf_val = state_val.get("confidence_score", 0.0)
                reason_val = state_val.get("reasoning", "Không có chi tiết")

                # Action Card sạch đẹp và chuẩn Streamlit Container
                with st.container(border=True):
                    st.warning("⚠️ **PENDING ACTION REVIEW (Workflow Tạm Dừng)**")
                    
                    col_info1, col_info2 = st.columns([1, 1])
                    with col_info1:
                        st.markdown(f"**Customer ID:** `{c_id_display}`")
                        st.markdown(f"**Proposed Action:** `{prop_action}`")
                    with col_info2:
                        st.markdown(f"**Confidence:** `{conf_val:.2f}`")
                        st.progress(conf_val)
                    
                    st.markdown("**Reasoning:**")
                    st.info(reason_val)

                st.markdown("#### 🔘 Quyết định của Operator")

                # Chế độ Edit
                if st.session_state.edit_mode:
                    edited_action_input = st.text_input(
                        "📝 Chỉnh sửa nội dung hành động:",
                        value="increase_credit_limit = 20,000,000",
                        help="Ví dụ: Giảm mức tín dụng đề xuất từ 50tr xuống 20tr"
                    )

                # 3 Buttons: Approve / Reject / Edit
                col_b1, col_b2, col_b3 = st.columns(3)
                
                with col_b1:
                    if st.button("✅ Approve", use_container_width=True, type="primary"):
                        st.session_state.graph.update_state(
                            config,
                            {
                                "human_decision": "approve",
                                "reviewer_id": reviewer_id,
                                "final_action": prop_action
                            }
                        )
                        with st.spinner("Đang tiếp tục workflow..."):
                            st.session_state.graph.invoke(None, config)
                        st.session_state.edit_mode = False
                        st.success("Đã phê duyệt (Approve) thành công!")
                        st.rerun()

                with col_b2:
                    if st.button("❌ Reject", use_container_width=True):
                        st.session_state.graph.update_state(
                            config,
                            {
                                "human_decision": "reject",
                                "reviewer_id": reviewer_id,
                                "final_action": "none (aborted by reviewer)"
                            }
                        )
                        with st.spinner("Đang hủy bỏ action..."):
                            st.session_state.graph.invoke(None, config)
                        st.session_state.edit_mode = False
                        st.warning("Đã từ chối (Reject) hành động!")
                        st.rerun()

                with col_b3:
                    if not st.session_state.edit_mode:
                        if st.button("✏️ Edit", use_container_width=True):
                            st.session_state.edit_mode = True
                            st.rerun()
                    else:
                        if st.button("💾 Lưu & Resume", use_container_width=True):
                            st.session_state.graph.update_state(
                                config,
                                {
                                    "human_decision": "edit",
                                    "reviewer_id": reviewer_id,
                                    "final_action": edited_action_input
                                }
                            )
                            with st.spinner("Đang cập nhật và tiếp tục..."):
                                st.session_state.graph.invoke(None, config)
                            st.session_state.edit_mode = False
                            st.info("Đã chỉnh sửa (Edit) và tiếp tục thành công!")
                            st.rerun()

            # TRƯỜNG HỢP GRAPH ĐÃ HOÀN TẤT
            else:
                with st.container(border=True):
                    st.success("🎉 **Workflow đã hoàn tất thành công!**")
                    st.markdown(f"- **Customer ID:** `{state_val.get('customer_id')}`")
                    st.markdown(f"- **Final Action:** `{state_val.get('final_action', state_val.get('proposed_action'))}`")
                    st.markdown(f"- **Decision:** `{state_val.get('human_decision', 'auto_approved')}`")
                    st.markdown(f"- **Reviewer:** `{state_val.get('reviewer_id', 'SYSTEM_AUTO')}`")
                    st.markdown(f"- **Confidence:** `{state_val.get('confidence_score'):.2f}`")


# =====================================================================
# TAB 2: AUDIT LOG VIEWER
# =====================================================================
with tab_audit:
    st.subheader("📋 Audit Trail Log (audit_log.json)")
    st.caption("Mọi quyết định của AI Agent và Human Reviewer đều được ghi nhận phục vụ kiểm toán.")

    if os.path.exists(AUDIT_LOG_FILE):
        try:
            with open(AUDIT_LOG_FILE, "r", encoding="utf-8") as f:
                logs_data = json.load(f)
        except Exception:
            logs_data = []
    else:
        logs_data = []

    if logs_data:
        df = pd.DataFrame(logs_data)
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Tổng logs", len(df))
        c2.metric("Approve", len(df[df["decision"].str.lower() == "approve"]))
        c3.metric("Reject", len(df[df["decision"].str.lower() == "reject"]))
        c4.metric("Edit / Auto", len(df[df["decision"].str.lower().isin(["edit", "auto_approved"])]))

        st.divider()
        st.dataframe(df, use_container_width=True, hide_index=True)
        
        st.download_button(
            "📥 Tải xuống Audit Log JSON",
            data=json.dumps(logs_data, ensure_ascii=False, indent=2),
            file_name="audit_log.json",
            mime="application/json"
        )
    else:
        st.info("Chưa có bản ghi kiểm toán nào.")


# =====================================================================
# TAB 3: WORKFLOW ARCHITECTURE
# =====================================================================
with tab_docs:
    st.subheader("📐 Human-in-the-Loop Workflow Architecture")
    st.markdown("""
```mermaid
flowchart TD
    Start([Customer Input: TOI, Churn Prob]) --> Eval[Node: evaluate_customer]
    
    Eval --> Route{Conditional Edge: route_action}
    
    Route -- "send_email & conf >= 0.85" --> LowRisk[Node: execute_low_risk_action]
    Route -- "increase_credit_limit OR conf < 0.85" --> InterruptPoint((🛑 INTERRUPT BEFORE))
    
    InterruptPoint --> StreamlitUI[Streamlit Action Card]
    StreamlitUI -- "Approve / Reject / Edit" --> UpdateState[graph.update_state + invoke None]
    
    UpdateState --> HighRisk[Node: execute_high_risk_action]
    
    LowRisk --> Audit[Node: log_audit_entry]
    HighRisk --> Audit
    
    Audit --> JSONFile[(audit_log.json)]
    Audit --> EndNode([END])
```
    """)
