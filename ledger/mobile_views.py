import calendar
import json
from datetime import date, timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.db.models import Sum, Count
from django.db.models.functions import TruncMonth
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import ProfileForm
from .models import Expense, Reminder, Vehicle
from .views import base_context


@login_required
def vehicle_detail(request, pk):
    vehicle = get_object_or_404(Vehicle, pk=pk, owner=request.user)
    expenses = Expense.objects.filter(owner=request.user, vehicle=vehicle)
    return render(request, 'ledger/vehicle_detail.html', {
        **base_context(request), 'vehicle': vehicle, 'mobile_title': vehicle.name,
        'back': 'vehicles', 'total': expenses.aggregate(v=Sum('amount'))['v'] or 0,
        'fuel': expenses.filter(category='fuel').aggregate(v=Sum('amount'))['v'] or 0,
        'liters': expenses.filter(category='fuel').aggregate(v=Sum('liters'))['v'] or 0,
        'recent': expenses[:5],
    })


@login_required
def profile(request):
    return render(request, 'ledger/profile.html', {
        **base_context(request), 'car_count': Vehicle.objects.filter(owner=request.user).count(),
        'expense_count': Expense.objects.filter(owner=request.user).count(),
    })


@login_required
def profile_edit(request):
    form = ProfileForm(request.POST if request.method == 'POST' else None, instance=request.user)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Your profile has been updated.')
        return redirect('profile')
    return render(request, 'ledger/form.html', {
        **base_context(request), 'form': form, 'heading': 'Edit Profile', 'back': 'profile',
        'save_label': 'Save Profile',
    })


@login_required
def password_change(request):
    form = PasswordChangeForm(request.user, request.POST if request.method == 'POST' else None)
    for field in form.fields.values():
        field.widget.attrs['class'] = 'form-control'
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        update_session_auth_hash(request, user)
        messages.success(request, 'Your password has been changed.')
        return redirect('profile')
    return render(request, 'ledger/form.html', {
        **base_context(request), 'form': form, 'heading': 'Change Password', 'back': 'profile',
        'save_label': 'Update Password',
    })


@login_required
def help_page(request):
    return render(request, 'ledger/help.html', {**base_context(request), 'back': 'profile'})


@login_required
def service_centers(request):
    centers = Expense.objects.filter(owner=request.user).exclude(station='').values('station').annotate(
        visits=Count('id'), total=Sum('amount')).order_by('station')
    return render(request, 'ledger/service_centers.html', {**base_context(request), 'centers': centers, 'back': 'profile'})


@login_required
def reminders(request):
    today = timezone.localdate()
    items = Reminder.objects.filter(owner=request.user).select_related('vehicle')
    vehicle_id = request.GET.get('vehicle', '')
    if vehicle_id.isdecimal() and len(vehicle_id) <= 18:
        items = items.filter(vehicle_id=vehicle_id)
    status = request.GET.get('status', '')
    if status in ['upcoming', 'completed']:
        items = items.filter(completed=status == 'completed')
    try:
        year, month = int(request.GET.get('year', today.year)), int(request.GET.get('month', today.month))
        first = date(year, month, 1)
        if not 1900 <= year <= 2100:
            raise ValueError
    except (ValueError, TypeError):
        first = today.replace(day=1)
    last = date(first.year, first.month, calendar.monthrange(first.year, first.month)[1])
    days_with_reminders = set(items.filter(due_date__gte=first, due_date__lte=last).values_list('due_date', flat=True))
    weeks = [[{'date': day, 'in_month': day.month == first.month, 'today': day == today,
               'has_reminder': day in days_with_reminders} for day in week]
             for week in calendar.Calendar(firstweekday=6).monthdatescalendar(first.year, first.month)]
    selected_day = None
    if request.GET.get('day'):
        try:
            selected_day = date.fromisoformat(request.GET['day'])
            items = items.filter(due_date=selected_day)
        except ValueError:
            pass
    previous = first - timedelta(days=1)
    following = last + timedelta(days=1)
    return render(request, 'ledger/reminders.html', {
        **base_context(request), 'items': items, 'calendar_month': first, 'calendar_weeks': weeks,
        'previous_month': previous, 'next_month': following, 'selected_day': selected_day,
        'calendar_view': request.GET.get('view', 'calendar') == 'calendar', 'selected_status': status,
        'selected_vehicle': vehicle_id,
    })


@login_required
@require_POST
def reminder_toggle(request, pk):
    item = get_object_or_404(Reminder, pk=pk, owner=request.user)
    item.completed = not item.completed
    item.save(update_fields=['completed'])
    messages.success(request, 'Reminder completed.' if item.completed else 'Reminder reopened.')
    return redirect('reminders')


@login_required
def reports(request):
    today = timezone.localdate()
    period = request.GET.get('period', 'month')
    start = today.replace(day=1)
    end = today
    if period == 'year':
        start = date(today.year, 1, 1)
    elif period == 'all':
        start = None
    elif period == 'custom':
        try:
            start, end = date.fromisoformat(request.GET['start']), date.fromisoformat(request.GET['end'])
            if start > end:
                raise ValueError
        except (KeyError, ValueError):
            start, end = today.replace(day=1), today
            messages.error(request, 'Choose a valid start and end date for your report.')
    elif period != 'month':
        period = 'month'
    items = Expense.objects.filter(owner=request.user, date__lte=end)
    if start:
        items = items.filter(date__gte=start)
    totals = list(items.values('category').annotate(total=Sum('amount')).order_by('-total'))
    grand = items.aggregate(s=Sum('amount'))['s'] or Decimal('0')
    category_names = dict(Expense.TYPES)
    colors = ['#0754ef', '#20b8d8', '#8075ed', '#6a9cdd', '#b49be6', '#55bda8', '#e0b86b']
    for index, row in enumerate(totals):
        row.update(label=category_names.get(row['category'], row['category']),
                   percent=round(float(row['total'] / grand * 100)) if grand else 0,
                   color=colors[index % len(colors)])
    trend = list(items.annotate(month=TruncMonth('date')).values('month').annotate(total=Sum('amount')).order_by('month'))
    monthly = [{'label': row['month'].strftime('%b %y'), 'value': float(row['total'])} for row in trend]
    return render(request, 'ledger/reports.html', {
        **base_context(request), 'totals': totals, 'count': items.count(), 'grand': grand,
        'period': period, 'start_date': start or today.replace(month=1, day=1), 'end_date': end,
        'monthly_json': json.dumps(monthly),
        'cats_json': json.dumps([{'label': row['label'], 'value': float(row['total'])} for row in totals]),
    })
