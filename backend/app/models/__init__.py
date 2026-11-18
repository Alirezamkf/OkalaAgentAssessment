"""Backend ORM models and their registration in the shared metadata."""

from app.models.candidate import Candidate
from app.models.exam import Exam, ExamStatus
from app.models.exam_invitation import ExamInvitation, InvitationStatus
from app.models.hr_user import HRUser
from app.models.question import Question
from app.models.question_option import QuestionOption

__all__ = [
    "Candidate",
    "Exam",
    "ExamInvitation",
    "ExamStatus",
    "HRUser",
    "InvitationStatus",
    "Question",
    "QuestionOption",
]
