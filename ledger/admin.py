from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User,Vehicle,Expense,Reminder
@admin.register(User)
class PhoneUserAdmin(UserAdmin):
 list_display=('username','first_name','last_name','is_staff','is_active')
 search_fields=('username','first_name','last_name')
@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):list_display=('name','plate','owner','odometer');list_filter=('fuel_type',)
@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):list_display=('date','owner','vehicle','category','amount');list_filter=('category','date')
@admin.register(Reminder)
class ReminderAdmin(admin.ModelAdmin):list_display=('title','vehicle','due_date','completed')
