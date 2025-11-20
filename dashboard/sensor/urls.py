from django.urls import path

from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('getTemp/<int:cnt>', views.getTemp, name='getTemp'),
    path('getHumi/<int:cnt>', views.getHumi, name='getHumi'),
    path('getVib/<int:cnt>', views.getVib, name='getVib'),
    path('getProx/<int:cnt>', views.getProx, name='getProx'),

    path('setTemp', views.setTemp, name='setTemp'),
    path('setHumi', views.setHumi, name='setHumi'),
    path('setVib', views.setVib, name='setVib'),
    path('setProx', views.setProx, name='setProx'),
]
