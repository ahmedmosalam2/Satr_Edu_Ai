from enum import Enum

class QuestionType(str, Enum):
    MCQ        = "MCQ"
    TRUE_FALSE = "TRUE_FALSE"
    ESSAY      = "ESSAY"
