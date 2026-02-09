from django.urls import path
from . import views

urlpatterns = [

    # =========================
    # AUTH
    # =========================
    path("", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path(
        "force-password-reset/",
        views.force_password_reset,
        name="force_password_reset"
    ),

    # =========================
    # WRAD ADMIN PANEL
    # =========================
    path("wrad_panel/", views.admin_home, name="admin_home"),

    path(
        "wrad_panel/register-employee/",
        views.register_employee,
        name="register_employee"
    ),
    path(
        "wrad_panel/create-login/",
        views.create_login,
        name="create_login"
    ),

    # --- ADMIN / MANAGEMENT EDIT ---
    path(
        "wrad_panel/edit/<str:employee_id>/",
        views.edit_employee,
        name="edit_employee"
    ),

    # --- MANAGEMENT ACTIONS ---
    path(
        "wrad_panel/deactivate/<str:employee_id>/",
        views.deactivate_employee,
        name="deactivate_employee"
    ),
    path(
        "wrad_panel/restore/<str:employee_id>/",
        views.restore_employee,
        name="restore_employee"
    ),

    # --- EMPLOYEE LOGS ---
    path(
        "wrad_panel/employee-logs/",
        views.employee_logs,
        name="employee_logs"
    ),

    # =========================
    # USER PANEL
    # =========================
    path("home/", views.user_home, name="user_home"),
    path(
        "profile/update/",
        views.update_profile,
        name="update_profile"
    ),
    path(
        "leave/apply/",
        views.apply_leave,
        name="apply_leave"
    ),
    path(
        "leave/approvals/",
        views.leave_approvals,
        name="leave_approvals"
    ),
    path(
        "leave/process/<int:leave_id>/<str:action>/",
        views.process_leave,
        name="process_leave"
    ),
    path(
    "wrad_panel/reset-password/",
    views.admin_reset_password,
    name="admin_reset_password"
),
# =========================
# TASK MANAGEMENT
# =========================
path(
    "tasks/manage/",
    views.task_manage,
    name="task_manage"
),

path(
    "tasks/my/",
    views.my_tasks,
    name="my_tasks"
),

path(
    "tasks/update/<int:task_id>/",
    views.update_task,
    name="update_task"
),

]
