from django import forms
from .models import User,Vehicle,Expense,Reminder
from django.contrib.auth.forms import UserCreationForm
from django.utils import timezone

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
  if user:self.fields['vehicle'].queryset=Vehicle.objects.filter(owner=user)
  self.apply()
