# Decisoes iniciais (DT) — como foram aplicadas

As DT da especificacao resolvem pontos operacionais e sao a configuracao inicial
proposta. Uma instrucao posterior da responsavel prevalece.

| DT | Decisao | Onde |
| --- | --- | --- |
| DT01 | Firestore nativo; FastAPI; React+TS+Vite | backend/, frontend/ |
| DT02 | Login e-mail/senha; cadastro so no /admin | routes/admin.py, auth |
| DT03 | Um dono por kanban; dono remove editor/link/exclui | services/sharing.py, boards.py |
| DT04 | E-mail nao cadastrado: orientacao, sem convite | services/sharing.grant_editor |
| DT05 | Link publico abre cards e anexos; sem dados privados | rules + routes/public.py |
| DT06 | Modelo guarda so estrutura | services/templates.py |
| DT07 | CRIACAO = DATA/HORA, nao visivel, imutavel tecnico | services/cards.creation_field |
| DT08 | Limite de 2 campos visiveis validado no backend | services/projection.py |
| DT09 | Duplicacao copia valores/arquivos, reinicia CRIACAO | services/cards.duplicate_card |
| DT10 | Modelos renomeaveis/excluiveis por editor | services/templates.py |
| DT11 | Fuso America/Sao_Paulo; regras de vencimento | utils/timeutils.py |
| DT12 | Busca por titulo sem acento/caixa; filtros | frontend BoardPage + utils/text.py |
| DT13 | Detalhe confirma no Salvar; arrastes persistem | CardDetail + move_card |
| DT14 | Exclusoes sem lixeira; limpeza por tarefa | services/operations.py |
| DT15 | Limite 20.000.000 bytes inclusivo | config.max_upload_bytes |
| DT16 | Ao menos uma coluna; INICIO renomeavel | services/boards.delete_column |
| DT17 | Leitor publico busca/filtra; minimiza so editor | rules + PublicBoardPage |
| DT18 | SMTP configuravel; Cloud Tasks para tarefas finitas | services/email.py, tasks.py |
