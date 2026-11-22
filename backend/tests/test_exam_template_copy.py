"""Focused tests for copying reusable templates into independent exams."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.exam import Exam
from app.models.exam_question import ExamQuestion
from app.models.exam_question_option import ExamQuestionOption
from app.models.exam_template import ExamTemplate
from app.models.exam_template_question import ExamTemplateQuestion
from app.models.exam_template_question_option import ExamTemplateQuestionOption
from app.models.hr_user import HRUser
from app.services.exam_name import create_exam_from_template


@pytest.fixture
def db():
    engine = create_engine("sqlite+pysqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE hr_users ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, username VARCHAR(100) NOT NULL UNIQUE, "
            "password_hash VARCHAR(255) NOT NULL, first_name VARCHAR(100) NOT NULL, "
            "last_name VARCHAR(100) NOT NULL, position VARCHAR(150) NOT NULL, "
            "profile_image_reference VARCHAR(500))"
        )
        connection.exec_driver_sql(
            "CREATE TABLE exam_templates ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, name VARCHAR(200) NOT NULL, "
            "description TEXT, created_by_hr_user_id INTEGER NOT NULL, "
            "created_at DATETIME, updated_at DATETIME, "
            "FOREIGN KEY(created_by_hr_user_id) REFERENCES hr_users(id))"
        )
        connection.exec_driver_sql(
            "CREATE TABLE exam_template_questions ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, exam_template_id INTEGER NOT NULL, "
            "question_text TEXT NOT NULL, position INTEGER NOT NULL, score INTEGER NOT NULL, "
            "image_reference VARCHAR(500), created_at DATETIME, updated_at DATETIME, "
            "FOREIGN KEY(exam_template_id) REFERENCES exam_templates(id) ON DELETE CASCADE, "
            "UNIQUE(exam_template_id, position))"
        )
        connection.exec_driver_sql(
            "CREATE TABLE exam_template_question_options ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, exam_template_question_id INTEGER NOT NULL, "
            "option_text TEXT NOT NULL, position INTEGER NOT NULL, is_correct BOOLEAN NOT NULL, "
            "created_at DATETIME, updated_at DATETIME, "
            "FOREIGN KEY(exam_template_question_id) REFERENCES exam_template_questions(id) ON DELETE CASCADE, "
            "UNIQUE(exam_template_question_id, position))"
        )
        connection.exec_driver_sql(
            "CREATE TABLE exams ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, name VARCHAR(200) NOT NULL UNIQUE, "
            "exam_template_id INTEGER, status VARCHAR(20) NOT NULL DEFAULT 'Created', "
            "duration_minutes INTEGER NOT NULL DEFAULT 25, available_from DATETIME NOT NULL, "
            "available_until DATETIME NOT NULL, created_by_hr_user_id INTEGER NOT NULL, "
            "FOREIGN KEY(exam_template_id) REFERENCES exam_templates(id), "
            "FOREIGN KEY(created_by_hr_user_id) REFERENCES hr_users(id), "
            "CHECK(duration_minutes >= 20 AND duration_minutes <= 25), "
            "CHECK(available_until > available_from))"
        )
        connection.exec_driver_sql(
            "CREATE TABLE exam_questions ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, exam_id INTEGER NOT NULL, "
            "text TEXT NOT NULL, score INTEGER NOT NULL, image_reference VARCHAR(500), "
            "FOREIGN KEY(exam_id) REFERENCES exams(id), UNIQUE(id, exam_id))"
        )
        connection.exec_driver_sql(
            "CREATE TABLE exam_question_options ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, exam_question_id INTEGER NOT NULL, "
            "text TEXT NOT NULL, is_correct BOOLEAN NOT NULL, position INTEGER NOT NULL, "
            "FOREIGN KEY(exam_question_id) REFERENCES exam_questions(id), "
            "UNIQUE(exam_question_id, position))"
        )

    session = Session(engine)
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def create_template(db: Session) -> tuple[HRUser, ExamTemplate]:
    hr_user = HRUser(
        id=1,
        username="template-owner",
        password_hash="hash",
        first_name="Template",
        last_name="Owner",
        position="Recruiter",
    )
    db.add(hr_user)
    db.flush()

    template = ExamTemplate(
        id=1,
        name="Technical Template",
        created_by_hr_user_id=hr_user.id,
    )
    db.add(template)
    db.flush()

    first_question = ExamTemplateQuestion(
        id=1,
        exam_template_id=template.id,
        question_text="First question",
        position=1,
        score=10,
        image_reference="first.png",
    )
    second_question = ExamTemplateQuestion(
        id=2,
        exam_template_id=template.id,
        question_text="Second question",
        position=2,
        score=20,
        image_reference=None,
    )
    db.add_all([first_question, second_question])
    db.flush()

    db.add_all([
        ExamTemplateQuestionOption(
            id=1,
            exam_template_question_id=first_question.id,
            option_text="A",
            position=1,
            is_correct=False,
        ),
        ExamTemplateQuestionOption(
            id=2,
            exam_template_question_id=first_question.id,
            option_text="B",
            position=2,
            is_correct=True,
        ),
        ExamTemplateQuestionOption(
            id=3,
            exam_template_question_id=second_question.id,
            option_text="Yes",
            position=1,
            is_correct=True,
        ),
    ])
    db.flush()
    return hr_user, template


def exam_dates() -> tuple[datetime, datetime]:
    now = datetime.now(timezone.utc)
    return now, now + timedelta(days=7)


def test_create_exam_from_template_copies_all_question_and_option_fields(db: Session) -> None:
    hr_user, template = create_template(db)
    available_from, available_until = exam_dates()

    exam = create_exam_from_template(
        db,
        name="Copied Exam",
        duration_minutes=25,
        available_from=available_from,
        available_until=available_until,
        created_by_hr_user_id=hr_user.id,
        template=template,
    )
    db.commit()

    assert exam.exam_template_id == template.id
    copied_questions = db.query(ExamQuestion).filter_by(exam_id=exam.id).order_by(ExamQuestion.id).all()
    assert [(question.text, question.score, question.image_reference) for question in copied_questions] == [
        ("First question", 10, "first.png"),
        ("Second question", 20, None),
    ]

    first_options = db.query(ExamQuestionOption).filter_by(exam_question_id=copied_questions[0].id).order_by(ExamQuestionOption.position).all()
    assert [(option.text, option.position, option.is_correct) for option in first_options] == [
        ("A", 1, False),
        ("B", 2, True),
    ]


def test_template_copies_are_independent_across_multiple_exams(db: Session) -> None:
    hr_user, template = create_template(db)
    available_from, available_until = exam_dates()

    first = create_exam_from_template(db, name="Exam One", duration_minutes=20, available_from=available_from, available_until=available_until, created_by_hr_user_id=hr_user.id, template=template)
    db.commit()
    second = create_exam_from_template(db, name="Exam Two", duration_minutes=20, available_from=available_from, available_until=available_until, created_by_hr_user_id=hr_user.id, template=template)
    db.commit()

    first_questions = db.query(ExamQuestion).filter_by(exam_id=first.id).all()
    second_questions = db.query(ExamQuestion).filter_by(exam_id=second.id).all()
    assert {question.id for question in first_questions}.isdisjoint(question.id for question in second_questions)
    assert len(first_questions) == len(second_questions) == 2


def test_editing_template_after_creation_does_not_change_exam_copies(db: Session) -> None:
    hr_user, template = create_template(db)
    available_from, available_until = exam_dates()
    exam = create_exam_from_template(db, name="Stable Exam", duration_minutes=25, available_from=available_from, available_until=available_until, created_by_hr_user_id=hr_user.id, template=template)
    db.commit()

    source_question = db.query(ExamTemplateQuestion).filter_by(id=1).one()
    source_question.question_text = "Edited source"
    source_question.options[0].option_text = "Edited option"
    db.commit()

    copied_question = db.query(ExamQuestion).filter_by(exam_id=exam.id, text="First question").one()
    copied_option = db.query(ExamQuestionOption).filter_by(exam_question_id=copied_question.id, position=1).one()
    assert copied_question.text == "First question"
    assert copied_option.text == "A"


def test_copy_failure_rolls_back_exam_and_previous_copies(db: Session) -> None:
    hr_user, template = create_template(db)
    available_from, available_until = exam_dates()

    db.execute(text(
        "CREATE TRIGGER fail_second_exam_question BEFORE INSERT ON exam_questions "
        "WHEN NEW.text = 'Second question' BEGIN SELECT RAISE(ABORT, 'forced copy failure'); END"
    ))

    with pytest.raises(IntegrityError):
        create_exam_from_template(
            db,
            name="Rollback Exam",
            duration_minutes=25,
            available_from=available_from,
            available_until=available_until,
            created_by_hr_user_id=hr_user.id,
            template=template,
        )

    db.rollback()
    assert db.query(Exam).filter_by(name="Rollback Exam").count() == 0
    assert db.query(ExamQuestion).count() == 0
    assert db.query(ExamQuestionOption).count() == 0
