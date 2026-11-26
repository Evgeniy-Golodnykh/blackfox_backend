from django.contrib import admin

from content.models import Article, ArticleContent, Video


class ArticleContentInline(admin.StackedInline):
    model = ArticleContent
    can_delete = True
    extra = 0
    max_num = 1


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ('title', 'section', 'has_body')
    search_fields = ('title', 'section')
    inlines = (ArticleContentInline,)

    @admin.display(boolean=True, description='текст в приложении')
    def has_body(self, obj):
        return hasattr(obj, 'content')


admin.site.register(Video)
