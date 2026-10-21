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
 return {'nav_vehicles':Vehicle.objects.filter(owner=request.user),'is_admin':request.user.is_staff}

@login_required
def dashboard(request):
 ex=Expense.objects.filter(owner=request.user).select_related('vehicle')
 today=date.today();month_start=today.replace(day=1)
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
 upcoming=Reminder.objects.filter(owner=request.user,completed=False).select_related('vehicle')[:5]
 return render(request,'ledger/dashboard.html',{**base_context(request),'vehicle':vehicle,'vehicles':vehicles,'recent':ex[:7],'reminders':upcoming,'total':total,'fuel':totals['fuel'],'maintenance':totals['maintenance'],'other':total-totals['fuel']-totals['maintenance'],'monthly_json':json.dumps(monthly),'cats_json':json.dumps(cats),'expense_count':current.count()})

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
 category=request.GET.get('category','')
 if category in dict(Expense.TYPES):items=items.filter(category=category)
 return render(request,'ledger/expenses.html',{**base_context(request),'items':items[:300],'selected':category,'categories':Expense.TYPES})
@login_required
def expense_form(request,pk=None):
 obj=get_object_or_404(Expense,pk=pk,owner=request.user) if pk else None
 form=ExpenseForm(request.POST or None,request.FILES or None,instance=obj,user=request.user)
 if request.method=='POST' and form.is_valid():
  item=form.save(commit=False);item.owner=request.user;item.save()
  if item.odometer is not None and item.odometer>item.vehicle.odometer:
   item.vehicle.odometer=item.odometer;item.vehicle.save(update_fields=['odometer'])
  messages.success(request,'Expense saved successfully.');return redirect('expenses')
 return render(request,'ledger/form.html',{**base_context(request),'form':form,'heading':'Edit expense' if pk else 'Add expense / fuel','back':'expenses','expense_mode':True})
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

def manifest(request):return JsonResponse({'name':'AutoLedger – Car Cost Manager','short_name':'AutoLedger','start_url':'/','scope':'/','display':'standalone','background_color':'#090b0e','theme_color':'#0d0f12','icons':[{'src':'/static/icons/icon-192.png','sizes':'192x192','type':'image/png'},{'src':'/static/icons/icon-512.png','sizes':'512x512','type':'image/png'}]})
def service_worker(request):
 script="""const CACHE='autoledger-v1';const ASSETS=['/static/css/style.css','/static/js/app.js','/static/icons/icon-192.png'];self.addEventListener('install',e=>e.waitUntil(caches.open(CACHE).then(c=>c.addAll(ASSETS))));self.addEventListener('activate',e=>e.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k!==CACHE).map(k=>caches.delete(k))))));self.addEventListener('fetch',e=>{if(e.request.method!=='GET'||e.request.url.includes('/media/')||e.request.mode==='navigate')return;e.respondWith(caches.match(e.request).then(r=>r||fetch(e.request)))});"""
 return HttpResponse(script,content_type='text/javascript',headers={'Service-Worker-Allowed':'/'})
