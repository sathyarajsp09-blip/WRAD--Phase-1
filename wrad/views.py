# ======================================================
# IMPORTS
# ======================================================

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.models import User
from django.db import IntegrityError
from django.db.models import Max, IntegerField
from django.db.models.functions import Cast, Substr
from django.forms.models import model_to_dict
from django.contrib.messages import get_messages

from datetime import date, datetime

# ======================================================
# MODELS
# ======================================================

from .models import (
    Employee,
    EmployeeLogHistory,
    LeaveRequest,
    LeaveApprovalLog,
    EmployeeSnapshot,
    Task,
)

# ======================================================
# FORMS
# ======================================================

from .forms import (
    EmployeeRegistryForm,
    PasswordCreationForm,
    EmployeeSelfUpdateForm,
    LeaveApplyForm,
    ForcePasswordResetForm,
    TaskCreateForm,
    TaskUpdateForm,
)

# ======================================================
# SNAPSHOT HELPER (AUDIT CORE)
# ======================================================

def serialize_dates(data):
    """
    Convert date/datetime objects to ISO strings
    so they can be safely stored in JSONField.
    """
    serialized = {}
    for key, value in data.items():
        if isinstance(value, (date, datetime)):
            serialized[key] = value.isoformat()
        else:
            serialized[key] = value
    return serialized


def create_employee_snapshot(employee, actor, action, before_state):
    """
    Create immutable snapshot for audit & compliance.
    """
    EmployeeSnapshot.objects.create(
        employee=employee,
        changed_by=actor,
        action=action,
        before_data=before_state,
        after_data=serialize_dates(model_to_dict(employee)),
    )

# ======================================================
# TASK ROLE DEFINITIONS
# ======================================================

TASK_EXECUTION_ROLES = [
    "ASSOCIATE",
    "SENIOR_ASSOCIATE",
    "TEAM_LEADER",
    "MANAGER",
    "VICE_PRESIDENT",
]

TASK_MANAGEMENT_ROLES = [
    "TEAM_LEADER",
    "MANAGER",
    "VICE_PRESIDENT",
]

# ======================================================
# ROLE / ACCESS HELPERS
# ======================================================

def can_access_task_workspace(employee):
    """
    Who can view & work on tasks (assignee side)
    """
    if not employee:
        return False
    return employee.designation in TASK_EXECUTION_ROLES


def can_manage_tasks(employee):
    """
    Who can assign & manage tasks (assignor side)
    """
    if not employee:
        return False
    return employee.designation in TASK_MANAGEMENT_ROLES


def is_management(employee):
    return employee.designation in ["VICE_PRESIDENT", "PRESIDENT", "CEO"]


def is_admin_department(employee):
    return employee.department == "ADMIN" and employee.designation != "CEO"


def can_access_admin_panel(employee):
    """
    Admin panel access rules:
    - Admin department employees
    - OR Top management (VP / President / CEO)
    """
    return is_admin_department(employee) or is_management(employee)

# ======================================================
# ID / USERNAME GENERATORS
# ======================================================

def generate_employee_id():
    last_number = (
        Employee.objects
        .annotate(num=Cast(Substr("employee_id", 3), IntegerField()))
        .aggregate(max_num=Max("num"))
        .get("max_num")
    )

    next_number = (last_number or 0) + 1
    return f"MD{next_number:05d}"


def generate_username(employee):
    """
    Generate unique username using employee name + ID.
    """
    parts = employee.employee_name.lower().split()

    if len(parts) == 1:
        base = parts[0]
    else:
        base = parts[0] if parts[0] == parts[-1] else parts[0] + parts[-1]

    num = int(employee.employee_id.replace("MD", ""))
    return f"{base}{num}@ward.in"
# ======================================================
# AUTHENTICATION VIEWS
# ======================================================

def login_view(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        login_as = request.POST.get("login_as")

        user = authenticate(request, username=username, password=password)

        if user is None:
            messages.error(request, "Invalid username or password.")
            return redirect("login")

        login(request, user)

        employee = get_object_or_404(Employee, user=user, is_deleted=False)

        # Force password reset check
        if employee.force_password_reset:
            return redirect("force_password_reset")

        # Admin login check
        if login_as == "admin":
            if not can_access_admin_panel(employee):
                messages.error(
                    request,
                    "You are not authorized to access the admin panel."
                )
                logout(request)
                return redirect("login")

            return redirect("admin_home")

        # Normal user login
        return redirect("user_home")

    return render(request, "auth/login.html")


@login_required
def force_password_reset(request):
    employee = get_object_or_404(Employee, user=request.user, is_deleted=False)

    if request.method == "POST":
        form = ForcePasswordResetForm(request.POST)

        if form.is_valid():
            request.user.set_password(form.cleaned_data["new_password"])
            request.user.save()
            update_session_auth_hash(request, request.user)

            employee.force_password_reset = False
            employee.save(update_fields=["force_password_reset"])

            messages.success(request, "Password updated successfully.")
            return redirect(
                "admin_home" if can_access_admin_panel(employee) else "user_home"
            )
    else:
        form = ForcePasswordResetForm()

    return render(
        request,
        "auth/force_password_reset.html",
        {
            "form": form,
            "is_admin": can_access_admin_panel(employee),
        }
    )


@login_required
def logout_view(request):
    logout(request)
    return redirect("login")
# ======================================================
# ADMIN PANEL – CORE VIEWS
# ======================================================

@login_required
def admin_home(request):
    # Clear stale messages (dashboard cleanliness)
    for _ in get_messages(request):
        pass

    employee = get_object_or_404(Employee, user=request.user, is_deleted=False)

    if not can_access_admin_panel(employee):
        messages.error(request, "Unauthorized access.")
        return redirect("user_home")

    # Management can see soft-deleted employees as well
    if is_management(employee):
        employees = Employee.objects.all()
    else:
        employees = Employee.objects.filter(is_deleted=False)

    return render(
        request,
        "admin/admin_home.html",
        {
            "employees": employees,
            "is_management": is_management(employee),
            "logged_in_employee": employee,
        }
    )


@login_required
def register_employee(request):
    admin_emp = get_object_or_404(Employee, user=request.user, is_deleted=False)

    if not can_access_admin_panel(admin_emp):
        messages.error(request, "Unauthorized access.")
        return redirect("admin_home")

    if request.method == "POST":
        form = EmployeeRegistryForm(request.POST)

        if form.is_valid():
            emp = form.save(commit=False)

            try:
                emp.employee_id = generate_employee_id()
                emp.save()
            except IntegrityError:
                messages.error(
                    request,
                    "Employee ID conflict detected. Please submit the form again."
                )
                return render(
                    request,
                    "admin/register_employee.html",
                    {"form": form}
                )

            # Audit log
            EmployeeLogHistory.objects.create(
                employee=emp,
                action="Employee registered by admin department"
            )

            messages.success(request, "Employee registered successfully.")
            return redirect("admin_home")
    else:
        form = EmployeeRegistryForm()

    return render(
        request,
        "admin/register_employee.html",
        {"form": form}
    )


@login_required
def create_login(request):
    admin_emp = get_object_or_404(Employee, user=request.user, is_deleted=False)

    if not can_access_admin_panel(admin_emp):
        messages.error(request, "Unauthorized access.")
        return redirect("admin_home")

    if request.method == "POST":
        form = PasswordCreationForm(request.POST)

        if form.is_valid():
            emp = Employee.objects.get(
                employee_id=form.cleaned_data["employee_id"]
            )

            username = generate_username(emp)

            user = User.objects.create(username=username)
            user.set_password(form.cleaned_data["password"])
            user.save()

            emp.user = user
            emp.force_password_reset = True
            emp.save(update_fields=["user", "force_password_reset"])

            EmployeeLogHistory.objects.create(
                employee=emp,
                action="Login credentials generated by admin department"
            )

            messages.success(request, "Login created successfully.")
            return redirect("admin_home")
    else:
        form = PasswordCreationForm()

    return render(
        request,
        "admin/create_login.html",
        {"form": form}
    )
# ======================================================
# ADMIN PANEL – MANAGEMENT & AUDIT
# ======================================================

@login_required
def edit_employee(request, employee_id):
    admin_emp = get_object_or_404(Employee, user=request.user, is_deleted=False)
    target_emp = get_object_or_404(Employee, employee_id=employee_id)

    # Admin panel access check
    if not can_access_admin_panel(admin_emp):
        messages.error(request, "Unauthorized access.")
        return redirect("admin_home")

    if request.method == "POST":
        form = EmployeeSelfUpdateForm(
            request.POST,
            instance=target_emp,
            current_employee=admin_emp
        )

        if form.is_valid():
            before_state = serialize_dates(model_to_dict(target_emp))
            form.save()

            create_employee_snapshot(
                employee=target_emp,
                actor=admin_emp,
                action="ADMIN_EDIT",
                before_state=before_state
            )

            # Optional admin comment
            comment = request.POST.get("admin_comment")
            if comment:
                EmployeeLogHistory.objects.create(
                    employee=target_emp,
                    action=f"Admin update by {admin_emp.employee_id}: {comment}"
                )

            messages.success(request, "Employee updated successfully.")
            return redirect("admin_home")
    else:
        form = EmployeeSelfUpdateForm(
            instance=target_emp,
            current_employee=admin_emp
        )

    return render(
        request,
        "admin/edit_employee.html",
        {
            "form": form,
            "employee": target_emp,
        }
    )


@login_required
def deactivate_employee(request, employee_id):
    if request.method != "POST":
        return redirect("admin_home")

    admin_emp = get_object_or_404(Employee, user=request.user, is_deleted=False)
    target = get_object_or_404(
        Employee,
        employee_id=employee_id,
        is_deleted=False
    )

    if not is_management(admin_emp):
        messages.error(request, "Only management can deactivate employees.")
        return redirect("admin_home")

    before_state = serialize_dates(model_to_dict(target))
    target.soft_delete(by_employee=admin_emp)

    create_employee_snapshot(
        employee=target,
        actor=admin_emp,
        action="SOFT_DELETE",
        before_state=before_state
    )

    EmployeeLogHistory.objects.create(
        employee=target,
        action=f"Employee deactivated by {admin_emp.employee_id}"
    )

    messages.success(request, "Employee deactivated successfully.")
    return redirect("admin_home")


@login_required
def restore_employee(request, employee_id):
    if request.method != "POST":
        return redirect("admin_home")

    admin_emp = get_object_or_404(Employee, user=request.user, is_deleted=False)
    target = get_object_or_404(
        Employee,
        employee_id=employee_id,
        is_deleted=True
    )

    if not is_management(admin_emp):
        messages.error(request, "Only management can restore employees.")
        return redirect("admin_home")

    before_state = serialize_dates(model_to_dict(target))
    target.restore()

    create_employee_snapshot(
        employee=target,
        actor=admin_emp,
        action="RESTORE",
        before_state=before_state
    )

    EmployeeLogHistory.objects.create(
        employee=target,
        action=f"Employee restored by {admin_emp.employee_id}"
    )

    messages.success(request, "Employee restored successfully.")
    return redirect("admin_home")


@login_required
def employee_logs(request):
    admin_emp = get_object_or_404(Employee, user=request.user, is_deleted=False)

    if not can_access_admin_panel(admin_emp):
        messages.error(request, "Unauthorized access.")
        return redirect("admin_home")

    logs = (
        EmployeeLogHistory.objects
        .select_related("employee")
        .order_by("-created_at")
    )

    return render(
        request,
        "admin/employee_logs.html",
        {"logs": logs}
    )


@login_required
def admin_reset_password(request):
    admin_emp = get_object_or_404(Employee, user=request.user, is_deleted=False)

    if not can_access_admin_panel(admin_emp):
        messages.error(request, "Unauthorized access.")
        return redirect("admin_home")

    if request.method == "POST":
        employee_id = request.POST.get("employee_id")
        new_password = request.POST.get("password")
        confirm_password = request.POST.get("confirm_password")

        if not employee_id or not new_password or not confirm_password:
            messages.error(request, "Please fill all fields.")
            return render(request, "admin/reset_password.html")

        if new_password != confirm_password:
            messages.error(request, "Passwords do not match.")
            return render(request, "admin/reset_password.html")

        try:
            employee = Employee.objects.get(
                employee_id=employee_id,
                is_deleted=False
            )
        except Employee.DoesNotExist:
            messages.error(request, "Invalid Employee ID.")
            return render(request, "admin/reset_password.html")

        if not employee.user:
            messages.error(
                request,
                "This employee does not have a login account."
            )
            return render(request, "admin/reset_password.html")

        employee.user.set_password(new_password)
        employee.user.save()

        employee.force_password_reset = True
        employee.save(update_fields=["force_password_reset"])

        EmployeeLogHistory.objects.create(
            employee=employee,
            action=f"Password reset by admin ({admin_emp.employee_id})"
        )

        messages.success(
            request,
            "Password reset successfully. "
            "User must set a new password on next login."
        )
        return redirect("admin_home")

    return render(request, "admin/reset_password.html")
# ======================================================
# USER DASHBOARD & PROFILE
# ======================================================

@login_required
def user_home(request):
    for _ in get_messages(request):
        pass

    employee = get_object_or_404(Employee, user=request.user, is_deleted=False)

    tasks = Task.objects.filter(assigned_to=employee)
    leaves = employee.leave_requests.all()

    context = {
        "employee": employee,

        # ===== DASHBOARD COUNTS (DERIVED) =====
        "active_tasks_count": tasks.exclude(status=Task.STATUS_COMPLETED).count(),
        "completed_tasks_count": tasks.filter(status=Task.STATUS_COMPLETED).count(),
        "pending_leaves_count": leaves.filter(status="SUBMITTED").count(),
        "approved_leaves_count": leaves.filter(status="APPROVED").count(),

        # ===== PREVIEWS =====
        "recent_tasks": tasks.order_by("-created_at")[:3],
        "recent_leaves": leaves.order_by("-created_at")[:3],

        "can_manage_tasks": can_manage_tasks(employee),
    }

    return render(request, "user/user_home.html", context)



@login_required
def update_profile(request):
    employee = get_object_or_404(Employee, user=request.user, is_deleted=False)

    # READ-ONLY PROFILE VIEW (Phase-1)
    form = EmployeeSelfUpdateForm(
        instance=employee,
        current_employee=employee
    )

    # Force-disable all fields (display only)
    for field in form.fields.values():
        field.disabled = True

    return render(
        request,
        "user/update_profile.html",
        {
            "employee": employee,
            "form": form,
            "readonly": True,
        }
    )
# ======================================================
# LEAVE WORKFLOW
# ======================================================

@login_required
def apply_leave(request):
    employee = get_object_or_404(Employee, user=request.user, is_deleted=False)

    # CEO cannot apply leave
    if employee.designation == "CEO":
        messages.error(request, "Leave not applicable for CEO.")
        return redirect("user_home")

    if request.method == "POST":
        form = LeaveApplyForm(request.POST)

        if form.is_valid():
            leave = form.save(commit=False)
            leave.employee = employee

            leave_type = form.cleaned_data.get("leave_type")
            start_date = form.cleaned_data.get("start_date")
            end_date = form.cleaned_data.get("end_date")
            reason = form.cleaned_data.get("reason", "")

            # =========================
            # PERMISSION LEAVE LOGIC
            # =========================
            if leave_type == "PERMISSION":
                permission_hours = request.POST.get("permission_hours")

                if not permission_hours:
                    messages.error(request, "Please select permission hours.")
                    return render(
                        request,
                        "user/apply_leave.html",
                        {
                            "form": form,
                            "employee": employee,
                        }
                    )

                # Permission is always single-day
                leave.start_date = start_date
                leave.end_date = start_date

                # Store hours descriptively in reason
                leave.reason = (
                    f"Permission: {permission_hours} hours\n"
                    f"{reason}"
                )

                # Date-based system → treat as 1 day
                leave.total_days = 1

            # =========================
            # NORMAL LEAVE LOGIC
            # =========================
            else:
                leave.start_date = start_date
                leave.end_date = end_date
                leave.total_days = (end_date - start_date).days + 1

            # Set first approver (single-level hierarchy)
            leave.current_approver = employee.reporting_person
            leave.save()

            EmployeeLogHistory.objects.create(
                employee=employee,
                action="Leave request submitted"
            )

            messages.success(request, "Leave submitted successfully.")
            return redirect("user_home")
    else:
        form = LeaveApplyForm()

    return render(
        request,
        "user/apply_leave.html",
        {
            "form": form,
            "employee": employee,
        }
    )


@login_required
def leave_approvals(request):
    employee = get_object_or_404(
        Employee,
        user=request.user,
        is_deleted=False
    )

    approvals = (
        LeaveRequest.objects
        .filter(current_approver=employee, is_active=True)
        .select_related("employee")
    )

    return render(
        request,
        "user/leave_approvals.html",
        {
            "approvals": approvals,
            "employee": employee,
        }
    )


@login_required
def process_leave(request, leave_id, action):
    employee = get_object_or_404(
        Employee,
        user=request.user,
        is_deleted=False
    )

    leave = get_object_or_404(
        LeaveRequest,
        id=leave_id,
        is_active=True
    )

    # ============================
    # AUTHORIZATION CHECK
    # ============================
    if leave.current_approver != employee:
        messages.error(
            request,
            "You are not authorized to act on this leave request."
        )
        return redirect("leave_approvals")

    if action not in ["approve", "reject", "send_back"]:
        messages.error(request, "Invalid action.")
        return redirect("leave_approvals")

    if request.method == "POST":
        remarks = request.POST.get("remarks", "").strip()

        # ============================
        # STATUS UPDATE (SINGLE-LEVEL)
        # ============================
        if action == "approve":
            leave.status = "APPROVED"
        elif action == "reject":
            leave.status = "REJECTED"
        elif action == "send_back":
            leave.status = "SENT_BACK"

        # Approval flow ENDS here
        leave.current_approver = None
        leave.save(update_fields=["status", "current_approver", "updated_at"])

        # ============================
        # APPROVAL LOG
        # ============================
        LeaveApprovalLog.objects.create(
            leave_request=leave,
            action_by=employee,
            action=leave.status,
            remarks=remarks
        )

        EmployeeLogHistory.objects.create(
            employee=leave.employee,
            action=(
                f"Leave {leave.status.lower()} by "
                f"{employee.designation} ({employee.employee_id})"
            )
        )

        messages.success(
            request,
            f"Leave request {leave.status.lower()} successfully."
        )

    return redirect("leave_approvals")
# ======================================================
# TASK MANAGEMENT SYSTEM
# ======================================================

@login_required
def task_manage(request):
    """
    Assignor (Team Leader and above) creates tasks
    for their direct reports.
    """
    assignor = get_object_or_404(Employee, user=request.user, is_deleted=False)

    # Access control: only TL+ can manage tasks
    if not can_manage_tasks(assignor):
        messages.error(request, "You are not authorized to manage tasks.")
        return redirect("user_home")

    if request.method == "POST":
        form = TaskCreateForm(request.POST, assignor=assignor)

        if form.is_valid():
            task = form.save(commit=False)
            task.assigned_by = assignor
            task.save()

            messages.success(request, "Task assigned successfully.")
            return redirect("task_manage")
    else:
        form = TaskCreateForm(assignor=assignor)

    tasks = (
        Task.objects
        .filter(assigned_by=assignor)
        .order_by("-created_at")
    )

    return render(
        request,
        "user/task_manage.html",
        {
            "form": form,
            "tasks": tasks,
        }
    )


@login_required
def my_tasks(request):
    employee = get_object_or_404(Employee, user=request.user, is_deleted=False)

    # Role gate
    if not can_access_task_workspace(employee):
        messages.error(request, "You are not authorized to access tasks.")
        return redirect("user_home")

    tasks = (
        Task.objects
        .filter(assigned_to=employee)
        .order_by("-created_at")
    )

    return render(
        request,
        "user/task_list.html",
        {
            "employee": employee,
            "tasks": tasks,
        }
    )


@login_required
def update_task(request, task_id):
    employee = get_object_or_404(
        Employee,
        user=request.user,
        is_deleted=False
    )

    task = get_object_or_404(Task, id=task_id)

    is_assignee = task.assigned_to == employee
    is_assignor = task.assigned_by == employee

    if not (is_assignee or is_assignor):
        messages.error(request, "You are not authorized to access this task.")
        return redirect("user_home")

    if request.method == "POST":
        if not is_assignee:
            messages.error(request, "Only the assignee can update this task.")
            return redirect("task_manage")

        form = TaskUpdateForm(
            request.POST,
            task=task,
            employee=employee
        )

        if form.is_valid():
            form.save()
            messages.success(request, "Task updated successfully.")
            return redirect("my_tasks")
    else:
        form = None
        if is_assignee:
            form = TaskUpdateForm(
                task=task,
                employee=employee,
                initial={
                    "status": task.status,
                    "progress_percent": task.progress_percent,
                }
            )

    return render(
        request,
        "user/task_workspace.html",
        {
            "task": task,
            "form": form,
            "logs": task.update_logs.all(),
            "is_assignee": is_assignee,
            "is_assignor": is_assignor,
        }
    )
