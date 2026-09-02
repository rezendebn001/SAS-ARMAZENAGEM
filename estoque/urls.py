from django.urls import path

from .views import mapa_estoque, operacoes_estoque

app_name = 'estoque'

urlpatterns = [
    path('', mapa_estoque, name='mapa_estoque'),
    path('mapa/', mapa_estoque, name='mapa_estoque_alt'),
    path('operacoes/', operacoes_estoque, name='operacoes_estoque'),
]
