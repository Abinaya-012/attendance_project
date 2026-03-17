from django.urls import path
from . import views

urlpatterns = [
    path('',                     views.dashboard,        name='dashboard'),
    path('register/',            views.register_student, name='register'),
    path('scan/',                views.scan_attendance,  name='scan'),
    path('api/mark-attendance/', views.mark_attendance,  name='mark_attendance'),
]