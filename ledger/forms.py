from django import forms
from .models import User,Vehicle,Expense,Reminder
from django.contrib.auth.forms import UserCreationForm,AdminUserCreationForm
from django.db import connection
from django.utils import timezone
from django.db.models import Q
from .access import vehicles_for

class StyledMixin:
 def apply(self):
  for f in self.fields.values():
   f.widget.attrs['class']='form-control'
   if isinstance(f.widget,forms.DateInput): f.widget.input_type='date'

class UserAddForm(StyledMixin,UserCreationForm):
 vehicle=forms.ModelChoiceField(queryset=Vehicle.objects.none(),label='Assign car',help_text='Choose an unassigned car for this driver. Add a car first if the list is empty.')
 class Meta:
  model=User;fields=['username','first_name','last_name','email','password1','password2']
 def __init__(self,*args,**kwargs):
  super().__init__(*args,**kwargs)
  self.fields['vehicle'].queryset=Vehicle.objects.filter(driver__isnull=True)
  self.fields['username'].label='Phone number'
  self.apply()

class DriverAssignmentForm(StyledMixin,forms.Form):
 vehicles=forms.ModelMultipleChoiceField(queryset=Vehicle.objects.none(),required=False,label='Assigned cars',widget=forms.CheckboxSelectMultiple,help_text='Select cars for this driver. Clear a car to remove its assignment. Cars assigned to another driver can be reassigned from the car edit page.')
 def __init__(self,*args,driver,**kwargs):
  super().__init__(*args,**kwargs)
  self.fields['vehicles'].queryset=Vehicle.objects.filter(Q(driver__isnull=True)|Q(driver=driver))
  self.fields['vehicles'].initial=Vehicle.objects.filter(driver=driver)
  self.apply()

class DriverAdminCreationForm(AdminUserCreationForm):
 vehicle=forms.ModelChoiceField(queryset=Vehicle.objects.none(),required=False,label='Assign car',help_text='Choose an unassigned car for the new driver.')
 class Meta(AdminUserCreationForm.Meta):
  model=User
 def __init__(self,*args,**kwargs):
  super().__init__(*args,**kwargs)
  self.fields['vehicle'].queryset=Vehicle.objects.filter(driver__isnull=True)
 def clean_vehicle(self):
  vehicle=self.cleaned_data.get('vehicle')
  if vehicle:
   # Django admin wraps validation and saving in one transaction.
   cars=Vehicle.objects.select_for_update() if connection.in_atomic_block else Vehicle.objects
   vehicle=cars.get(pk=vehicle.pk)
   if vehicle.driver_id:raise forms.ValidationError('This car has already been assigned. Choose another car.')
  return vehicle
 def _save_m2m(self):
  super()._save_m2m()
  vehicle=self.cleaned_data.get('vehicle')
  if vehicle:
   vehicle.driver=self.instance
   vehicle.save(update_fields=['driver'])

class VehicleForm(StyledMixin,forms.ModelForm):
 class Meta: model=Vehicle;fields=['name','make','model','year','plate','fuel_type','odometer','photo']
 def __init__(self,*a,user=None,**kw):
  super().__init__(*a,**kw)
  if user and user.is_staff:
   self.fields['driver']=forms.ModelChoiceField(queryset=User.objects.filter(is_staff=False,is_active=True),required=False,label='Assigned driver',help_text='Choose a driver, or leave empty to make this car unassigned.',initial=self.instance.driver_id)
  self.apply()
 def save(self,commit=True):
  vehicle=super().save(commit=False)
  if 'driver' in self.fields:vehicle.driver=self.cleaned_data['driver']
  if commit:vehicle.save();self.save_m2m()
  return vehicle

class ExpenseForm(StyledMixin,forms.ModelForm):
 class Meta:
  model=Expense
  fields=['vehicle','category','title','amount','date','odometer','liters','price_per_liter','fuel_type','station','receipt_photo','pump_photo','notes']
  widgets={'date':forms.DateInput(attrs={'type':'date'}),'notes':forms.Textarea(attrs={'rows':3})}
 def __init__(self,*a,user=None,**kw):
  super().__init__(*a,**kw)
  self.fields['vehicle'].queryset=vehicles_for(user) if user else Vehicle.objects.none()
  fuel_choices=list(Vehicle._meta.get_field('fuel_type').choices)
  if self.instance.fuel_type and self.instance.fuel_type not in dict(fuel_choices):fuel_choices.append((self.instance.fuel_type,self.instance.fuel_type))
  self.fields['fuel_type']=forms.ChoiceField(choices=[('','Choose fuel type')]+fuel_choices,required=False,label='Fuel type')
  self.fields['date'].initial=timezone.localdate
  self.fields['amount'].label='Amount (BDT)'
  self.fields['liters'].label='Quantity (litres)'
  self.fields['price_per_liter'].label='Price per litre (BDT)'
  self.fields['station'].label='Station / service center'
  for name in ['receipt_photo','pump_photo']:
   self.fields[name].widget.attrs.update({'accept':'image/*','data-photo-input':name})
  self.apply()
 def clean(self):
  data=super().clean()
  if data.get('category')=='fuel':
   if not data.get('liters') or data['liters']<=0:self.add_error('liters','Enter a positive fuel quantity.')
  if data.get('price_per_liter') is not None and data['price_per_liter']<=0:self.add_error('price_per_liter','Enter a positive price per litre.')
  return data

class ProfileForm(StyledMixin,forms.ModelForm):
 class Meta:
  model=User
  fields=['username','first_name','last_name','email']
  labels={'username':'Phone number'}
 def __init__(self,*a,**kw):
  super().__init__(*a,**kw);self.apply()
  self.fields['username'].widget.attrs['autocomplete']='tel'

class ReminderForm(StyledMixin,forms.ModelForm):
 class Meta:
  model=Reminder;fields=['vehicle','title','due_date','due_odometer','notes','completed']
  widgets={'due_date':forms.DateInput(attrs={'type':'date'}),'notes':forms.Textarea(attrs={'rows':3})}
 def __init__(self,*a,user=None,**kw):
  super().__init__(*a,**kw)
  self.fields['vehicle'].queryset=vehicles_for(user) if user else Vehicle.objects.none()
  self.apply()
