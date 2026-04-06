from pydantic import BaseModel, Field
from typing import Optional, List, Any
from datetime import datetime
import uuid


def gen_id():
    return str(uuid.uuid4())


class AcademicYear(BaseModel):
    id: str = Field(default_factory=gen_id)
    name: str
    start_date: str
    end_date: str
    is_current: bool = False


class Class(BaseModel):
    id: str = Field(default_factory=gen_id)
    academic_year_id: str
    name: str
    section: str
    class_teacher_id: Optional[str] = None


class Subject(BaseModel):
    id: str = Field(default_factory=gen_id)
    class_id: str
    name: str
    teacher_id: Optional[str] = None
    max_marks: int = 100


class Guardian(BaseModel):
    id: str = Field(default_factory=gen_id)
    student_id: str
    name: str
    relation: str
    phone: str
    alt_phone: Optional[str] = None
    whatsapp_phone: Optional[str] = None
    email: Optional[str] = None
    is_primary: bool = False


class Student(BaseModel):
    id: str = Field(default_factory=gen_id)
    class_id: str
    user_id: Optional[str] = None
    name: str
    admission_number: Optional[str] = None
    roll_number: Optional[str] = None
    dob: Optional[str] = None
    gender: Optional[str] = None
    blood_group: Optional[str] = None
    photo_url: Optional[str] = None
    admission_date: str = Field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"))
    status: str = "active"
    is_active: bool = True
    uses_transport: bool = False
    bus_route: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class Staff(BaseModel):
    id: str = Field(default_factory=gen_id)
    user_id: str
    name: str
    staff_type: str
    employee_id: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    photo_url: Optional[str] = None
    qualification: Optional[str] = None
    specialization: Optional[str] = None
    department: Optional[str] = None
    join_date: Optional[str] = None
    salary: Optional[float] = None
    casual_leave_balance: int = 12
    medical_leave_balance: int = 10
    earned_leave_balance: int = 15
    is_active: bool = True
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class User(BaseModel):
    id: str = Field(default_factory=gen_id)
    name: str
    role: str
    phone: Optional[str] = None
    email: Optional[str] = None
    preferred_language: str = "en"
    is_active: bool = True


class FeeStructure(BaseModel):
    id: str = Field(default_factory=gen_id)
    academic_year_id: str
    class_name: str
    fee_type: str
    amount: float
    frequency: str
    due_day: Optional[int] = None
    is_optional: bool = False


class FeeTransaction(BaseModel):
    id: str = Field(default_factory=gen_id)
    student_id: str
    fee_structure_id: Optional[str] = None
    fee_type: str
    amount: float
    due_date: Optional[str] = None
    paid_date: Optional[str] = None
    status: str = "pending"
    payment_mode: Optional[str] = None
    receipt_number: Optional[str] = None
    transaction_ref: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class StudentAttendance(BaseModel):
    id: str = Field(default_factory=gen_id)
    student_id: str
    class_id: str
    date: str
    status: str
    marked_by: str


class StaffAttendance(BaseModel):
    id: str = Field(default_factory=gen_id)
    staff_id: str
    date: str
    status: str
    check_in: Optional[str] = None
    check_out: Optional[str] = None


class LeaveRequest(BaseModel):
    id: str = Field(default_factory=gen_id)
    staff_id: str
    leave_type: str
    start_date: str
    end_date: str
    reason: str
    status: str = "pending"
    approved_by: Optional[str] = None
    approved_at: Optional[str] = None
    rejection_reason: Optional[str] = None
    applied_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class Announcement(BaseModel):
    id: str = Field(default_factory=gen_id)
    title: str
    content: str
    audience_type: str = "all"
    audience_classes: Optional[List[str]] = None
    audience_roles: Optional[List[str]] = None
    channels: List[str] = ["push"]
    is_draft: bool = True
    sent_at: Optional[str] = None
    created_by: str
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class Enquiry(BaseModel):
    id: str = Field(default_factory=gen_id)
    student_name: str
    parent_name: str
    phone: str
    class_applying: Optional[str] = None
    status: str = "new"
    source: Optional[str] = None
    assigned_to: Optional[str] = None
    follow_up_date: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class Conversation(BaseModel):
    id: str = Field(default_factory=gen_id)
    user_id: str
    title: str = "New conversation"
    tool_context: Optional[str] = None
    is_pinned: bool = False
    is_starred: bool = False
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class Message(BaseModel):
    id: str = Field(default_factory=gen_id)
    conversation_id: str
    role: str
    content: Optional[str] = None
    rich_content: Optional[Any] = None
    tool_calls: Optional[Any] = None
    actions: Optional[Any] = None
    language_detected: str = "en"
    is_flagged: bool = False
    flag_reason: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())


# Request/Response models
class MessageRequest(BaseModel):
    text: str
    conversation_id: Optional[str] = None


class ConversationUpdate(BaseModel):
    title: Optional[str] = None
    is_pinned: Optional[bool] = None
    is_starred: Optional[bool] = None


class StudentCreate(BaseModel):
    name: str
    class_id: str
    admission_number: Optional[str] = None
    roll_number: Optional[str] = None
    dob: Optional[str] = None
    gender: Optional[str] = None
    phone: Optional[str] = None
    guardian_name: Optional[str] = None
    guardian_phone: Optional[str] = None


class AttendanceBulkRecord(BaseModel):
    student_id: str
    status: str  # present, absent, late, holiday


class AttendanceBulkRequest(BaseModel):
    class_id: str
    date: str
    records: List[AttendanceBulkRecord]


class FeePaymentRequest(BaseModel):
    student_id: str
    fee_type: str
    amount: float
    payment_mode: str
    status: Optional[str] = "paid"
    due_date: Optional[str] = None
    transaction_ref: Optional[str] = None


class LeaveApprovalRequest(BaseModel):
    status: str  # approved or rejected
    rejection_reason: Optional[str] = None
