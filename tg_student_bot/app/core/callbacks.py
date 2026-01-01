from aiogram.filters.callback_data import CallbackData


class RegCb(CallbackData, prefix="reg"):
    action: str  # confirm_yes / confirm_no


class GradeCb(CallbackData, prefix="grade"):
    course: str


class AdminStudentCb(CallbackData, prefix="admstu"):
    student_id: str
    action: str  # grades / unlink / edit_name / back
