from django.db import models
from django.contrib.auth.models import AbstractUser
from django.conf import settings
from django.core.validators import MinValueValidator,RegexValidator

class User(AbstractUser):
 username=models.CharField(max_length=20,unique=True,validators=[RegexValidator(r'^\+?[0-9]{10,15}$','Use a phone number with 10–15 digits (optionally starting with +).')],help_text='Phone number, e.g. 01712345678')
 email=models.EmailField(blank=True)
 def __str__(self): return f'{self.username} — {self.get_full_name() or "User"}'

class Vehicle(models.Model):
 owner=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name='vehicles')
 driver=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,related_name='assigned_vehicles',null=True,blank=True,limit_choices_to={'is_staff':False,'is_active':True})
 name=models.CharField(max_length=100)
 make=models.CharField(max_length=60,blank=True)
 model=models.CharField(max_length=60,blank=True)
 year=models.PositiveIntegerField(null=True,blank=True)
 plate=models.CharField(max_length=40)
 fuel_type=models.CharField(max_length=25,choices=[(v,v) for v in ['Petrol','Octane','Diesel','LPG','CNG','Electric','Hybrid','Other']],default='Petrol')
 odometer=models.PositiveIntegerField(default=0)
 photo=models.ImageField(upload_to='vehicles/',blank=True,null=True)
 created_at=models.DateTimeField(auto_now_add=True)
 class Meta: ordering=['-created_at']
 def __str__(self): return f'{self.name} ({self.plate})'

class Expense(models.Model):
 TYPES=[('fuel','Fuel'),('maintenance','Maintenance'),('parking','Parking'),('insurance','Insurance'),('toll','Toll'),('wash','Car Wash'),('other','Other')]
 owner=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name='expenses')
 vehicle=models.ForeignKey(Vehicle,on_delete=models.CASCADE,related_name='expenses')
 category=models.CharField(max_length=20,choices=TYPES)
 title=models.CharField(max_length=150)
 amount=models.DecimalField(max_digits=12,decimal_places=2,validators=[MinValueValidator(0.01)])
 date=models.DateField()
 odometer=models.PositiveIntegerField(null=True,blank=True)
 notes=models.TextField(blank=True)
 liters=models.DecimalField(max_digits=10,decimal_places=2,null=True,blank=True)
 price_per_liter=models.DecimalField(max_digits=10,decimal_places=2,null=True,blank=True)
 fuel_type=models.CharField(max_length=25,blank=True)
 station=models.CharField(max_length=120,blank=True)
 receipt_photo=models.ImageField(upload_to='receipts/',null=True,blank=True)
 pump_photo=models.ImageField(upload_to='pumps/',null=True,blank=True)
 created_at=models.DateTimeField(auto_now_add=True)
 class Meta: ordering=['-date','-created_at']
 def __str__(self): return f'{self.title}: {self.amount}'

class Reminder(models.Model):
 owner=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name='reminders')
 vehicle=models.ForeignKey(Vehicle,on_delete=models.CASCADE,related_name='reminders')
 title=models.CharField(max_length=150)
 due_date=models.DateField(null=True,blank=True)
 due_odometer=models.PositiveIntegerField(null=True,blank=True)
 notes=models.TextField(blank=True)
 completed=models.BooleanField(default=False)
 created_at=models.DateTimeField(auto_now_add=True)
 class Meta: ordering=['completed','due_date']
 def __str__(self): return self.title
