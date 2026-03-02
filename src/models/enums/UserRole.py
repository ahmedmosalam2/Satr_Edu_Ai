from enum import Enum

class UserRole(str, Enum):
    TEACHER    = "teacher"
    STUDENT    = "student"
    OPERATIONS = "operations"
    PARENT     = "parent"
