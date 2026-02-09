from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.conf import settings


class Employee(models.Model):
    """
    Master employee record (Operational Model)

    - Controlled editing via role-based logic
    - Soft delete supported (Management only)
    - Hard delete restricted to Django Super User
    """

    # ---- System identity ----
    id = models.AutoField(primary_key=True)

    user = models.OneToOneField(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Linked login account"
    )

    # ======================================================
    # TAB 1: PERSONAL INFORMATION
    # ======================================================

    employee_name = models.CharField(max_length=100)

    date_of_birth = models.DateField(null=True, blank=True)

    BLOOD_GROUP_CHOICES = [
        ('A+', 'A+'), ('A-', 'A-'),
        ('B+', 'B+'), ('B-', 'B-'),
        ('O+', 'O+'), ('O-', 'O-'),
        ('AB+', 'AB+'), ('AB-', 'AB-'),
    ]
    blood_group = models.CharField(
        max_length=3,
        choices=BLOOD_GROUP_CHOICES,
        blank=True
    )

    MARITAL_STATUS_CHOICES = [
        ('SINGLE', 'Single'),
        ('MARRIED', 'Married'),
    ]
    marital_status = models.CharField(
        max_length=10,
        choices=MARITAL_STATUS_CHOICES,
        blank=True
    )

    email_address = models.EmailField(blank=True)

    residential_address = models.TextField(blank=True)
    permanent_address = models.TextField(blank=True)

    contact_number = models.CharField(max_length=15, blank=True)
    emergency_contact_number = models.CharField(max_length=15, blank=True)

    # ======================================================
    # TAB 2: OFFICIAL INFORMATION
    # ======================================================

    employee_id = models.CharField(
        max_length=20,
        unique=True,
        help_text="Official Employee ID"
    )

    DESIGNATION_CHOICES = [
        ('ASSOCIATE', 'Associate'),
        ('SENIOR_ASSOCIATE', 'Senior Associate'),
        ('TEAM_LEADER', 'Team Leader'),
        ('MANAGER', 'Manager'),
        ('SENIOR_MANAGER', 'Senior Manager'),
        ('VICE_PRESIDENT', 'Vice President'),
        ('PRESIDENT', 'President'),
        ('CEO', 'CEO'),
        ('HR', 'HR'),
    ]
    designation = models.CharField(
        max_length=30,
        choices=DESIGNATION_CHOICES,
        blank=True
    )

    DEPARTMENT_CHOICES = [
        ('IT', 'IT'),
        ('ADMIN', 'Admin'),
        ('DEVELOPER', 'Developer'),
        ('HR', 'HR'),
        ('MANAGEMENT', 'Management'),
    ]
    department = models.CharField(
        max_length=30,
        choices=DEPARTMENT_CHOICES,
        blank=True
    )

    client = models.CharField(max_length=100, blank=True)

    reporting_role = models.CharField(
        max_length=30,
        choices=DESIGNATION_CHOICES,
        blank=True,
        help_text="Role/designation this employee reports to"
    )

    reporting_person = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reportees',
        help_text="Actual employee in the selected reporting role"
    )

    joining_date = models.DateField(null=True, blank=True)
    ending_date = models.DateField(null=True, blank=True)

    EMPLOYMENT_STATUS_CHOICES = [
        ('ACTIVE', 'Active'),
        ('TERMINATED', 'Terminated'),
        ('ABSCOND_TERMINATED', 'Absconded-Terminated'),
    ]
    employment_status = models.CharField(
        max_length=25,
        choices=EMPLOYMENT_STATUS_CHOICES,
        default='ACTIVE'
    )

    # ---- Account control ----
    is_locked = models.BooleanField(default=False)
    failed_login_attempts = models.PositiveIntegerField(default=0)
    force_password_reset = models.BooleanField(default=True)

    # ======================================================
    # SOFT DELETE (MANAGEMENT ONLY)
    # ======================================================

    is_deleted = models.BooleanField(
        default=False,
        help_text="Soft delete flag (Management only)"
    )

    deleted_at = models.DateTimeField(null=True, blank=True)

    deleted_by = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='deleted_employees'
    )

    # ---- Audit ----
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # ======================================================
    # HELPERS
    # ======================================================

    def soft_delete(self, by_employee=None):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.deleted_by = by_employee
        self.save(update_fields=['is_deleted', 'deleted_at', 'deleted_by'])

    def restore(self):
        self.is_deleted = False
        self.deleted_at = None
        self.deleted_by = None
        self.save(update_fields=['is_deleted', 'deleted_at', 'deleted_by'])

    def __str__(self):
        return f"{self.employee_name} ({self.employee_id})"

class EmployeeLogHistory(models.Model):
    """
    Event-based log history for Employee actions
    (read-only in admin)
    """

    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name='logs'
    )

    action = models.CharField(
        max_length=255,
        help_text="Description of the action performed"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.employee.employee_id} - {self.action}"
# Leave request raised by an employee
class LeaveRequest(models.Model):

    # employee who applied for leave
    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name='leave_requests'
    )

    # type of leave
    LEAVE_TYPE_CHOICES = [
        ('CASUAL', 'Casual Leave'),
        ('SICK', 'Sick Leave'),
        ('PERMISSION', 'Permission'),
       
    ]
    leave_type = models.CharField(
        max_length=20,
        choices=LEAVE_TYPE_CHOICES
    )

    # leave duration
    start_date = models.DateField()
    end_date = models.DateField()
    total_days = models.PositiveIntegerField()

    # reason for leave
    reason = models.TextField()

    # current status of the request
    STATUS_CHOICES = [
        ('SUBMITTED', 'Submitted'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('SENT_BACK', 'Sent Back'),
        ('CANCELLED', 'Cancelled'),
    ]
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='SUBMITTED'
    )

    # person who has to approve now
    current_approver = models.ForeignKey(
        Employee,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pending_leave_approvals'
    )

    # system fields
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.employee.employee_id} - {self.leave_type}"
# stores approval or rejection history for a leave request
class LeaveApprovalLog(models.Model):

    # related leave request
    leave_request = models.ForeignKey(
        LeaveRequest,
        on_delete=models.CASCADE,
        related_name='approval_logs'
    )

    # person who took action
    action_by = models.ForeignKey(
        Employee,
        on_delete=models.SET_NULL,
        null=True
    )

    # action taken
    ACTION_CHOICES = [
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('SENT_BACK', 'Sent Back'),
    ]
    action = models.CharField(
        max_length=20,
        choices=ACTION_CHOICES
    )

    # comments from approver
    remarks = models.TextField(blank=True)

    # when action was taken
    action_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.leave_request.id} - {self.action}"


class EmployeeSnapshot(models.Model):
    """
    Immutable snapshot of employee state changes.
    Used for audit & compliance.
    """

    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name="snapshots"
    )

    changed_by = models.ForeignKey(
        Employee,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="performed_snapshots",
        help_text="Employee who performed the action"
    )

    action = models.CharField(
        max_length=100,
        help_text="Type of action (PROFILE_UPDATE, ADMIN_EDIT, SOFT_DELETE, RESTORE)"
    )

    before_data = models.JSONField(
        help_text="Employee state before change"
    )

    after_data = models.JSONField(
        help_text="Employee state after change"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.employee.employee_id} | {self.action} | {self.created_at}"


class Task(models.Model):
    """
    Core Task model.
    Represents the current state of a task assigned by a reporting person
    to their direct report.
    """

    STATUS_ASSIGNED = "ASSIGNED"
    STATUS_IN_PROGRESS = "IN_PROGRESS"
    STATUS_BLOCKED = "BLOCKED"
    STATUS_COMPLETED = "COMPLETED"

    STATUS_CHOICES = [
        (STATUS_ASSIGNED, "Assigned"),
        (STATUS_IN_PROGRESS, "In Progress"),
        (STATUS_BLOCKED, "Blocked"),
        (STATUS_COMPLETED, "Completed"),
    ]

    PRIORITY_LOW = "LOW"
    PRIORITY_MEDIUM = "MEDIUM"
    PRIORITY_HIGH = "HIGH"

    PRIORITY_CHOICES = [
        (PRIORITY_LOW, "Low"),
        (PRIORITY_MEDIUM, "Medium"),
        (PRIORITY_HIGH, "High"),
    ]

    # --- RELATIONSHIPS ---
    assigned_by = models.ForeignKey(
        "Employee",
        on_delete=models.PROTECT,
        related_name="tasks_assigned"
    )

    assigned_to = models.ForeignKey(
        "Employee",
        on_delete=models.PROTECT,
        related_name="tasks_received"
    )

    # --- TASK DEFINITION (ASSIGNOR-OWNED) ---
    title = models.CharField(max_length=255)
    description = models.TextField()
    priority = models.CharField(
        max_length=10,
        choices=PRIORITY_CHOICES,
        default=PRIORITY_MEDIUM
    )
    due_date = models.DateTimeField()

    # --- EXECUTION STATE (ASSIGNEE-OWNED) ---
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_ASSIGNED
    )
    progress_percent = models.PositiveSmallIntegerField(default=0)

    # --- AUDIT ---
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} ({self.assigned_to.employee_id})"

    # =====================
    # DOMAIN RULE HELPERS
    # =====================

    def is_completed(self):
        return self.status == self.STATUS_COMPLETED

    def can_assignor_edit(self):
        """
        Assignor can edit task definition fields
        only if task is NOT completed.
        """
        return not self.is_completed()

    def can_assignee_update(self):
        """
        Assignee can update execution fields
        only if task is NOT completed.
        """
        return not self.is_completed()
class TaskUpdateLog(models.Model):
    """
    Append-only log for task updates.
    Mirrors LeaveApprovalLog behavior.
    """

    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name="update_logs"
    )

    updated_by = models.ForeignKey(
        "Employee",
        on_delete=models.PROTECT
    )

    status = models.CharField(
        max_length=20,
        choices=Task.STATUS_CHOICES
    )

    progress_percent = models.PositiveSmallIntegerField()
    comment = models.TextField(blank=True)

    updated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return f"{self.task.title} - {self.status} ({self.updated_at.date()})"
    