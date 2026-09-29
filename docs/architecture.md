# Arquitetura — Fase 1

Browser → frontend React → API FastAPI → Database → SQLite/filesystem.

A viewport usa Three.js diretamente, isolada em um módulo lazy. OrbitControls controla câmera e pan.
Ela redesenha apenas em interação, mudança de tamanho ou configuração; geometrias, materiais e controles são liberados no unmount.
O cenário é apenas ambiente de trabalho e nunca é salvo como asset gerado.

`backend/main.py` contém os contratos HTTP e validação Pydantic; `database.py` controla transações e diretórios;
`diagnostics.py` consulta hardware e processos com timeout. Não há worker de IA nesta fase.
O banco usa WAL, schema v1 (`PRAGMA user_version=1`) e uma conexão por operação. SQL usa parâmetros.
Uma revisão monotônica impede que duas janelas sobrescrevam alterações sem perceber.

O servidor é iniciado em 127.0.0.1. Host e Origin são limitados, corpos JSON têm limite de 32 KiB,
IDs são UUIDs e nenhum caminho ou comando de shell é aceito pela API.
Diagnóstico ComfyUI usa uma URL loopback fixa, sem proxy nem redirects. Não há chamadas de inferência ou telemetria.
O modo local é obrigatório nesta versão, inclusive se FORGE_LOCAL_ONLY=false for definido.

Persistência: dados de projeto e câmera no SQLite; layout por navegador em localStorage.
Autosave tem debounce de 1s; antes de sair com mudanças pendentes o navegador alerta.
O WAL recupera transações já confirmadas; alterações ainda em debounce podem ser perdidas numa queda abrupta.

Próximas fases devem separar services/jobs/providers à medida que os fluxos reais forem implementados,
adicionando migrações e contratos sem expor modelos específicos ao frontend.
