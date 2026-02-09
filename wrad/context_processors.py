from .models import Employee
from .views import can_manage_tasks

def user_permissions(request):
    if not request.user.is_authenticated:
        return {}

    try:
        employee = Employee.objects.get(user=request.user, is_deleted=False)
    except Employee.DoesNotExist:
        return {}

    return {
        "can_manage_tasks": can_manage_tasks(employee),
        "employee": employee,
    }
