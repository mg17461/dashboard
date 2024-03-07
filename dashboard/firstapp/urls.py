from django.urls import path

from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('weather_stats/', views.weather_stats, name='weather_stats'),
    path('pv_tool/', views.pv_tool, name='pv_tool'),
    path('energy_sim/', views.energy_sim, name='energy_sim'),
    path('rainwater/', views.rainwater, name='rainwater'),
    path('reset_epw/', views.reset_epw_session, name='reset_epw'),

]