# SAS Armazenagem

Sistema web para controle de armazenagem de paletes em torres porta-paletes, com mapa visual do estoque e registro de movimentacoes (entrada, transferencia e saida).

## Funcionalidades principais

- Cadastro de torres com geracao automatica de posicoes (nivel x vao).
- Mapa de estoque por torre com status de cada posicao: `LIVRE`, `OCUPADA` ou `BLOQUEADA`.
- Cadastro de produtos com validacao de saldo total vs quantidade alocada em paletes.
- Cadastro de paletes e itens por palete (produto, quantidade, lote e validade).
- Operacoes de estoque:
  - Entrada de palete em posicao livre.
  - Transferencia de palete entre posicoes.
  - Saida (expedicao) com liberacao automatica da posicao.
- Historico de movimentacoes por palete, com usuario e observacao.
- Regra de setor BAC: posicoes BAC aceitam apenas paletes do setor BAC.

## Tecnologias

- Python
- Django (projeto `config`, app `estoque`)
- SQLite (`db.sqlite3`)
- Templates Django + arquivos estaticos em `static/`

## Estrutura do projeto

```text
.
|- config/            # Configuracoes do projeto Django
|- estoque/           # Regras de negocio, modelos, views e urls
|- static/            # CSS, JS e imagens
|- manage.py          # Comandos Django
|- start.bat          # Script de inicializacao no Windows
`- db.sqlite3         # Banco de dados local (desenvolvimento)
```

## Requisitos

- Python instalado (recomendado 3.10+)
- `pip`
- Windows (para usar `start.bat` diretamente)

## Como rodar o projeto

### 1) Criar ambiente virtual

```bash
python -m venv venv
```

### 2) Instalar dependencias

```bash
venv\Scripts\python.exe -m pip install --upgrade pip
venv\Scripts\python.exe -m pip install django
```

### 3) Aplicar migracoes

```bash
venv\Scripts\python.exe manage.py migrate
```

### 4) Iniciar servidor

Opcao A (recomendada no Windows):

```bash
start.bat
```

Opcao B (manual):

```bash
venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

Aplicacao: http://127.0.0.1:8000/  
Admin Django: http://127.0.0.1:8000/admin/

## Comandos uteis

```bash
# Criar superusuario
venv\Scripts\python.exe manage.py createsuperuser

# Rodar testes
venv\Scripts\python.exe manage.py test

# Gerar novas migracoes apos alterar modelos
venv\Scripts\python.exe manage.py makemigrations
venv\Scripts\python.exe manage.py migrate
```

## Fluxo operacional (resumo)

1. Cadastre torres e gere as posicoes.
2. Cadastre produtos e saldos.
3. Cadastre paletes e seus itens.
4. Realize entrada, transferencia e saida pela tela de operacoes.
5. Acompanhe ocupacao no mapa e historico de movimentacoes.

## Regras de negocio importantes

- Posicao bloqueada nao recebe palete.
- Posicao ocupada nao recebe outro palete.
- Transferencia exige posicao de origem e destino diferentes.
- Saida de palete libera automaticamente a posicao anterior.
- Quantidade total alocada em paletes nao pode ultrapassar o saldo do produto.
- Posicoes BAC sao exclusivas para paletes do setor BAC.

## Observacoes

- Este projeto esta configurado para desenvolvimento local (`DEBUG = True`).
- Antes de publicar em producao, ajuste seguranca, `ALLOWED_HOSTS`, banco e estrategia de arquivos estaticos.
