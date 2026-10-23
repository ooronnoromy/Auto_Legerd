from datetime import date,timedelta
from decimal import Decimal
from collections import defaultdict
import csv,json
from django.shortcuts import render,redirect,get_object_or_404
from django.contrib.auth.decorators import login_required,user_passes_test
from django.contrib import messages
from django.db import connection, DatabaseError
from django.db.models import Sum, Q
from django.http import HttpResponse,JsonResponse,FileResponse,Http404
from django.core.files.storage import default_storage
from django.views.decorators.cache import never_cache
from django.views.decorators.vary import vary_on_cookie
from django.views.decorators.http import require_GET
from django.views.decorators.http import require_POST
from django.utils import timezone
from .models import Vehicle,Expense,Reminder,User
from .forms import VehicleForm,ExpenseForm,ReminderForm,UserAddForm

def staff(user):return user.is_authenticated and user.is_staff

@never_cache
@require_GET
def healthcheck(request):
 try:
  with connection.cursor() as cursor:
   cursor.execute('SELECT 1')
   cursor.fetchone()
 except DatabaseError:
  return JsonResponse({'status':'unavailable'},status=503)
 return JsonResponse({'status':'ok'})

@login_required
@never_cache
@vary_on_cookie
@require_GET
def protected_media(request,filename):
 vehicles=Vehicle.objects.all()
 expenses=Expense.objects.all()
 if not request.user.is_staff:
  vehicles=vehicles.filter(owner=request.user)
  expenses=expenses.filter(owner=request.user)
 if not (vehicles.filter(photo=filename).exists() or expenses.filter(Q(receipt_photo=filename)|Q(pump_photo=filename)).exists()):
  raise Http404
 try:
  return FileResponse(default_storage.open(filename,'rb'))
 except (FileNotFoundError,ValueError):
  raise Http404

def base_context(request):
 name=request.resolver_match.url_name if request.resolver_match else ''
 active='cars' if name.startswith('vehicle') else 'add' if name=='expense_add' else 'history' if name.startswith('expense') else 'profile' if name in ['profile','profile_edit','password_change','help','service_centers'] else 'home' if name=='dashboard' else ''
 titles={'dashboard':'Home','vehicles':'My Cars','expenses':'Expense History','expense_add':'Add Expense','reminders':'Reminders','reports':'Analytics','profile':'Profile','profile_edit':'Edit Profile','password_change':'Change Password','help':'Help & Support','service_centers':'Service Centers'}
 hour=timezone.localtime().hour
 greeting='Good morning' if hour<12 else 'Good afternoon' if hour<18 else 'Good evening'
 return {'nav_vehicles':Vehicle.objects.filter(owner=request.user),'is_admin':request.user.is_staff,'active_nav':active,'mobile_title':titles.get(name,'Your Garage'),'greeting':greeting,'pending_reminder_count':Reminder.objects.filter(owner=request.user,completed=False).count()}

@login_required
def dashboard(request):
 ex=Expense.objects.filter(owner=request.user).select_related('vehicle')
 today=timezone.localdate();month_start=today.replace(day=1)
 current=ex.filter(date__gte=month_start,date__lte=today)
 totals={k:current.filter(category=k).aggregate(v=Sum('amount'))['v'] or Decimal('0') for k,_ in Expense.TYPES}
 total=sum(totals.values(),Decimal('0'))
 monthly=[]
 for i in range(5,-1,-1):
  year=today.year;month=today.month-i
  while month<=0:month+=12;year-=1
  while month>12:month-=12;year+=1
  first=date(year,month,1)
  next_first=date(year+1,1,1) if month==12 else date(year,month+1,1)
  monthly.append({'label':first.strftime('%b'),'value':float(ex.filter(date__gte=first,date__lt=next_first).aggregate(v=Sum('amount'))['v'] or 0)})
 cats=[{'label':label,'value':float(totals[key])} for key,label in Expense.TYPES if totals[key]]
 vehicles=Vehicle.objects.filter(owner=request.user)
 vehicle=vehicles.first()
 vehicle_expenses=ex.filter(vehicle=vehicle) if vehicle else ex.none()
 upcoming=Reminder.objects.filter(owner=request.user,completed=False).select_related('vehicle')[:5]
 return render(request,'ledger/dashboard.html',{**base_context(request),'vehicle':vehicle,'vehicles':vehicles,'vehicle_total':vehicle_expenses.aggregate(v=Sum('amount'))['v'] or 0,'last_fuel':vehicle_expenses.filter(category='fuel').first(),'last_service':vehicle_expenses.filter(category='maintenance').first(),'recent':ex[:7],'reminders':upcoming,'total':total,'fuel':totals['fuel'],'maintenance':totals['maintenance'],'other':total-totals['fuel']-totals['maintenance'],'monthly_json':json.dumps(monthly),'cats_json':json.dumps(cats),'expense_count':current.count()})

@login_required
def vehicles(request):return render(request,'ledger/vehicles.html',{**base_context(request),'items':Vehicle.objects.filter(owner=request.user)})
@login_required
def vehicle_form(request,pk=None):
 obj=get_object_or_404(Vehicle,pk=pk,owner=request.user) if pk else None
 form=VehicleForm(request.POST or None,request.FILES or None,instance=obj)
 if request.method=='POST' and form.is_valid():
  item=form.save(commit=False);item.owner=request.user;item.save();messages.success(request,'Vehicle saved.');return redirect('vehicles')
 return render(request,'ledger/form.html',{**base_context(request),'form':form,'heading':'Edit vehicle' if pk else 'Add vehicle','back':'vehicles'})
@login_required
def expenses(request):
 items=Expense.objects.filter(owner=request.user).select_related('vehicle')
 search_query=request.GET.get('q','').strip()[:150]
 if search_query:items=items.filter(Q(title__icontains=search_query)|Q(vehicle__name__icontains=search_query)|Q(station__icontains=search_query)|Q(notes__icontains=search_query))
 if request.GET.get('group')=='other':items=items.exclude(category__in=['fuel','maintenance'])
 category=request.GET.get('category','')
 if category in dict(Expense.TYPES):items=items.filter(category=category)
 vehicle_id=request.GET.get('vehicle','')
 if vehicle_id.isdecimal() and len(vehicle_id)<=18:items=items.filter(vehicle_id=vehicle_id)
 fuel_type=request.GET.get('fuel_type','')
 if fuel_type:items=items.filter(fuel_type=fuel_type)
 station=request.GET.get('station','')
 if station:items=items.filter(station=station)
 return render(request,'ledger/expenses.html',{**base_context(request),'items':items[:300],'search_query':search_query,'selected':category,'categories':Expense.TYPES,'selected_vehicle':vehicle_id,'selected_fuel':fuel_type,'fuel_types':['Petrol','Octane','Diesel','LPG','CNG','Electric'],'selected_station':station,'mobile_title':'Fuel History' if category=='fuel' else 'Maintenance History' if category=='maintenance' else 'Expense History'})
@login_required
def expense_form(request,pk=None):
 obj=get_object_or_404(Expense,pk=pk,owner=request.user) if pk else None
 initial={}
 if not obj:
  category=request.GET.get('category','fuel')
  if category in dict(Expense.TYPES):initial.update(category=category,title='Fuel refill' if category=='fuel' else 'Maintenance service' if category=='maintenance' else '')
  vehicle_id=request.GET.get('vehicle','')
  chosen_vehicle=Vehicle.objects.filter(owner=request.user,pk=vehicle_id).first() if vehicle_id.isdecimal() and len(vehicle_id)<=18 else Vehicle.objects.filter(owner=request.user).first() if not vehicle_id else None
  if chosen_vehicle:initial.update(vehicle=chosen_vehicle.pk,fuel_type=chosen_vehicle.fuel_type)
 form=ExpenseForm(request.POST if request.method=='POST' else None,request.FILES or None,instance=obj,user=request.user,initial=initial)
 if request.method=='POST' and form.is_valid():
  item=form.save(commit=False);item.owner=request.user;item.save()
  if item.odometer is not None and item.odometer>item.vehicle.odometer:
   item.vehicle.odometer=item.odometer;item.vehicle.save(update_fields=['odometer'])
  messages.success(request,'Expense saved successfully.');return redirect('expenses')
 return render(request,'ledger/form.html',{**base_context(request),'form':form,'heading':'Edit Expense' if pk else 'Add Expense','back':'expenses','expense_mode':True,'save_label':'Save Expense'})
@login_required
@require_POST
def expense_delete(request,pk):
 get_object_or_404(Expense,pk=pk,owner=request.user).delete();messages.success(request,'Expense deleted.');return redirect('expenses')
@login_required
def reminders(request):return render(request,'ledger/reminders.html',{**base_context(request),'items':Reminder.objects.filter(owner=request.user).select_related('vehicle')})
@login_required
def reminder_form(request,pk=None):
 obj=get_object_or_404(Reminder,pk=pk,owner=request.user) if pk else None
 form=ReminderForm(request.POST or None,instance=obj,user=request.user)
 if request.method=='POST' and form.is_valid():
  item=form.save(commit=False);item.owner=request.user;item.save();messages.success(request,'Reminder saved.');return redirect('reminders')
 return render(request,'ledger/form.html',{**base_context(request),'form':form,'heading':'Edit reminder' if pk else 'New service reminder','back':'reminders'})
@login_required
@user_passes_test(staff)
def users(request):return render(request,'ledger/users.html',{**base_context(request),'items':User.objects.all().order_by('-date_joined')})
@login_required
@user_passes_test(staff)
def user_add(request):
 form=UserAddForm(request.POST or None)
 if request.method=='POST' and form.is_valid():
  form.save();messages.success(request,'User created. They can log in using their phone number.');return redirect('users')
 return render(request,'ledger/form.html',{**base_context(request),'form':form,'heading':'Create phone-number user','back':'users'})
@login_required
def reports(request):
 items=Expense.objects.filter(owner=request.user)
 totals=items.values('category').annotate(total=Sum('amount')).order_by('-total')
 return render(request,'ledger/reports.html',{**base_context(request),'totals':totals,'count':items.count(),'grand':items.aggregate(s=Sum('amount'))['s'] or 0})
@login_required
def export_csv(request):
 response=HttpResponse(content_type='text/csv');response['Content-Disposition']='attachment; filename="autoledger_expenses.csv"'
 w=csv.writer(response);w.writerow(['Date','Vehicle','Category','Title','Amount BDT','Odometer KM','Liters','Fuel type','Station','Notes'])
 for e in Expense.objects.filter(owner=request.user).select_related('vehicle'):
  w.writerow([e.date,e.vehicle.name,e.get_category_display(),e.title,e.amount,e.odometer or '',e.liters or '',e.fuel_type,e.station,e.notes])
 return response

def manifest(request):return JsonResponse({'name':'AutoLedger – Car Cost Manager','short_name':'AutoLedger','start_url':'/','scope':'/','display':'standalone','background_color':'#f5f9ff','theme_color':'#f5f9ff','icons':[{'src':'/static/icons/icon-192.png','sizes':'192x192','type':'image/png'},{'src':'/static/icons/icon-512.png','sizes':'512x512','type':'image/png'}]})
def service_worker(request):
 from django.conf import settings
 script=(settings.BASE_DIR/'static'/'js'/'service-worker.js').read_text(encoding='utf-8')
 return HttpResponse(script,content_type='text/javascript',headers={'Service-Worker-Allowed':'/','Cache-Control':'no-cache'})
