from aiogram.fsm.state import State, StatesGroup


class AuthStates(StatesGroup):
    waiting_student_number = State()
    waiting_profile_text = State()


class GradeImportStates(StatesGroup):
    waiting_course_title = State()
    waiting_grade_lines = State()


class BroadcastStates(StatesGroup):
    waiting_message = State()


class FormCreateStates(StatesGroup):
    waiting_title = State()
    waiting_description = State()
    waiting_deadline = State()
    waiting_capacity = State()
    waiting_waitlist = State()
    waiting_question_type = State()
    waiting_question_label = State()
    waiting_question_required = State()
    waiting_question_options = State()
    waiting_add_another = State()


class FormSubmitStates(StatesGroup):
    answering_question = State()


class FormAdminStates(StatesGroup):
    waiting_manual_add_student = State()
    waiting_manual_remove_student = State()
    waiting_search_query = State()
    waiting_channel_id = State()


class AdminStates(StatesGroup):
    waiting_remove_student = State()
    waiting_student_search = State()
    waiting_channel_id = State()


class ScheduleStates(StatesGroup):
    waiting_channel_id = State()
    waiting_post_at = State()
    waiting_deadline = State()
    waiting_recurring = State()
