from django.urls import path
from django.contrib.auth import views as auth_views
from . import views, mobile_views
urlpatterns=[path('login/',auth_views.LoginView.as_view(template_name='registration/login.html'),name='login'),path('logout/',auth_views.LogoutView.as_view(),name='logout'),path('',views.dashboard,name='dashboard'),path('vehicles/',views.vehicles,name='vehicles'),path('vehicles/add/',views.vehicle_form,name='vehicle_add'),path('vehicles/<int:pk>/edit/',views.vehicle_form,name='vehicle_edit'),path('expenses/',views.expenses,name='expenses'),path('expenses/add/',views.expense_form,name='expense_add'),path('expenses/<int:pk>/edit/',views.expense_form,name='expense_edit'),path('expenses/<int:pk>/delete/',views.expense_delete,name='expense_delete'),path('reminders/',mobile_views.reminders,name='reminders'),path('reminders/add/',views.reminder_form,name='reminder_add'),path('reminders/<int:pk>/edit/',views.reminder_form,name='reminder_edit'),path('users/',views.users,name='users'),path('users/add/',views.user_add,name='user_add'),path('reports/',mobile_views.reports,name='reports'),path('reports/download/',views.export_csv,name='export_csv'),path('manifest.webmanifest',views.manifest,name='manifest'),path('sw.js',views.service_worker,name='service_worker')]

urlpatterns += [
 path('vehicles/<int:pk>/', mobile_views.vehicle_detail, name='vehicle_detail'),
 path('profile/', mobile_views.profile, name='profile'),
 path('profile/edit/', mobile_views.profile_edit, name='profile_edit'),
 path('profile/password/', mobile_views.password_change, name='password_change'),
 path('help/', mobile_views.help_page, name='help'),
 path('service-centers/', mobile_views.service_centers, name='service_centers'),
 path('reminders/<int:pk>/toggle/', mobile_views.reminder_toggle, name='reminder_toggle'),
]
