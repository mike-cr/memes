from django.contrib import admin

from .models import Meme, Tag


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'created_at')
    search_fields = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Meme)
class MemeAdmin(admin.ModelAdmin):
    list_display = ('display_title', 'created_at', 'created_by', 'size')
    list_filter = ('created_at', 'tags')
    search_fields = ('title', 'tags__name')
    readonly_fields = ('public_id', 'created_at', 'updated_at')
    filter_horizontal = ('tags',)
