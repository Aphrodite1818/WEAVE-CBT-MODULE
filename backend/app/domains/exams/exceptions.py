# =========================== #
#     exams/exceptions.py     #
# =========================== #

"""Domain exceptions for examination authoring and lifecycle validation."""


class ExamDomainError(Exception):
    """Base exception for examination-domain failures."""


class ExamNotFound(ExamDomainError):
    """Raised when a requested local examination does not exist."""


class ExamStateError(ExamDomainError):
    """Raised when an exam lifecycle transition is invalid."""


class ExamAuthorizationError(ExamDomainError):
    """Raised when an actor is not authorized for an exam operation."""


class ExamAcademicScopeError(ExamDomainError):
    """Raised when synchronized academic references contradict one another."""


class ExamTargetScopeError(ExamDomainError):
    """Raised when a target class or assignment does not match the exam scope."""


class ExamQuestionScopeError(ExamDomainError):
    """Raised when source questions or point totals do not match the exam scope."""
