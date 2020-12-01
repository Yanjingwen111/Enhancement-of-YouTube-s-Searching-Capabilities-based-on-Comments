from django.urls import path
from . import views
from search.views import result

urlpatterns = [
    path('', views.index, name='index'),
    path('result/', result, name='result'),
]