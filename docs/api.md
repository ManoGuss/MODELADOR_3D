# API v0.1

Mesmo host do frontend. Contrato OpenAPI em `/openapi.json`. Swagger/ReDoc desativados para não depender de CDN.

| Método | Rota | Resultado |
| --- | --- | --- |
| GET | /api/health | Saúde do banco, versão, local_only |
| GET | /api/projects | Lista real, vazia na primeira execução |
| POST | /api/projects | Cria com `{ "name": "Meu projeto" }`, retorna 201 |
| GET | /api/projects/{uuid} | Projeto, workspace e revision |
| PUT | /api/projects/{uuid} | Salva name, workspace, revision esperada |
| GET | /api/providers | Providers planejados, desabilitados |
| GET | /api/system | Hardware, runtimes, armazenamento |
| GET | /api/diagnostics | Mesmo diagnóstico |

Workspace: grid/environment/overlays booleanos; camera/target com três números finitos em metros.
`revision` começa em zero; PUT incrementa atomicamente. Conflito retorna 409; ausente 404;
dados inválidos 422; origem externa 403; corpo grande 413; mídia diferente de JSON 415.
JSON máximo de 32 KiB; nomes de 1–100 caracteres, sem controles. UUID gerado pelo servidor.
Não existem endpoints de geração, importação, upload ou exportação nesta fase.
