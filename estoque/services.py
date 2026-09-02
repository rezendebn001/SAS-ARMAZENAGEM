"""Regras de negócio do estoque: alocação, transferência e expedição de paletes.

Manter essa lógica centralizada aqui (fora das views/admin) facilita reutilizar
as mesmas regras em diferentes lugares (views web, comandos, API futura) sem
duplicar código nem esquecer de gravar o histórico de movimentação.
"""
from django.db import transaction
from django.utils import timezone

from .models import Movimentacao, Palete, Posicao


class EstoqueError(Exception):
    """Erro de regra de negócio do estoque (ex: posição ocupada)."""


def _validar_setor_destino(palete: Palete, posicao: Posicao):
    if posicao.setor_destino == Posicao.SetorDestino.BAC and palete.setor != Palete.Setor.BAC:
        raise EstoqueError(
            f"A posição {posicao.codigo} é exclusiva para BAC. "
            "Alocar apenas paletes do setor pós-vendas (BAC)."
        )


@transaction.atomic
def alocar_palete(palete: Palete, posicao: Posicao, usuario=None, observacao=""):
    """Aloca um palete (novo ou sem posição) em uma posição livre."""
    posicao = Posicao.objects.select_for_update().get(pk=posicao.pk)

    if posicao.status == Posicao.Status.BLOQUEADA:
        raise EstoqueError(f"A posição {posicao.codigo} está bloqueada.")

    if hasattr(posicao, "palete_atual") and posicao.palete_atual_id:
        raise EstoqueError(f"A posição {posicao.codigo} já está ocupada.")

    _validar_setor_destino(palete, posicao)

    if palete.posicao_id:
        raise EstoqueError(
            f"O palete {palete.codigo} já está alocado em {palete.posicao.codigo}. "
            "Use transferir_palete para movê-lo."
        )

    palete.posicao = posicao
    palete.status = Palete.Status.ATIVO
    palete.save(update_fields=["posicao", "status"])

    posicao.status = Posicao.Status.OCUPADA
    posicao.save(update_fields=["status"])

    Movimentacao.objects.create(
        palete=palete,
        tipo=Movimentacao.Tipo.ENTRADA,
        posicao_origem=None,
        posicao_destino=posicao,
        usuario=usuario,
        observacao=observacao,
    )
    return palete


@transaction.atomic
def transferir_palete(palete: Palete, nova_posicao: Posicao, usuario=None, observacao=""):
    """Move um palete já alocado para outra posição livre."""
    if not palete.posicao_id:
        raise EstoqueError(f"O palete {palete.codigo} não está alocado em nenhuma posição.")

    origem = Posicao.objects.select_for_update().get(pk=palete.posicao_id)
    destino = Posicao.objects.select_for_update().get(pk=nova_posicao.pk)

    if destino.pk == origem.pk:
        raise EstoqueError("A posição de destino é igual à posição atual do palete.")

    if destino.status == Posicao.Status.BLOQUEADA:
        raise EstoqueError(f"A posição {destino.codigo} está bloqueada.")

    if hasattr(destino, "palete_atual") and destino.palete_atual_id:
        raise EstoqueError(f"A posição {destino.codigo} já está ocupada.")

    _validar_setor_destino(palete, destino)

    palete.posicao = destino
    palete.save(update_fields=["posicao"])

    destino.status = Posicao.Status.OCUPADA
    destino.save(update_fields=["status"])

    origem.status = Posicao.Status.LIVRE
    origem.save(update_fields=["status"])

    Movimentacao.objects.create(
        palete=palete,
        tipo=Movimentacao.Tipo.TRANSFERENCIA,
        posicao_origem=origem,
        posicao_destino=destino,
        usuario=usuario,
        observacao=observacao,
    )
    return palete


@transaction.atomic
def expedir_palete(palete: Palete, usuario=None, observacao=""):
    """Expede (dá saída em) um palete, liberando sua posição."""
    if not palete.posicao_id:
        raise EstoqueError(f"O palete {palete.codigo} não está alocado em nenhuma posição.")

    origem = Posicao.objects.select_for_update().get(pk=palete.posicao_id)

    palete.status = Palete.Status.EXPEDIDO
    palete.posicao = None
    palete.data_expedicao = timezone.now()
    palete.save(update_fields=["status", "posicao", "data_expedicao"])

    origem.status = Posicao.Status.LIVRE
    origem.save(update_fields=["status"])

    Movimentacao.objects.create(
        palete=palete,
        tipo=Movimentacao.Tipo.SAIDA,
        posicao_origem=origem,
        posicao_destino=None,
        usuario=usuario,
        observacao=observacao,
    )
    return palete
