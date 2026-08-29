# Day 27: Agent Human-in-the-Loop (HITL) Churn Risk Workflow

Hệ thống đánh giá rủi ro khách hàng rời bỏ (Churn Risk) và xử lý hành động bằng cơ chế **Human-in-the-Loop** sử dụng **LangGraph**, **Streamlit**, và **Pydantic**.

---

## 📁 Cấu trúc Dự án

```text
Day27-Agent-Human-in-the-Loop-2A202601216/
├── app.py              # Giao diện Streamlit: Phê duyệt HITL, Resume Graph, Xem Audit Trail
├── graph.py            # GraphState, Agent Node, Routing Logic, MemorySaver & compile interrupt_before
├── models.py           # Pydantic models: AuditEntry, CustomerData
├── audit_log.json      # File lưu nhật ký kiểm toán (Audit Trail)
├── test_workflow.py    # Script kiểm thử tự động quy trình LangGraph
├── requirements.txt    # Danh sách thư viện cần cài đặt
└── README.md           # Hướng dẫn chi tiết
```

---

## 🚀 Hướng dẫn Cài đặt & Chạy ứng dụng

### 1. Cài đặt thư viện
Mở Terminal / PowerShell tại thư mục dự án và chạy:
```bash
pip install -r requirements.txt
```
*(Hoặc: `pip install langgraph langchain-core streamlit pydantic`)*

### 2. Kiểm thử luồng LangGraph qua Terminal
Chạy script kiểm thử:
```bash
python test_workflow.py
```

### 3. Chạy Giao diện Streamlit
Khởi chạy web app Streamlit:
```bash
streamlit run app.py
```

Ứng dụng sẽ tự động mở tại `http://localhost:8501`.

---

## 🧠 Chi tiết Kỹ thuật

### 1. `GraphState` trong `graph.py`
Lưu trữ trạng thái xuyên suốt của workflow:
- `customer_id`: Mã khách hàng.
- `customer_data`: Dữ liệu phân tích hành vi khách hàng.
- `proposed_action`: Hành động đề xuất từ Agent.
- `confidence_score`: Điểm tin cậy (0.0 -> 1.0).
- `reasoning`: Lập luận chi tiết.
- `action_type`: Phân loại rủi ro (`"LOW_RISK"` / `"HIGH_RISK"`).
- `human_decision`: Quyết định từ con người (`"APPROVE"`, `"REJECT"`, `"EDIT"`).
- `final_action`: Hành động cuối cùng sau khi phê duyệt.
- `reviewer_id` & `reviewer_notes`: Thông tin người duyệt.
- `execution_status`: Trạng thái thực thi.

### 2. Định tuyến `route_action(state)`
- **Auto-Execute (Rủi ro thấp & độ tin cậy >= 0.75)**: Chuyển thẳng sang `execute_low_risk_action` và ghi `audit_log.json`.
- **Policy Override / Escalate (Rủi ro cao hoặc độ tin cậy < 0.75)**: Chuyển sang `execute_high_risk_action`.

### 3. Cơ chế ngắt luồng (Interrupt) & Resume
- Workflow được compile với `MemorySaver()` và cấu hình `interrupt_before=["execute_high_risk_action"]`.
- Khi đến node này, LangGraph tự động tạm dừng và trả quyền điều khiển về Streamlit UI.
- Người dùng thực hiện:
  - **Approve**: Phê duyệt hành động gốc.
  - **Reject**: Hủy bỏ hành động đề xuất.
  - **Edit**: Chỉnh sửa nội dung ưu đãi/chính sách trước khi thực thi.
- Streamlit cập nhật state qua `churn_graph.update_state()` và kích hoạt `churn_graph.invoke(None, config)` để tiếp tục hoàn tất quy trình và ghi vào `audit_log.json`.
