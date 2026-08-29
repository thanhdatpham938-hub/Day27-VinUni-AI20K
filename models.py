from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class CustomerData(BaseModel):
    """Mô hình dữ liệu hồ sơ khách hàng phục vụ đánh giá rủi ro rời bỏ và tài chính."""
    customer_id: str = Field(..., description="Mã định danh khách hàng")
    customer_name: str = Field(default="Khách hàng", description="Họ tên khách hàng")
    toi: float = Field(default=5000.0, description="Total Operating Income (TOI) ($)")
    churn_probability: float = Field(default=0.3, ge=0.0, le=1.0, description="Xác suất rời bỏ (0.0 -> 1.0)")
    credit_score: int = Field(default=700, description="Điểm tín dụng")
    support_tickets_last_month: int = Field(default=1, description="Số ticket hỗ trợ trong tháng gần nhất")
    tenure_months: int = Field(default=12, description="Số tháng gắn bó")


class AuditEntry(BaseModel):
    """
    [BƯỚC 1 & BƯỚC 6] Pydantic Model lưu vết kiểm toán (Audit Schema).
    Lưu lại đầy đủ:
    - timestamp: Thời điểm ghi nhận sự kiện (ISO format)
    - agent_id: Agent nào đưa ra quyết định?
    - action: Hành động được thực thi / đề xuất
    - confidence: Confidence của agent
    - reviewer_id: Ai review (operator_01 hoặc SYSTEM_AUTO)
    - decision: Human quyết định gì (approve / reject / edit / auto_approved)
    """
    timestamp: str = Field(
        default_factory=lambda: datetime.now().isoformat(timespec="seconds"),
        description="Thời điểm ghi nhận sự kiện"
    )
    agent_id: str = Field(default="churn-risk-agent", description="ID của AI Agent")
    action: str = Field(..., description="Hành động (send_email, increase_credit_limit, ...)")
    confidence: float = Field(..., description="Độ tin cậy của Agent (0.0 - 1.0)")
    reviewer_id: str = Field(default="SYSTEM_AUTO", description="ID người phê duyệt")
    decision: str = Field(..., description="Quyết định (approve / reject / edit / auto_approved)")
    customer_id: Optional[str] = Field(default="UNKNOWN", description="Mã khách hàng")
