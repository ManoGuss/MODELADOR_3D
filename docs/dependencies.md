# Dependências

Versões exatas em `frontend/pnpm-lock.yaml` e `backend/requirements.lock.txt`.
O segundo lock inclui testes; `requirements.txt` descreve dependências diretas de produção.

| Dependência | Versão validada | Papel | Licença |
| --- | --- | --- | --- |
| React / React DOM | 19.3.0 | Interface | MIT |
| Three.js | 0.180.0 | WebGL local | MIT |
| TypeScript | 5.9.3 | Verificação de tipos | Apache-2.0 |
| Vite | 7.3.6 | Build/dev server | MIT |
| FastAPI | 0.135.1 | API local | MIT |
| Uvicorn | 0.41.0 | ASGI | BSD-3-Clause |
| psutil | 7.2.2 | RAM/CPU | BSD-3-Clause |
| pytest | 9.0.2 | Testes backend | MIT |
| httpx | 0.28.1 | Cliente de testes | BSD-3-Clause |

Todos operam localmente, sem chave, crédito ou assinatura. SQLite e hashlib vêm com Python.
APIs oficiais e licenças foram consultadas; compatibilidade foi validada por build e testes.
O registro automático inclui dependências transitivas e URLs dos metadados instalados.
Antes de distribuir um instalador, revisar todos os avisos e componentes transitivos, incluindo os runtimes.
Esta entrega não equivale a uma auditoria completa de vulnerabilidades ou cadeia de fornecimento.
