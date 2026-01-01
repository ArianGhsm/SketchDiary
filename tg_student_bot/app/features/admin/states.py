from aiogram.fsm.state import StatesGroup, State


class AdminStates(StatesGroup):
    browsing_students = State()
    editing_name_first = State()
    editing_name_last = State()
