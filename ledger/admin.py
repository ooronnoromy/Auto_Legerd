from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User,Vehicle,Expense,Reminder
from .forms import DriverAdminCreationForm
@admin.register(User)
class PhoneUserAdmin(UserAdmin):
 add_form=DriverAdminCreationForm
 add_fieldsets=UserAdmin.add_fieldsets+(('Driver car',{'fields':('vehicle',)}),)
 list_display=('username','first_name','last_name','is_staff','is_active')
 search_fields=('username','first_name','last_name')
@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
 list_display=('name','plate','owner','driver','odometer')
 list_filter=('fuel_type','driver')
 search_fields=('name','plate','driver__username','driver__first_name','driver__last_name')
@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):list_display=('date','owner','vehicle','category','amount');list_filter=('category','date')
@admin.register(Reminder)
class ReminderAdmin(admin.ModelAdmin):list_display=('title','vehicle','due_date','completed')
