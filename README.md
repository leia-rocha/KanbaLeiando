<p align="center">
  <img src="frontend/assets/logo.png" alt="KanbaLeiando" height="80" />
</p>

# KanbaLeiando

KanbaLeiando e uma aplicacao Kanban colaborativa em portugues, pensada para
poucos usuarios (1 a 3 em media, ate 10 simultaneos) com prioridade em custo
baixo. Roda como um unico container no Google Cloud Run com escala a zero: o
servico pode ficar sem instancias quando nao ha uso, com uma espera inicial
aceitavel no primeiro acesso apos ociosidade.

O frontend React e a API FastAPI sao servidos pelo mesmo dominio. A persistencia
e no Cloud Firestore, os anexos ficam em um bucket privado do Cloud Storage e a
identidade dos usuarios usa o Firebase Authentication.

## Funcionalidades

- Login por e-mail e senha, recuperacao e primeiro acesso por link seguro.
- Painel administrativo isolado (`/admin`) para provisionar e gerenciar contas.
- Kanbans com colunas reordenaveis e minimizaveis (estado compartilhado).
- Cards com titulo e campos personalizados: texto, link, anexo, data, data/hora
  e checklist. Ate dois campos visiveis no resumo do quadro, exibidos por
  inteiro.
- Prazos com destaque de atraso (texto + icone), calculado no fuso do kanban.
- Drag and drop com alternativa acessivel por menu e teclado.
- Modelos reutilizaveis por kanban e duplicacao independente de cards.
- Compartilhamento por e-mail (edicao) e link publico de leitura em tempo real.
- Auditoria de alteracoes com ator e data/hora.
- Busca por titulo e filtros por coluna, prazo e atraso (preferencias locais).
- Tema escuro, responsivo (desktop, tablet, celular), usando o logo do projeto.

## Limitacoes conhecidas

- A previa de DOC/DOCX/XLS/XLSX usa LibreOffice headless incluido na imagem; a
  primeira abertura pode retornar "em processamento" ate a conversao em cache
  ficar pronta. Imagens e PDF tem previa imediata; demais formatos ficam como
  download.
- Nao ha arquivamento, lixeira, movimentacao entre kanbans, comentarios,
  etiquetas, notificacoes de prazo nem cobranca (fora do escopo desta versao).
- Testes de Security Rules e e2e completos exigem o Firebase Emulator Suite
  (Node + Java) no ambiente.

## Tecnologias

- **Frontend**: React 18, TypeScript, Vite, React Router, dnd-kit, Firebase Web SDK.
- **Backend**: Python 3.11, FastAPI, Pydantic, Firebase Admin SDK, clientes
  oficiais do Google Cloud (Firestore, Storage, Tasks).
- **Infra**: Cloud Run, Cloud Firestore (modo nativo), Cloud Storage, Cloud
  Tasks, Secret Manager, Artifact Registry.

## Estrutura de pastas

```
KanbaLeiando/
├── backend/
│   ├── app/            # config, rotas, schemas, servicos de dominio, repositorios
│   ├── tests/          # testes unitarios de dominio e prazos
│   └── pyproject.toml
├── frontend/
│   ├── assets/logo.png # logo preservado, importado pelo build do Vite
│   ├── src/            # telas, componentes, auth, listeners Firestore
│   └── package.json
├── tests/e2e/          # testes de navegador (Playwright)
├── infra/              # scripts de provisionamento e deploy no Cloud Run
├── docs/               # architecture.md, api.md, decisions.md
├── firestore.rules     # leitura do cliente + proibicao de escrita direta
├── firestore.indexes.json
├── storage.rules
├── firebase.json       # Emulator Suite
├── Dockerfile          # build multi-stage (Node -> Python)
├── .env.example
└── README.md
```

## Pre-requisitos

- Node.js 20+ e npm (frontend).
- Python 3.11+ (backend).
- `gcloud` e `firebase` CLIs para emuladores e deploy.
- Docker para build/execucao da imagem.
- Para os emuladores: Java 11+ (exigido pelo Firebase Emulator Suite).

## Configuracao

1. Copie `.env.example` para `.env` na raiz e preencha os valores. Segredos
   (`ADMIN_PASSWORD`, `ADMIN_SESSION_SECRET`, `PUBLIC_LINK_SECRET`, SMTP) nunca
   sao versionados nem entram na imagem. Gere os segredos aleatorios com:

   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(48))"
   ```

2. Valores publicos do Firebase Web (`FIREBASE_WEB_API_KEY`,
   `FIREBASE_AUTH_DOMAIN`, `FIREBASE_WEB_APP_ID`, `FIREBASE_PROJECT_ID`) vem do
   console do Firebase (configuracao do app Web).

## Execucao local com emuladores

```bash
# 1) Emuladores Firebase (Auth, Firestore, Storage)
firebase emulators:start

# 2) Backend (em outro terminal), com as variaveis de emulador no .env
cd backend
python -m venv .venv && . .venv/Scripts/activate   # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8080

# 3) Frontend (em outro terminal)
cd frontend
npm install
npm run dev     # http://localhost:5173 (proxy /api -> :8080)
```

O primeiro administrador usa `ADMIN_USER`/`ADMIN_PASSWORD` do `.env`. Em
`/admin`, crie o primeiro usuario comum (nome + e-mail). O e-mail de boas-vindas
traz o link para definir a primeira senha; sem SMTP configurado, o estado fica
`pending_no_smtp` e o link pode ser obtido pelos logs do emulador de Auth.

## Como usar

- **Definir a primeira senha / recuperar acesso**: abra o link recebido por
  e-mail (pagina `/auth/action`), escolha a senha e confirme.
- **Criar um quadro**: em `/kanbans`, use "Novo kanban". Ele nasce com a coluna
  `INICIO`.
- **Campos e modelos**: abra o card (duplo clique ou lapis), adicione campos,
  marque ate dois como visiveis e, se quiser, marque "Prazo" em datas. Use
  "Utilizar como modelo" para salvar a estrutura.
- **Minimizar colunas**: a acao fica no cabecalho da coluna e e compartilhada.
- **Compartilhar**: o icone de compartilhamento concede edicao por e-mail
  cadastrado e gera o link publico de leitura.
- **Auditoria**: botao "Auditoria" na barra do quadro.

### Papeis

- **Dono**: tudo no quadro, mais remover editores, revogar link e excluir/renomear.
- **Editor**: cria/edita cards, campos, colunas, modelos e convida usuarios.
- **Leitor publico**: abre e filtra cards e ve anexos; nao escreve nem ve
  auditoria/modelos/membros.
- **Administrador**: gerencia contas em `/admin`; nao acessa quadros.

## Lint, testes e build

```bash
# Backend
cd backend
ruff check app
pytest                      # testes de dominio e prazos

# Frontend
cd frontend
npm run typecheck
npm run build               # gera frontend/dist

# e2e (app precisa estar servida em BASE_URL)
npx playwright install
BASE_URL=http://localhost:8080 npx playwright test
```

## Docker

```bash
docker build -t kanbaleiando:local .
docker run --rm -p 8080:8080 --env-file .env kanbaleiando:local
# App em http://localhost:8080 (SPA + API no mesmo dominio)
```

## Implantacao no Cloud Run

Os scripts em `infra/` parametrizam projeto, regiao, nomes de recursos e
segredos. Nenhum valor privado e inventado.

```bash
export PROJECT_ID=seu-projeto
export REGION=southamerica-east1

# 1) Provisiona conta de servico (minimo privilegio), bucket privado, fila e
#    orienta a criacao dos segredos no Secret Manager.
bash infra/setup-resources.sh

# 2) Crie os segredos no Secret Manager (ver saida do passo 1).

# 3) Build + deploy com escala a zero (min-instances=0, max-instances=2).
bash infra/deploy.sh
```

Depois do deploy, atualize `APP_BASE_URL` e `TASKS_AUDIENCE` com a URL do
servico. Publique as regras e indices do Firestore:

```bash
firebase deploy --only firestore:rules,firestore:indexes,storage --project PROJECT_ID
```

### Requisitos de faturamento e custos

O Cloud Storage for Firebase exige plano Blaze com faturamento associado, mesmo
havendo franquias sem custo. Escala a zero vale para o container; Firestore,
anexos, build, tarefas, segredos e e-mails podem gerar custo. Configure um
alerta de orcamento com valor ajustavel (um alerta nao bloqueia cobranca).

## Resolucao de problemas

- **Cold start lento**: primeira requisicao apos ociosidade mostra carregamento;
  evite disparar multiplas operacoes.
- **SMTP**: sem configuracao, boas-vindas/reset ficam `pending_no_smtp`; valide
  com um SMTP de teste antes de produzir.
- **Permissao de bucket**: confirme os papeis da conta de servico e
  `iam.serviceAccounts.signBlob` para URLs assinadas e custom tokens.
- **Previa indisponivel**: arquivo corrompido/protegido mostra aviso e mantem o
  download; a previa de Office pode levar alguns segundos na primeira abertura.

## Contribuicao e licenca

Repositorio privado da responsavel pelo projeto. Licenca ainda nao definida;
nenhuma licenca livre especifica e declarada sem decisao da responsavel.
