from django import forms
from .models import User,Vehicle,Expense,Reminder
from django.contrib.auth.forms import UserCreationForm

class StyledMixin:
 def apply(self):
  for f in self.fields.values():
   f.widget.attrs['class']='form-control'
   if isinstance(f.widget,forms.DateInput): f.widget.input_type='date'

class UserAddForm(StyledMixin,UserCreationForm):
 class Meta:
  model=User;fields=['username','first_name','last_name','email','password1','password2']
 def __init__(self,*args,**kwargs): super().__init__(*args,**kwargs);self.apply()

class VehicleForm(StyledMixin,forms.ModelForm):
 class Meta: model=Vehicle;fields=['name','make','model','year','plate','fuel_type','odometer','photo']
 def __init__(self,*a,**kw):super().__init__(*a,**kw);self.apply()

class ExpenseForm(StyledMixin,forms.ModelForm):
 class Meta:
  model=Expense
  fields=['vehicle','category','title','amount','date','odometer','liters','price_per_liter','fuel_type','station','receipt_photo','pump_photo','notes']
  widgets={'date':forms.DateInput(attrs={'type':'date'}),'notes':forms.Textarea(attrs={'rows':3})}
 def __init__(self,*a,user=None,**kw):
  super().__init__(*a,**kw)
  if user:self.fields['vehicle'].queryset=Vehicle.objects.filter(owner=user)
  self.fields['date'].initial=__import__('datetime').date.today
  self.apply()
 def clean(self):
  data=super().clean()
  if data.get('category')=='fuel':
   if not data.get('liters') or data['liters']<=0:self.add_error('liters','Enter a positive fuel quantity.')
  return data

class ReminderForm(StyledMixin,forms.ModelForm):
 class Meta:
  model=Reminder;fields=['vehicle','title','due_date','due_odometer','notes','completed']
  widgets={'due_date':forms.DateInput(attrs={'type':'date'}),'notes':forms.Textarea(attrs={'rows':3})}
 def __init__(self,*a,user=None,**kw):
  super().__init__(*a,**kw)
  if user:self.fields['vehicle'].queryset=Vehicle.objects.filter(owner=user)
  self.apply()
