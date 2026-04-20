from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)

from app_callbacks import (
    MENU_ADMIN_HELP,
    MENU_ADMIN_REMOVE,
    MENU_BACK,
    MENU_CANCEL,
    MENU_GRADES,
    MENU_HELP,
    MENU_PROFILE,
    MENU_REGISTER,
    MENU_REP_BROADCAST,
    MENU_REP_FORMS,
    MENU_REP_FORM_CREATE,
    MENU_REP_FORM_LIST,
    MENU_REP_HELP,
    MENU_REP_IMPORT_GRADES,
    MENU_REP_PANEL,
    PREFIX_JOIN_FORM_CANCEL,
    PREFIX_JOIN_FORM_CONFIRM,
    PREFIX_REP_FORM_REFRESH,
    PREFIX_REP_FORM_VIEW,
)
from bot.handlers import (
    back_to_menu,
    begin_register,
    begin_remove_student,
    begin_rep_broadcast,
    begin_rep_form_create,
    begin_rep_import_grades,
    cancel,
    join_form_cancel,
    join_form_confirm,
    menu_admin_help,
    menu_grades,
    menu_help,
    menu_profile,
    menu_rep_form_list,
    menu_rep_form_refresh,
    menu_rep_form_view,
    menu_rep_forms,
    menu_rep_help,
    menu_rep_panel,
    plain_text_router,
    receive_profile,
    receive_remove_student_number,
    receive_rep_broadcast_text,
    receive_rep_course_title,
    receive_rep_form_title,
    receive_rep_grade_list,
    receive_student_number,
    start,
    unknown_command,
)
from bot.states import (
    WAITING_PROFILE,
    WAITING_REMOVE_STUDENT_NUMBER,
    WAITING_REP_BROADCAST_TEXT,
    WAITING_REP_COURSE_TITLE,
    WAITING_REP_FORM_TITLE,
    WAITING_REP_GRADE_LIST,
    WAITING_STUDENT_NUMBER,
)


def build_application(bot_token: str) -> Application:
    app = ApplicationBuilder().token(bot_token).build()

    conversation = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CallbackQueryHandler(begin_register, pattern=f"^{MENU_REGISTER}$"),
            CallbackQueryHandler(begin_remove_student, pattern=f"^{MENU_ADMIN_REMOVE}$"),
            CallbackQueryHandler(begin_rep_import_grades, pattern=f"^{MENU_REP_IMPORT_GRADES}$"),
            CallbackQueryHandler(begin_rep_broadcast, pattern=f"^{MENU_REP_BROADCAST}$"),
            CallbackQueryHandler(begin_rep_form_create, pattern=f"^{MENU_REP_FORM_CREATE}$"),
        ],
        states={
            WAITING_STUDENT_NUMBER: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_student_number)
            ],
            WAITING_PROFILE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_profile)
            ],
            WAITING_REMOVE_STUDENT_NUMBER: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_remove_student_number)
            ],
            WAITING_REP_COURSE_TITLE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_rep_course_title)
            ],
            WAITING_REP_GRADE_LIST: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_rep_grade_list)
            ],
            WAITING_REP_BROADCAST_TEXT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_rep_broadcast_text)
            ],
            WAITING_REP_FORM_TITLE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_rep_form_title)
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CallbackQueryHandler(cancel, pattern=f"^{MENU_CANCEL}$"),
            CallbackQueryHandler(back_to_menu, pattern=f"^{MENU_BACK}$"),
        ],
        per_message=False,
    )

    app.add_handler(conversation)
    app.add_handler(CallbackQueryHandler(back_to_menu, pattern=f"^{MENU_BACK}$"))
    app.add_handler(CallbackQueryHandler(menu_profile, pattern=f"^{MENU_PROFILE}$"))
    app.add_handler(CallbackQueryHandler(menu_grades, pattern=f"^{MENU_GRADES}$"))
    app.add_handler(CallbackQueryHandler(menu_help, pattern=f"^{MENU_HELP}$"))
    app.add_handler(CallbackQueryHandler(menu_admin_help, pattern=f"^{MENU_ADMIN_HELP}$"))
    app.add_handler(CallbackQueryHandler(menu_rep_panel, pattern=f"^{MENU_REP_PANEL}$"))
    app.add_handler(CallbackQueryHandler(menu_rep_help, pattern=f"^{MENU_REP_HELP}$"))
    app.add_handler(CallbackQueryHandler(menu_rep_forms, pattern=f"^{MENU_REP_FORMS}$"))
    app.add_handler(CallbackQueryHandler(menu_rep_form_list, pattern=f"^{MENU_REP_FORM_LIST}$"))
    app.add_handler(CallbackQueryHandler(menu_rep_form_view, pattern=f"^{PREFIX_REP_FORM_VIEW}\\d+$"))
    app.add_handler(
        CallbackQueryHandler(menu_rep_form_refresh, pattern=f"^{PREFIX_REP_FORM_REFRESH}\\d+$")
    )
    app.add_handler(
        CallbackQueryHandler(join_form_confirm, pattern=f"^{PREFIX_JOIN_FORM_CONFIRM}\\d+$")
    )
    app.add_handler(
        CallbackQueryHandler(join_form_cancel, pattern=f"^{PREFIX_JOIN_FORM_CANCEL}\\d+$")
    )

    # Inline-first UX guard: keep free text only for active data-entry states.
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, plain_text_router))
    app.add_handler(MessageHandler(filters.COMMAND, unknown_command))
    return app
