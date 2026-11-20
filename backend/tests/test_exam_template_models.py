"""Static metadata tests for reusable exam templates."""

from app.database.base import Base
from app.models import (
    Exam,
    ExamTemplate,
    ExamTemplateQuestion,
    ExamTemplateQuestionOption,
    HRUser,
)


def test_reusable_template_tables_are_registered() -> None:
    assert ExamTemplate.__tablename__ == "exam_templates"
    assert ExamTemplateQuestion.__tablename__ == "exam_template_questions"
    assert ExamTemplateQuestionOption.__tablename__ == "exam_template_question_options"

    assert "exam_templates" in Base.metadata.tables
    assert "exam_template_questions" in Base.metadata.tables
    assert "exam_template_question_options" in Base.metadata.tables


def test_template_relationships_and_exam_reference() -> None:
    assert "created_exam_templates" in {prop.key for prop in HRUser.__mapper__.relationships}

    template = ExamTemplate.__mapper__
    question = ExamTemplateQuestion.__mapper__
    option = ExamTemplateQuestionOption.__mapper__

    assert template.relationships.questions.mapper.class_ is ExamTemplateQuestion
    assert question.relationships.exam_template.mapper.class_ is ExamTemplate
    assert question.relationships.options.mapper.class_ is ExamTemplateQuestionOption
    assert option.relationships.exam_template_question.mapper.class_ is ExamTemplateQuestion

    assert Exam.__table__.c.exam_template_id.nullable is True
    assert Exam.__table__.c.name.nullable is False


def test_template_constraints_preserve_order_and_one_correct_option() -> None:
    question_table = ExamTemplateQuestion.__table__
    option_table = ExamTemplateQuestionOption.__table__

    assert any(
        constraint.name == "uq_exam_template_questions_template_position"
        for constraint in question_table.constraints
    )
    assert any(
        constraint.name == "uq_exam_template_question_options_question_position"
        for constraint in option_table.constraints
    )
    assert any(
        index.name == "uq_exam_template_question_options_one_correct" and index.unique
        for index in option_table.indexes
    )
