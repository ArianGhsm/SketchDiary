from aiogram.fsm.state import StatesGroup, State


class RegistrationStates(StatesGroup):
    waiting_student_id = State()
    waiting_confirm = State()
