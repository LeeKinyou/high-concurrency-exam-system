from core.constants import (
    ALLOWED_EXCEL_EXTENSIONS,
    DEFAULT_PAGE_SIZE,
    LOCKOUT_MINUTES,
    MAX_LOGIN_ATTEMPTS,
    MAX_UPLOAD_FILE_SIZE_MB,
    SESSION_ID_EXPIRE_SECONDS,
    Difficulty,
    ExamStatus,
    QuestionType,
    RecordStatus,
    SubmissionMethod,
    UserRole,
    Visibility,
)


class TestUserRole:
    def test_choices(self):
        assert UserRole.TEACHER == "teacher"
        assert UserRole.STUDENT == "student"

    def test_has_teacher_and_student(self):
        values = [c[0] for c in UserRole.choices]
        assert "teacher" in values
        assert "student" in values


class TestExamStatus:
    def test_all_statuses(self):
        assert ExamStatus.DRAFT == "draft"
        assert ExamStatus.PUBLISHED == "published"
        assert ExamStatus.ONGOING == "ongoing"
        assert ExamStatus.ENDED == "ended"


class TestRecordStatus:
    def test_all_statuses(self):
        assert RecordStatus.DRAFT == "draft"
        assert RecordStatus.SUBMITTED == "submitted"
        assert RecordStatus.AUTO_GRADED == "auto_graded"
        assert RecordStatus.MANUAL_GRADING == "manual_grading"
        assert RecordStatus.MANUAL_GRADED == "manual_graded"
        assert RecordStatus.REVIEWED == "reviewed"


class TestQuestionType:
    def test_types(self):
        assert QuestionType.CHOICE == "choice"
        assert QuestionType.BLANK == "blank"


class TestDifficulty:
    def test_levels(self):
        assert Difficulty.EASY == "easy"
        assert Difficulty.MEDIUM == "medium"
        assert Difficulty.HARD == "hard"


class TestVisibility:
    def test_values(self):
        assert Visibility.PUBLIC == "public"
        assert Visibility.CLASS_SPECIFIC == "class_specific"


class TestSubmissionMethod:
    def test_values(self):
        assert SubmissionMethod.MANUAL == "manual"
        assert SubmissionMethod.AUTO == "auto"


class TestNumericConstants:
    def test_login_constants(self):
        assert MAX_LOGIN_ATTEMPTS == 5
        assert LOCKOUT_MINUTES == 30

    def test_session_constants(self):
        assert SESSION_ID_EXPIRE_SECONDS == 300

    def test_file_constants(self):
        assert MAX_UPLOAD_FILE_SIZE_MB == 10
        assert ".xlsx" in ALLOWED_EXCEL_EXTENSIONS
        assert ".xls" in ALLOWED_EXCEL_EXTENSIONS

    def test_pagination(self):
        assert DEFAULT_PAGE_SIZE == 20
