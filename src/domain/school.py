from dataclasses import dataclass

from .student import Student


@dataclass
class SchoolClass:
    name: str
    students: list[Student]

@dataclass
class School:
    name: str
    classes: list[SchoolClass]
