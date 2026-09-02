from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.db.models import Sum


class Torre(models.Model):
    """Representa uma torre/estrutura porta-paletes do armazém."""

    codigo = models.CharField(
        max_length=20,
        unique=True,
        help_text="Código único da torre. Ex: T01",
    )
    nome = models.CharField(max_length=100, blank=True)
    localizacao = models.CharField(
        max_length=100,
        blank=True,
        help_text="Setor/corredor onde a torre está localizada (opcional).",
    )
    qtd_niveis = models.PositiveIntegerField(help_text="Quantidade de níveis (andares) da torre.")
    qtd_vaos = models.PositiveIntegerField(help_text="Quantidade de vãos (colunas) por nível.")
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Torre"
        verbose_name_plural = "Torres"
        ordering = ["codigo"]

    def __str__(self):
        return f"{self.codigo} - {self.nome}" if self.nome else self.codigo

    @property
    def capacidade_total(self):
        return self.qtd_niveis * self.qtd_vaos

    def gerar_posicoes(self):
        """Cria as posições (nível x vão) que ainda não existem para esta torre.

        Não remove nem altera posições já existentes (evita perder um palete
        alocado caso a torre seja redimensionada).
        """
        criadas = 0
        for nivel in range(1, self.qtd_niveis + 1):
            for vao in range(1, self.qtd_vaos + 1):
                _, created = Posicao.objects.get_or_create(
                    torre=self,
                    nivel=nivel,
                    vao=vao,
                    defaults={"codigo": f"{self.codigo}-N{nivel:02d}-V{vao:02d}"},
                )
                if created:
                    criadas += 1
        return criadas


class Posicao(models.Model):
    """Uma célula de armazenagem dentro de uma torre (nível x vão)."""

    class Status(models.TextChoices):
        LIVRE = "LIVRE", "Livre"
        OCUPADA = "OCUPADA", "Ocupada"
        BLOQUEADA = "BLOQUEADA", "Bloqueada"

    class SetorDestino(models.TextChoices):
        GERAL = "GERAL", "Geral"
        BAC = "BAC", "Pos-vendas (BAC)"

    torre = models.ForeignKey(Torre, on_delete=models.CASCADE, related_name="posicoes")
    nivel = models.PositiveIntegerField()
    vao = models.PositiveIntegerField()
    codigo = models.CharField(
        max_length=30,
        unique=True,
        help_text="Código do endereço. Ex: T01-N02-V03",
    )
    setor_destino = models.CharField(
        max_length=10,
        choices=SetorDestino.choices,
        default=SetorDestino.GERAL,
        help_text="Define se a posição é geral ou dedicada ao setor BAC.",
    )
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.LIVRE)
    observacao = models.CharField(max_length=200, blank=True)

    class Meta:
        verbose_name = "Posição"
        verbose_name_plural = "Posições"
        unique_together = ("torre", "nivel", "vao")
        ordering = ["torre__codigo", "nivel", "vao"]

    def __str__(self):
        return self.codigo

    def save(self, *args, **kwargs):
        if not self.codigo:
            self.codigo = f"{self.torre.codigo}-N{self.nivel:02d}-V{self.vao:02d}"
        super().save(*args, **kwargs)


class Produto(models.Model):
    """Cadastro de produtos armazenados."""

    class Unidade(models.TextChoices):
        UNIDADE = "UNIDADE", "UNIDADE"
        CAIXA = "CAIXA", "CAIXA"
        KG = "KG", "KG"

    sku = models.CharField(max_length=50, unique=True, verbose_name="SKU")
    descricao = models.CharField(max_length=200)
    unidade = models.CharField(
        max_length=10,
        choices=Unidade.choices,
        default=Unidade.UNIDADE,
        help_text="Selecione a unidade de medida.",
    )
    categoria = models.CharField(max_length=100, blank=True)
    saldo_estoque = models.PositiveIntegerField(
        default=0,
        help_text="Quantidade total cadastrada em estoque.",
    )
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Produto"
        verbose_name_plural = "Produtos"
        ordering = ["sku"]

    def __str__(self):
        return f"{self.sku} - {self.descricao}"

    def clean(self):
        super().clean()
        if not self.pk:
            return

        alocado = self.itens_palete.aggregate(total=Sum("quantidade")).get("total") or 0
        if self.saldo_estoque < alocado:
            raise ValidationError(
                {
                    "saldo_estoque": (
                        "O estoque total não pode ser menor que a quantidade já alocada em paletes "
                        f"({alocado})."
                    )
                }
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class Palete(models.Model):
    """Um palete físico armazenado (ou já expedido)."""

    class Status(models.TextChoices):
        ATIVO = "ATIVO", "Ativo"
        EXPEDIDO = "EXPEDIDO", "Expedido"

    class Setor(models.TextChoices):
        GERAL = "GERAL", "Geral"
        BAC = "BAC", "Pos-vendas (BAC)"

    codigo = models.CharField(max_length=50, unique=True, help_text="Identificador do palete.")
    setor = models.CharField(
        max_length=10,
        choices=Setor.choices,
        default=Setor.GERAL,
        help_text="Setor responsável pelo palete.",
    )
    posicao = models.OneToOneField(
        Posicao,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="palete_atual",
        help_text="Posição atual do palete. Vazio se estiver em trânsito/na doca.",
    )
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ATIVO)
    data_entrada = models.DateTimeField(auto_now_add=True)
    data_expedicao = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Palete"
        verbose_name_plural = "Paletes"
        ordering = ["-data_entrada"]

    def __str__(self):
        return self.codigo

    def clean(self):
        super().clean()
        if not self.posicao_id:
            return

        if self.posicao.status == Posicao.Status.BLOQUEADA:
            raise ValidationError(
                {
                    "posicao": f"A posição {self.posicao.codigo} está bloqueada e não pode receber paletes."
                }
            )

        if self.posicao.setor_destino == Posicao.SetorDestino.BAC and self.setor != Palete.Setor.BAC:
            raise ValidationError(
                {
                    "posicao": (
                        f"A posição {self.posicao.codigo} é exclusiva para pós-vendas (BAC). "
                        "Selecione um palete do setor BAC para usar esse vão."
                    )
                }
            )

    def save(self, *args, **kwargs):
        self.full_clean()

        with transaction.atomic():
            posicao_anterior_id = None
            if self.pk:
                anterior = Palete.objects.filter(pk=self.pk).values("posicao_id").first()
                if anterior:
                    posicao_anterior_id = anterior["posicao_id"]

            resultado = super().save(*args, **kwargs)

            ids_para_sincronizar = {posicao_anterior_id, self.posicao_id}
            ids_para_sincronizar.discard(None)
            for posicao_id in ids_para_sincronizar:
                posicao = Posicao.objects.select_for_update().get(pk=posicao_id)
                tem_palete = Posicao.objects.filter(pk=posicao_id, palete_atual__isnull=False).exists()

                if tem_palete and posicao.status != Posicao.Status.OCUPADA:
                    posicao.status = Posicao.Status.OCUPADA
                    posicao.save(update_fields=["status"])
                elif not tem_palete and posicao.status == Posicao.Status.OCUPADA:
                    posicao.status = Posicao.Status.LIVRE
                    posicao.save(update_fields=["status"])

            return resultado


class ItemPalete(models.Model):
    """Item (produto + quantidade) que compõe um palete."""

    palete = models.ForeignKey(Palete, on_delete=models.CASCADE, related_name="itens")
    produto = models.ForeignKey(Produto, on_delete=models.PROTECT, related_name="itens_palete")
    quantidade = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    lote = models.CharField(max_length=50, blank=True)
    validade = models.DateField(null=True, blank=True)

    class Meta:
        verbose_name = "Item do Palete"
        verbose_name_plural = "Itens do Palete"

    def __str__(self):
        return f"{self.produto.sku} x {self.quantidade} ({self.palete.codigo})"

    def clean(self):
        super().clean()
        if not self.produto_id or self.quantidade is None:
            return

        quantidade_outros = (
            ItemPalete.objects.filter(produto_id=self.produto_id)
            .exclude(pk=self.pk)
            .aggregate(total=Sum("quantidade"))
            .get("total")
            or 0
        )
        quantidade_total = quantidade_outros + self.quantidade

        if quantidade_total > self.produto.saldo_estoque:
            raise ValidationError(
                {
                    "quantidade": (
                        "A soma das quantidades em paletes não pode ser maior que o estoque cadastrado do produto "
                        f"({self.produto.saldo_estoque})."
                    )
                }
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class Movimentacao(models.Model):
    """Histórico de movimentações de paletes (entrada, transferência, saída)."""

    class Tipo(models.TextChoices):
        ENTRADA = "ENTRADA", "Entrada"
        TRANSFERENCIA = "TRANSFERENCIA", "Transferência"
        SAIDA = "SAIDA", "Saída"

    palete = models.ForeignKey(Palete, on_delete=models.CASCADE, related_name="movimentacoes")
    tipo = models.CharField(max_length=15, choices=Tipo.choices)
    posicao_origem = models.ForeignKey(
        Posicao, on_delete=models.SET_NULL, null=True, blank=True, related_name="movimentacoes_origem"
    )
    posicao_destino = models.ForeignKey(
        Posicao, on_delete=models.SET_NULL, null=True, blank=True, related_name="movimentacoes_destino"
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    data_hora = models.DateTimeField(auto_now_add=True)
    observacao = models.CharField(max_length=200, blank=True)

    class Meta:
        verbose_name = "Movimentação"
        verbose_name_plural = "Movimentações"
        ordering = ["-data_hora"]

    def __str__(self):
        return f"{self.tipo} - {self.palete.codigo} ({self.data_hora:%d/%m/%Y %H:%M})"
