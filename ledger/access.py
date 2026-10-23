"""Keep car assignments consistent across pages, forms, exports and photos."""
from django.db.models import Q

from .models import Expense, Reminder, Vehicle


def vehicles_for(user):
    if not user.is_authenticated:
        return Vehicle.objects.none()
    if user.is_staff:
        return Vehicle.objects.all()
    return Vehicle.objects.filter(Q(owner=user) | Q(driver=user))


def managed_vehicles_for(user):
    if user.is_staff:
        return Vehicle.objects.all()
    return Vehicle.objects.filter(owner=user)


def expenses_for(user):
    return Expense.objects.filter(vehicle__in=vehicles_for(user))


def reminders_for(user):
    return Reminder.objects.filter(vehicle__in=vehicles_for(user))
