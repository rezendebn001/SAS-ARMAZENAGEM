from collections import defaultdict

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render

from .models import Palete, Posicao, Produto, Torre
from .services import EstoqueError, alocar_palete, expedir_palete, transferir_palete


def mapa_estoque(request):
    torres = Torre.objects.filter(ativo=True).order_by('codigo')
    torre_id = request.GET.get('torre')
    busca = (request.GET.get('q') or '').strip()

    torre_selecionada = None
    if torre_id:
        torre_selecionada = torres.filter(pk=torre_id).first()
    if not torre_selecionada:
        torre_selecionada = torres.first()

    contexto = {
        'torres': torres,
        'torre_selecionada': torre_selecionada,
        'niveis': [],
        'vaos': [],
        'ocupadas': 0,
        'livres': 0,
        'bloqueadas': 0,
        'taxa_ocupacao': 0,
        'configuradas': 0,
        'nao_configuradas': 0,
        'busca': busca,
        'resultado_busca': {'paletes': [], 'posicoes': [], 'produtos': [], 'total': 0},
    }

    if not torre_selecionada:
        return render(request, 'estoque/mapa_estoque.html', contexto)

    posicoes = (
        Posicao.objects.filter(torre=torre_selecionada)
        .select_related('torre', 'palete_atual')
        .order_by('nivel', 'vao')
    )

    por_nivel = defaultdict(dict)
    ocupadas = livres = bloqueadas = 0

    for posicao in posicoes:
        tem_palete = getattr(posicao, 'palete_atual', None) is not None
        posicao.ocupacao_visual = Posicao.Status.OCUPADA if tem_palete else posicao.status

        if posicao.status == Posicao.Status.BLOQUEADA:
            bloqueadas += 1
        elif tem_palete:
            ocupadas += 1
        else:
            livres += 1
        por_nivel[posicao.nivel][posicao.vao] = posicao

    niveis = []
    for nivel in range(torre_selecionada.qtd_niveis, 0, -1):
        linha = []
        for vao in range(1, torre_selecionada.qtd_vaos + 1):
            linha.append(por_nivel.get(nivel, {}).get(vao))
        niveis.append({'numero': nivel, 'vaos': linha})

    capacidade = torre_selecionada.capacidade_total
    taxa = int((ocupadas / capacidade) * 100) if capacidade else 0
    configuradas = posicoes.count()
    nao_configuradas = max(capacidade - configuradas, 0)

    contexto.update(
        {
            'niveis': niveis,
            'vaos': list(range(1, torre_selecionada.qtd_vaos + 1)),
            'ocupadas': ocupadas,
            'livres': livres,
            'bloqueadas': bloqueadas,
            'taxa_ocupacao': taxa,
            'configuradas': configuradas,
            'nao_configuradas': nao_configuradas,
        }
    )

    if busca:
        paletes = (
            Palete.objects.select_related('posicao')
            .filter(
                Q(codigo__icontains=busca)
                | Q(posicao__codigo__icontains=busca)
                | Q(itens__produto__sku__icontains=busca)
                | Q(itens__produto__descricao__icontains=busca)
            )
            .distinct()
            .order_by('codigo')[:20]
        )
        posicoes_encontradas = (
            Posicao.objects.select_related('torre', 'palete_atual')
            .filter(codigo__icontains=busca)
            .order_by('torre__codigo', 'nivel', 'vao')[:20]
        )
        produtos = (
            Produto.objects.filter(Q(sku__icontains=busca) | Q(descricao__icontains=busca))
            .annotate(paletes_relacionados=Count('itens_palete__palete', distinct=True))
            .order_by('sku')[:20]
        )
        contexto['resultado_busca'] = {
            'paletes': paletes,
            'posicoes': posicoes_encontradas,
            'produtos': produtos,
            'total': len(paletes) + len(posicoes_encontradas) + len(produtos),
        }

    return render(request, 'estoque/mapa_estoque.html', contexto)


def operacoes_estoque(request):
    if request.method == 'POST':
        acao = request.POST.get('acao')
        observacao = (request.POST.get('observacao') or '').strip()

        try:
            if acao == 'entrada':
                palete = get_object_or_404(Palete, pk=request.POST.get('palete_id'))
                posicao = get_object_or_404(Posicao, pk=request.POST.get('posicao_id'))
                alocar_palete(palete, posicao, usuario=request.user, observacao=observacao)
                messages.success(request, f'Entrada registrada: palete {palete.codigo} em {posicao.codigo}.')

            elif acao == 'transferencia':
                palete = get_object_or_404(Palete, pk=request.POST.get('palete_id'))
                posicao = get_object_or_404(Posicao, pk=request.POST.get('posicao_id'))
                transferir_palete(palete, posicao, usuario=request.user, observacao=observacao)
                messages.success(request, f'Transferência registrada: palete {palete.codigo} para {posicao.codigo}.')

            elif acao == 'saida':
                palete = get_object_or_404(Palete, pk=request.POST.get('palete_id'))
                codigo = palete.codigo
                expedir_palete(palete, usuario=request.user, observacao=observacao)
                messages.success(request, f'Saída registrada: palete {codigo} expedido.')

            else:
                messages.error(request, 'Ação inválida.')

        except (EstoqueError, ValidationError) as e:
            messages.error(request, str(e))

        return redirect('estoque:operacoes_estoque')

    paletes_entrada = Palete.objects.filter(status=Palete.Status.ATIVO, posicao__isnull=True).order_by('codigo')
    paletes_transferencia = (
        Palete.objects.filter(status=Palete.Status.ATIVO, posicao__isnull=False)
        .select_related('posicao')
        .order_by('codigo')
    )
    posicoes_livres = (
        Posicao.objects.filter(status=Posicao.Status.LIVRE, palete_atual__isnull=True)
        .select_related('torre')
        .order_by('torre__codigo', 'nivel', 'vao')
    )

    contexto = {
        'paletes_entrada': paletes_entrada,
        'paletes_transferencia': paletes_transferencia,
        'paletes_saida': paletes_transferencia,
        'posicoes_livres': posicoes_livres,
    }
    return render(request, 'estoque/operacoes_estoque.html', contexto)
