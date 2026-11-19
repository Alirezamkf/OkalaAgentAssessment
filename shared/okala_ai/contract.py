from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class EventType(str, Enum):
    TAB_HIDDEN = "TabHidden"
    CAMERA_STOPPED = "CameraStopped"
    SCREEN_STOPPED = "ScreenShareStopped"
    COPY = "CopyAttempt"
    PASTE = "PasteAttempt"
    REENTERED = "Reentered"
    CONCURRENT = "ConcurrentSessionBlocked"
    IDLE = "Idle"
    DISCONNECTED = "NetworkDisconnected"
    RESTORED = "NetworkRestored"
    GAP = "RecordingGap"


class Event(StrictModel):
    event_type: EventType
    timestamp: datetime
    duration_seconds: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def aware_timestamp(self):
        if self.timestamp.utcoffset() is None:
            raise ValueError("Timezone required")
        return self


class EventRequest(StrictModel):
    # Keep provider input bounded. The backend fails closed above this limit;
    # it must never summarize a truncated subset as if it were complete.
    events: list[Event] = Field(max_length=100)

    @model_validator(mode="after")
    def chronological(self):
        if self.events != sorted(self.events, key=lambda event: event.timestamp):
            raise ValueError("Events must be chronological")
        return self


class Category(str, Enum):
    STATUS = "status_counts"
    SCORES = "score_statistics"
    EVENTS = "highest_event_count"
    RECORDINGS = "incomplete_recordings"


class ReportRequest(StrictModel):
    category: Category
    counts: dict[str, int] | None = None
    scored_attempts: int | None = Field(default=None, ge=0)
    average: float | None = Field(default=None, ge=0)
    minimum: float | None = Field(default=None, ge=0)
    maximum: float | None = Field(default=None, ge=0)
    highest_count: int | None = Field(default=None, ge=0)
    matching_attempts: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def category_fields(self):
        allowed = {
            Category.STATUS: {"category", "counts"},
            Category.SCORES: {"category", "scored_attempts", "average", "minimum", "maximum"},
            Category.EVENTS: {"category", "highest_count", "matching_attempts"},
            Category.RECORDINGS: {"category", "matching_attempts"},
        }[self.category]
        populated = {key for key, value in self.model_dump().items() if value is not None}
        if not populated <= allowed:
            raise ValueError("Unexpected report data")
        if self.category == Category.STATUS:
            statuses = {"Not Started", "In Progress", "Submitted", "Timed Out", "Interrupted", "Cancelled"}
            if self.counts is None or set(self.counts) != statuses or any(type(v) is not int or v < 0 for v in self.counts.values()):
                raise ValueError("Invalid status counts")
        elif self.category == Category.SCORES:
            if self.scored_attempts is None:
                raise ValueError("Missing scored count")
            values = [self.minimum, self.average, self.maximum]
            if self.scored_attempts == 0:
                if any(v is not None for v in values):
                    raise ValueError("No scores available")
            elif any(v is None for v in values) or not self.minimum <= self.average <= self.maximum:
                raise ValueError("Invalid score statistics")
        elif self.matching_attempts is None or (self.category == Category.EVENTS and self.highest_count is None):
            raise ValueError("Missing counts")
        return self


class AIResponse(StrictModel):
    status: Literal["available", "empty", "unavailable"]
    text: str = Field(max_length=16000)


UNAVAILABLE = "سرویس هوش مصنوعی در دسترس نیست. داده‌های اصلی همچنان قابل بررسی هستند."
NO_EVENTS = "هیچ رخدادی برای این تلاش ثبت نشده است."
EVENTS_TOO_MANY = "تعداد رخدادها برای تهیهٔ خلاصهٔ قابل‌اعتماد بیش از حد است؛ فهرست خام رخدادها را بررسی کنید."
UNSUPPORTED = "خارج از گزارش‌های پشتیبانی‌شده"
EVENT_LABELS = dict(zip([item.value for item in EventType], [
    "پنهان شدن برگه", "توقف دوربین", "توقف اشتراک صفحه", "تلاش برای کپی در برنامه",
    "تلاش برای جای‌گذاری در برنامه", "ورود مجدد", "مسدود شدن نشست هم‌زمان", "عدم تعامل",
    "قطع اتصال شبکه", "بازگشت اتصال شبکه", "فاصله در ضبط",
]))
STATUS_LABELS = dict(zip(["Not Started", "In Progress", "Submitted", "Timed Out", "Interrupted", "Cancelled"],
                         ["شروع‌نشده", "در حال انجام", "ثبت‌شده", "پایان زمان", "متوقف‌شده", "لغوشده"]))


def approved_phrasings(request: EventRequest | ReportRequest) -> list[str]:
    """Bound factual output to complete approved Persian phrasings.

    The LLM chooses a concise phrasing; arbitrary prose is rejected rather than
    relying on a prompt or numeric regex to prevent invented causes and facts.
    """
    if isinstance(request, EventRequest):
        if not request.events:
            return [NO_EVENTS]
        lines = []
        for event in request.events:
            duration = "" if event.duration_seconds is None else f"؛ مدت ثبت‌شده: {event.duration_seconds:g} ثانیه"
            lines.append(f"{event.timestamp.isoformat()}: {EVENT_LABELS[event.event_type.value]}{duration}")
        body = "\n".join(lines)
        return [f"رخدادهای ثبت‌شده به ترتیب زمانی:\n{body}\nاین رخدادها صرفاً نشانه‌های بازبینی هستند.",
                f"خلاصهٔ زمانی رخدادها:\n{body}\nاین رخدادها صرفاً نشانه‌های بازبینی هستند."]
    if request.category == Category.STATUS:
        body = "؛ ".join(f"{STATUS_LABELS[key]}: {value}" for key, value in request.counts.items())
    elif request.category == Category.SCORES:
        body = "نمره نهایی ثبت‌شده‌ای وجود ندارد." if request.scored_attempts == 0 else (
            f"تعداد نمره‌های نهایی: {request.scored_attempts}؛ میانگین: {request.average:g}؛ کمینه: {request.minimum:g}؛ بیشینه: {request.maximum:g}")
    elif request.category == Category.EVENTS:
        body = "هیچ رخدادی ثبت نشده است؛ تلاشی برای این گزارش انتخاب نشده است." if request.highest_count == 0 else (
            f"بیشترین تعداد رخداد: {request.highest_count}؛ تعداد تلاش‌های هم‌رتبه: {request.matching_attempts}")
    else:
        body = f"تعداد تلاش‌های دارای ضبط ناقص: {request.matching_attempts}"
    return [f"نتیجه گزارش: {body}", f"بر اساس داده‌های ثبت‌شده: {body}"]


def validate_response(request: EventRequest | ReportRequest, response: AIResponse) -> AIResponse:
    if response.status == "available" and response.text in approved_phrasings(request):
        return response
    if isinstance(request, EventRequest) and not request.events and response.status == "empty" and response.text == NO_EVENTS:
        return response
    if response.status == "unavailable" and response.text == UNAVAILABLE:
        return response
    raise ValueError("Ungrounded agent response")
