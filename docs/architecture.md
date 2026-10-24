# Arquitetura do KanbaLeiando

Documento de decisoes tecnicas (RF e DT da especificacao). Registra o que foi
implementado e por que.

## Visao geral

Aplicacao Kanban colaborativa servida por um unico container no Cloud Run com
escala a zero. O frontend React/TypeScript/Vite e a API FastAPI sao servidos
pelo mesmo dominio. Persistencia em Cloud Firestore (modo nativo), anexos em
bucket privado do Cloud Storage, identidade em Firebase Authentication.

```
Navegador ──(SPA)── Cloud Run ──(API /api/v1)── FastAPI (Admin SDK)
    │                                               │
    │                                               ├─ Firestore (escrita de dominio)
    ├──(listeners Firestore)──────── Firestore ─────┤  (leitura em tempo real)
    │                                               ├─ Cloud Storage (URLs assinadas)
    └──(custom token p/ leitor publico)             └─ Cloud Tasks (tarefas finitas)
```

Toda escrita de dominio passa pela API, que valida identidade, estado do perfil
e vinculo com o quadro antes de gravar e registrar auditoria. O React recebe
atualizacoes por listeners do Firestore. Nao ha WebSocket/SSE mantido pela API,
permitindo escala a zero (RF39, T1/T2/T3).

## Autorizacao em duas camadas (RF38, secao 15.1)

1. **Security Rules** (`firestore.rules`): negam por padrao, liberam apenas
   LEITURA de `boards/**` para membros ativos ou leitores publicos com a claim
   `kind=public_view` e `shareVersion` vigente. Proibem toda escrita direta.
2. **Autorizacao da API** (`app/services/authorization.py`): como o Admin SDK
   ignora as Security Rules, cada servico confirma o token, o perfil ativo, o
   vinculo e que `boardId/columnId/cardId/fieldId/attachmentId` pertencem a mesma
   arvore (prevencao de troca de identificadores).

## Identidade e administracao (secao 3)

- Login comum por e-mail/senha no Firebase Auth. Perfil de aplicacao em
  `users/{uid}` com `status` (`pending_activation` → `active`). Uma identidade
  criada fora do provisionamento nao recebe acesso (RF02).
- `/admin` e isolado: sessao por cookie Secure/HttpOnly/SameSite assinada e
  vinculada a versao das credenciais de ambiente, com CSRF nas mutacoes e rate
  limit persistido no Firestore (RF07). A sessao administrativa nao acessa
  quadros (RF08).
- Primeiro acesso (RF03): admin cria identidade com senha aleatoria nao
  persistida; e-mail de boas-vindas com link de acao do Firebase; a rota
  `POST /auth/activate` aceita `pending_activation`, exige sign-in recente por
  `password` e promove a `active`. O cliente nao prova ativacao por UID/status.

## Dominio do quadro (secoes 5-7, 9, 11)

- **Colunas**: fractional indexing (`utils/sortkey.py`). Exclusao so com coluna
  vazia, revalidada em transacao; preserva a ultima coluna (RF14, DT16).
- **Cards/campos**: `contentVersion` e `positionVersion` separados — mover um
  card nao descarta edicao de texto concorrente (secao 11.3). O backend
  reconstroi `visibleFieldsSnapshot` e `dueFields` em transacao (secao 13.2).
- **Projecao/atraso**: ate 2 campos visiveis (RF20); atraso por qualquer prazo
  vencido, inclusive de campos nao visiveis; DATA vence no inicio do dia
  seguinte no fuso do kanban, DATA/HORA no instante (DT11). O cliente recalcula
  por temporizador sem gravar (RF30).
- **Modelos**: guardam so a estrutura (DT06), nomes unicos por kanban. O campo
  `CRIACAO` usa `semanticRole="creation"`, nao o nome (RF22).
- **Duplicacao**: novos IDs, copia de valores e arquivos no bucket, `CRIACAO`
  reiniciado; excluir o original nao quebra a copia (DT09).
- **Auditoria**: eventos imutaveis em `boardAudit/{boardId}/events`, gravados na
  transacao da mudanca quando cabe; sem binarios/tokens/URLs assinadas.

## Compartilhamento e link publico (secao 10)

- Concessao por UID; repeticao nao duplica nem reinicia `grantedAt`. E-mail nao
  cadastrado retorna orientacao sem criar convite (DT04).
- Link publico: token HMAC-SHA256 de `boardId+shareVersion` com
  `PUBLIC_LINK_SECRET`, base64url, comparado em tempo constante. Revogar/rotacionar
  incrementa `shareVersion`. `POST /public/session` emite Firebase custom token de
  visitante (`kind=public_view`). O frontend usa instancia Firebase separada com
  persistencia em memoria para nao substituir o login comum (secao 10.3).

## Anexos (secao 8)

- Upload direto ao bucket por URL assinada; a API confirma tamanho/geracao antes
  de marcar `ready`; rejeita e limpa acima de 20.000.000 bytes (DT15).
- Download/previa exigem nova autorizacao e URL assinada curta (5 min).
- Previa: imagens e PDF diretos; DOC/DOCX/XLS/XLSX convertidos por LibreOffice
  headless (presente na imagem), com cache por geracao/hash. Tipos arbitrarios
  ficam como download com `Content-Disposition: attachment` e `nosniff`.

## Exclusoes e tarefas duraveis (secao 12, RF36/RF37)

- Exclusao retira acesso imediatamente e agenda limpeza fisica por operacao
  duravel com cursor e lotes (`operations/{id}`), executada por Cloud Tasks
  (`POST /internal/tasks/{kind}`, OIDC da conta de servico).
- Exclusao de usuario transfere a propriedade ao editor com `grantedAt` mais
  antigo (desempate por UID) ou exclui o board se for o unico membro.

## Infraestrutura (secao 16)

- Imagem multi-stage: Node compila o SPA, Python serve API + estaticos e inclui
  LibreOffice. Processo sem root, SIGTERM gracioso, escuta `0.0.0.0:$PORT`.
- Cloud Run: `min-instances=0`, `max-instances=2`, 1 vCPU/1 GiB, concorrencia 10,
  timeout 120s. Conta de servico de minimo privilegio; bucket privado com UBLA e
  bloqueio publico; sem versionamento de objetos (politica de exclusao definitiva).

## Pendencias e limitacoes conhecidas

- A conversao pesada de Office retorna `processing` na primeira previa; o
  resultado em cache deve ser emitido por um conversor chamado sob demanda
  (hook em `attachments.preview_descriptor`/`internal/tasks`).
- Testes de Security Rules e e2e completos exigem o Emulator Suite e Node/Java
  instalados no ambiente de execucao.
```
