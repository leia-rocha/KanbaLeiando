# Contratos da API — KanbaLeiando

Prefixo `/api/v1`, JSON UTF-8. Em desenvolvimento, a especificacao OpenAPI
interativa fica em `/api/docs` e o JSON em `/api/openapi.json` (desativados em
producao). Erros seguem o formato uniforme da secao 14.2:

```json
{ "error": { "code": "version_conflict", "message": "...", "requestId": "req_..." } }
```

## Autenticacao

- Usuario comum e visitante tecnico: header `Authorization: Bearer <Firebase ID token>`.
- Admin: cookie de sessao (`kanba_admin_session`) + header `X-CSRF-Token` nas mutacoes.

## Grupos de rotas

| Grupo | Rotas |
| --- | --- |
| Config/saude | `GET /config`, `GET /healthz`, `GET /me` |
| Sessao comum | `POST /auth/activate`, `POST /auth/forgot-password` |
| Admin | `POST/DELETE /admin/session`; `GET/POST /admin/users`; `PATCH/DELETE /admin/users/{uid}`; `POST /admin/users/{uid}/password-reset`; `POST /admin/users/{uid}/welcome-resend`; `GET /admin/operations/{id}` |
| Kanbans | `GET/POST /boards`; `GET/PATCH/DELETE /boards/{boardId}`; `GET /boards/{boardId}/cards` |
| Colunas | `POST /boards/{boardId}/columns`; `PATCH/DELETE /boards/{boardId}/columns/{columnId}`; `POST /boards/{boardId}/columns/reorder` |
| Cards | `POST /boards/{boardId}/cards`; `GET/PATCH/DELETE /boards/{boardId}/cards/{cardId}`; `POST .../move`; `POST .../duplicate` |
| Modelos | `GET/POST /boards/{boardId}/templates`; `PATCH/DELETE /boards/{boardId}/templates/{templateId}` |
| Compartilhamento | `GET/POST /boards/{boardId}/members`; `DELETE /boards/{boardId}/members/{uid}`; `GET /boards/{boardId}/public-link`; `POST /boards/{boardId}/public-link/rotate`; `POST /boards/{boardId}/public-link/revoke` |
| Acesso publico | `POST /public/session`; `GET /public/boards/{boardId}`; `.../columns`; `.../cards` |
| Anexos | `POST /boards/{boardId}/uploads`; `POST /uploads/{uploadId}/complete`; `DELETE /uploads/{uploadId}`; `GET .../attachments/{id}/download`; `GET .../attachments/{id}/preview` |
| Auditoria/operacoes | `GET /boards/{boardId}/audit`; `GET /operations/{id}` (restrito) |
| Tarefas internas | `POST /internal/tasks/{kind}` (OIDC da fila) |

## Codigos de status (secao 14.2)

`400` entrada invalida · `401` sem identidade · `403` sem permissao · `404`
inexistente · `409` conflito de versao/coluna nao vazia/duplicidade · `413`
acima do limite · `422` validacao de regra · `429` rate limit · `500/503` falha
interna.
