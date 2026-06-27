from django.urls import path

from . import views

app_name = 'library'

urlpatterns = [
    path('', views.index, name='index'),
    path('upload/', views.create_meme, name='create'),
    path('memes/<int:pk>/edit/', views.edit_meme, name='edit'),
    path('memes/<int:pk>/delete/', views.delete_meme, name='delete'),
    path('memes/<int:pk>/download/', views.download_meme, name='download'),
    path('api/memes/', views.meme_search_api, name='meme_search_api'),
    path('api/tags/', views.tag_search_api, name='tag_search_api'),
    path('thumbs/<int:pk>/', views.thumbnail, name='thumbnail'),
    path('i/<str:token>/<str:filename>', views.public_image, name='public_image'),
]
