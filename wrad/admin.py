from django.contrib import admin
from .models import Employee, EmployeeLogHistory
from .models import LeaveRequest, LeaveApprovalLog



# ==============================
# Log History Inline (Tab 3 base)
# ==============================
class EmployeeLogHistoryInline(admin.TabularInline):
    model = EmployeeLogHistory
    extra = 0
    can_delete = False
    readonly_fields = ('action', 'created_at')
    verbose_name = "Log Entry"
    verbose_name_plural = "Log History"


# ==============================
# Employee Admin
# ==============================
@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):

    list_display = (
        'employee_id',
        'employee_name',
        'department',
        'designation',
        'employment_status',
        'joining_date',
        'created_at',
    )

    list_filter = (
        'department',
        'designation',
        'employment_status',
    )

    search_fields = (
        'employee_id',
        'employee_name',
        'department',
        'designation',
    )

    ordering = ('employee_id',)
    list_per_page = 25

    # ==============================
    # SECTION GROUPING (Tabs later)
    # ==============================
    fieldsets = (
        ("Personal Information", {
            'fields': (
                'employee_name',
                'date_of_birth',
                'blood_group',
                'marital_status',
                'email_address',
                'contact_number',
                'emergency_contact_number',
                'residential_address',
                'permanent_address',
            )
        }),
        ("Official Information", {
            'fields': (
                'employee_id',
                'designation',
                'department',
                'client',
                'reporting_role',
                'reporting_person',
                'joining_date',
                'ending_date',
                'employment_status',
                'is_locked',
                'user',
            )
        }),
        ("System Information", {
            'fields': (
                'failed_login_attempts',
                'created_at',
                'updated_at',
            )
        }),
    )

    readonly_fields = (
        'failed_login_attempts',
        'created_at',
        'updated_at',
    )

    # ==============================
    # Log History (Tab 3)
    # ==============================
    inlines = [EmployeeLogHistoryInline]
# shows approval history inside leave request page
class LeaveApprovalLogInline(admin.TabularInline):
    model = LeaveApprovalLog
    extra = 0
    can_delete = False
    readonly_fields = (
        'action_by',
        'action',
        'remarks',
        'action_at',
    )
# admin view for leave requests
@admin.register(LeaveRequest)
class LeaveRequestAdmin(admin.ModelAdmin):

    list_display = (
        'id',
        'employee',
        'leave_type',
        'start_date',
        'end_date',
        'status',
        'current_approver',
        'created_at',
    )

    # filters shown on the right side
    list_filter = (
        'status',
        'leave_type',
        'start_date',
        'employee',
    )

    # search box
    search_fields = (
        'employee__employee_id',
        'employee__employee_name',
        'reason',
    )

    ordering = ('-created_at',)

    readonly_fields = (
        'created_at',
        'updated_at',
    )

    inlines = [LeaveApprovalLogInline]
