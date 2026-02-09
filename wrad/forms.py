from django import forms
from django.contrib.auth.models import User
import re
from .models import Employee, LeaveRequest
from .models import Task, TaskUpdateLog


# ======================================================
# ADMIN: EMPLOYEE REGISTRATION
# ======================================================

class EmployeeRegistryForm(forms.ModelForm):
    """
    Admin-only form.
    Used to register an employee with all personal
    and official information.
    """

    class Meta:
        model = Employee
        exclude = [
            "id",
            "user",
            "employee_id",
            "failed_login_attempts",
            "is_locked",
            "is_deleted",
            "deleted_at",
            "deleted_by",
            "created_at",
            "updated_at",
        ]
        widgets = {
            # ===== PERSONAL =====
            "date_of_birth": forms.DateInput(
                attrs={
                    "type": "date",
                    # Prevent future DOBs (adjust year if needed)
                    "max": "2010-12-31",
                }
            ),

            # ===== OFFICIAL =====
            "joining_date": forms.DateInput(
                attrs={
                    "type": "date",
                }
            ),

            "ending_date": forms.DateInput(
                attrs={
                    "type": "date",
                }
            ),
        }


    def clean(self):
        cleaned_data = super().clean()

        designation = cleaned_data.get("designation")
        reporting_person = cleaned_data.get("reporting_person")

        if reporting_person and designation:
            seniority_order = {
                "ASSOCIATE": 1,
                "SENIOR_ASSOCIATE": 2,
                "TEAM_LEADER": 3,
                "MANAGER": 4,
                "SENIOR_MANAGER": 5,
                "VICE_PRESIDENT": 6,
                "PRESIDENT": 7,
                "CEO": 8,
            }

            if seniority_order.get(reporting_person.designation, 0) <= seniority_order.get(designation, 0):
                raise forms.ValidationError(
                    "Reporting person must be senior to the employee."
                )

        return cleaned_data


# ======================================================
# ADMIN: CREDENTIAL CREATION
# ======================================================

class PasswordCreationForm(forms.Form):
    employee_id = forms.CharField(max_length=20, label="Employee ID")
    password = forms.CharField(
        widget=forms.PasswordInput,
        min_length=8,
        max_length=16,
        label="Password"
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput,
        label="Confirm Password"
    )

    def clean_password(self):
        password = self.cleaned_data.get("password")

        if not re.search(r"[A-Z]", password):
            raise forms.ValidationError("Password must contain at least one uppercase letter.")

        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
            raise forms.ValidationError("Password must contain at least one special symbol.")

        return password

    def clean(self):
        cleaned_data = super().clean()

        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")
        employee_id = cleaned_data.get("employee_id")

        if password and confirm_password and password != confirm_password:
            self.add_error("confirm_password", "Passwords do not match.")

        if employee_id:
            try:
                employee = Employee.objects.get(employee_id=employee_id)
            except Employee.DoesNotExist:
                self.add_error("employee_id", "Invalid employee ID.")
                return cleaned_data

            if employee.user is not None:
                self.add_error("employee_id", "Login already exists for this employee.")

        return cleaned_data


# ======================================================
# ROLE-AWARE EMPLOYEE SELF UPDATE (CORE CHANGE)
# ======================================================

class EmployeeSelfUpdateForm(forms.ModelForm):
    """
    Role-aware update form.
    Fields are dynamically disabled based on designation.
    """

    class Meta:
        model = Employee
        fields = [
            "contact_number",
            "emergency_contact_number",
            "residential_address",
            "permanent_address",
            "client",
            "department",
            "designation",
        ]

    def __init__(self, *args, **kwargs):
        self.current_employee = kwargs.pop("current_employee", None)
        super().__init__(*args, **kwargs)

        if not self.current_employee:
            return

        role = self.current_employee.designation

        # Base editable fields
        allowed_fields = {
    "ASSOCIATE": [
        "contact_number",
        "emergency_contact_number",
    ],
    "SENIOR_ASSOCIATE": [
        "contact_number",
        "emergency_contact_number",
    ],
    "TEAM_LEADER": [
        "contact_number",
        "emergency_contact_number",
        "residential_address",
        "permanent_address",
    ],
    "MANAGER": [
        "contact_number",
        "emergency_contact_number",
        "residential_address",
        "permanent_address",
        "client",
        "department",
    ],
    "SENIOR_MANAGER": [
        "contact_number",
        "emergency_contact_number",
        "residential_address",
        "permanent_address",
        "client",
        "department",
    ],
    "VICE_PRESIDENT": [
        "contact_number",
        "emergency_contact_number",
        "residential_address",
        "permanent_address",
        "client",
        "department",
    ],
    "PRESIDENT": [
        "contact_number",
        "emergency_contact_number",
        "residential_address",
        "permanent_address",
        "client",
        "department",
    ],
    "CEO": [
        "contact_number",
        "emergency_contact_number",
        "residential_address",
        "permanent_address",
        "client",
        "department",
    ],
}


        editable = allowed_fields.get(role, [])

        for field_name in self.fields:
            if field_name not in editable:
                self.fields[field_name].disabled = True
    def clean(self):
        cleaned_data = super().clean()

        # Safety: no context → no edits
        if not self.current_employee:
            return cleaned_data

        role = self.current_employee.designation

        # Management: full access
        if role in ["VICE_PRESIDENT", "PRESIDENT", "CEO"]:
            return cleaned_data

        allowed_fields = {
    "ASSOCIATE": ["contact_number", "emergency_contact_number"],
    "SENIOR_ASSOCIATE": ["contact_number", "emergency_contact_number"],
    "TEAM_LEADER": [
        "contact_number",
        "emergency_contact_number",
        "residential_address",
        "permanent_address",
    ],
    "MANAGER": [
        "contact_number",
        "emergency_contact_number",
        "residential_address",
        "permanent_address",
        "client",
        "department",
    ],
    "SENIOR_MANAGER": [
        "contact_number",
        "emergency_contact_number",
        "residential_address",
        "permanent_address",
        "client",
        "department",
    ],
}


        permitted = allowed_fields.get(role, [])

        # Strip unauthorized fields from POST
        for field in list(cleaned_data.keys()):
            if field not in permitted:
                cleaned_data.pop(field, None)

        return cleaned_data



# ======================================================
# LEAVE APPLICATION
# ======================================================

class LeaveApplyForm(forms.ModelForm):
    class Meta:
        model = LeaveRequest
        fields = [
            "leave_type",
            "start_date",
            "end_date",
            "reason",
        ]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
            "reason": forms.Textarea(attrs={"rows": 3}),
        }

    def clean(self):
        cleaned_data = super().clean()
        start = cleaned_data.get("start_date")
        end = cleaned_data.get("end_date")

        if start and end and end < start:
            raise forms.ValidationError("End date cannot be earlier than start date.")

        return cleaned_data


# ======================================================
# FORCE PASSWORD RESET
# ======================================================

class ForcePasswordResetForm(forms.Form):
    new_password = forms.CharField(
        widget=forms.PasswordInput,
        min_length=8,
        max_length=16,
        label="New Password"
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput,
        label="Confirm New Password"
    )

    def clean_new_password(self):
        password = self.cleaned_data.get("new_password")

        if not re.search(r"[A-Z]", password):
            raise forms.ValidationError("Password must contain at least one uppercase letter.")

        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
            raise forms.ValidationError("Password must contain at least one special symbol.")

        return password

    def clean(self):
        cleaned_data = super().clean()

        if cleaned_data.get("new_password") != cleaned_data.get("confirm_password"):
            raise forms.ValidationError("Passwords do not match.")

        return cleaned_data


# ======================================================
# CREDENTIAL PREVIEW CONFIRMATION
# ======================================================

class CredentialPreviewConfirmForm(forms.Form):
    confirm = forms.BooleanField(
        required=True,
        label="I confirm the above details are correct"
    )
class TaskCreateForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = [
            "assigned_to",
            "title",
            "description",
            "priority",
            "due_date",
        ]
        widgets = {
            "due_date": forms.DateTimeInput(
                attrs={
                    "type": "datetime-local"
                }
            )
        }

    def __init__(self, *args, **kwargs):
        self.assignor = kwargs.pop("assignor", None)
        super().__init__(*args, **kwargs)

        if self.assignor:
            # ONLY direct reportees should appear
            self.fields["assigned_to"].queryset = Employee.objects.filter(
                reporting_person=self.assignor,
                is_deleted=False
            )

        self.fields["title"].widget.attrs.update({
            "placeholder": "Enter task title"
        })
        self.fields["description"].widget.attrs.update({
            "placeholder": "Describe the task clearly"
        })

class TaskUpdateForm(forms.Form):
    """
    Form used by assignee to update task progress and status.
    """

    status = forms.ChoiceField(choices=Task.STATUS_CHOICES)
    progress_percent = forms.IntegerField(
        min_value=0,
        max_value=100
    )
    comment = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            "rows": 3,
            "placeholder": "Describe progress, blockers, or updates"
        })
    )

    def __init__(self, *args, **kwargs):
        self.task = kwargs.pop("task", None)
        self.employee = kwargs.pop("employee", None)
        super().__init__(*args, **kwargs)

    def clean(self):
        """
        Cross-field validation:
        - Only assignee can update
        - No updates if task is completed
        - Progress rules
        """
        cleaned_data = super().clean()

        if not self.task or not self.employee:
            raise forms.ValidationError("Invalid task context.")

        if self.task.assigned_to != self.employee:
            raise forms.ValidationError("You are not allowed to update this task.")

        if self.task.is_completed():
            raise forms.ValidationError("Completed tasks cannot be updated.")

        status = cleaned_data.get("status")
        progress = cleaned_data.get("progress_percent")

        # Enforce progress rules
        if status == Task.STATUS_COMPLETED and progress < 100:
            raise forms.ValidationError(
                "Progress must be 100% to mark task as completed."
            )

        return cleaned_data

    def save(self):
        """
        Apply update:
        - Update Task
        - Create TaskUpdateLog
        """
        status = self.cleaned_data["status"]
        progress = self.cleaned_data["progress_percent"]
        comment = self.cleaned_data["comment"]

        # Update task current state
        self.task.status = status
        self.task.progress_percent = progress
        self.task.save(update_fields=["status", "progress_percent", "updated_at"])

        # Create append-only log
        TaskUpdateLog.objects.create(
            task=self.task,
            updated_by=self.employee,
            status=status,
            progress_percent=progress,
            comment=comment
        )

        return self.task
