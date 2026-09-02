from django.contrib import admin, messages

from .models import ItemPalete, Movimentacao, Palete, Posicao, Produto, Torre
from .services import EstoqueError, expedir_palete


@admin.register(Torre)
class TorreAdmin(admin.ModelAdmin):
    list_display = ("codigo", "nome", "qtd_niveis", "qtd_vaos", "capacidade_total", "ativo")
    search_fields = ("codigo", "nome", "localizacao")
    list_filter = ("ativo",)
    actions = ["gerar_posicoes_action"]

    @admin.action(description="Gerar posições (nível x vão) para as torres selecionadas")
    def gerar_posicoes_action(self, request, queryset):
        total = 0
        for torre in queryset:
            total += torre.gerar_posicoes()
        self.message_user(request, f"{total} posição(ões) criada(s).", level=messages.SUCCESS)


@admin.register(Posicao)
class PosicaoAdmin(admin.ModelAdmin):
    list_display = ("codigo", "torre", "nivel", "vao", "setor_destino", "status", "palete_alocado")
    list_filter = ("torre", "setor_destino", "status", "nivel")
    search_fields = ("codigo",)
    autocomplete_fields = ("torre",)
    actions = ["sincronizar_status_action"]

    def palete_alocado(self, obj):
        palete = getattr(obj, "palete_atual", None)
        return palete.codigo if palete else "-"

    palete_alocado.short_description = "Palete"

    @admin.action(description="Sincronizar status das posições selecionadas")
    def sincronizar_status_action(self, request, queryset):
        atualizadas = 0

        for posicao in queryset:
            tem_palete = getattr(posicao, "palete_atual", None) is not None
            novo_status = posicao.status

            if tem_palete and posicao.status != Posicao.Status.OCUPADA:
                novo_status = Posicao.Status.OCUPADA
            elif not tem_palete and posicao.status == Posicao.Status.OCUPADA:
                novo_status = Posicao.Status.LIVRE

            if novo_status != posicao.status:
                posicao.status = novo_status
                posicao.save(update_fields=["status"])
                atualizadas += 1

        self.message_user(
            request,
            f"Sincronização concluída. {atualizadas} posição(ões) atualizada(s).",
            level=messages.SUCCESS,
        )


@admin.register(Produto)
class ProdutoAdmin(admin.ModelAdmin):
    list_display = ("sku", "descricao", "unidade", "saldo_estoque", "categoria", "ativo")
    search_fields = ("sku", "descricao")
    list_filter = ("ativo", "categoria")


class ItemPaleteInline(admin.TabularInline):
    model = ItemPalete
    extra = 1
    autocomplete_fields = ("produto",)


@admin.register(Palete)
class PaleteAdmin(admin.ModelAdmin):
    list_display = ("codigo", "setor", "posicao", "status", "data_entrada", "data_expedicao")
    list_filter = ("setor", "status")
    search_fields = ("codigo", "posicao__codigo")
    autocomplete_fields = ("posicao",)
    inlines = [ItemPaleteInline]
    actions = ["expedir_paletes_action"]

    @admin.action(description="Expedir (dar saída) nos paletes selecionados")
    def expedir_paletes_action(self, request, queryset):
        sucesso, erro = 0, 0
        for palete in queryset:
            try:
                expedir_palete(palete, usuario=request.user)
                sucesso += 1
            except EstoqueError as e:
                erro += 1
                self.message_user(request, str(e), level=messages.ERROR)
        if sucesso:
            self.message_user(request, f"{sucesso} palete(s) expedido(s).", level=messages.SUCCESS)


@admin.register(Movimentacao)
class MovimentacaoAdmin(admin.ModelAdmin):
    list_display = ("data_hora", "tipo", "palete", "posicao_origem", "posicao_destino", "usuario")
    list_filter = ("tipo",)
    search_fields = ("palete__codigo",)
    readonly_fields = [f.name for f in Movimentacao._meta.fields]

    def has_add_permission(self, request):
        # Movimentações só devem ser criadas pelas regras de negócio (services.py),
        # nunca manualmente, para preservar a integridade do histórico.
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
