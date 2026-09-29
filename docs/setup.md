# Instalação Windows

Use Python 3.12+, Node 22.12+ e pnpm 11 no PATH. Python 3.12 e Node 24.19 foram usados nesta entrega.
Alternativamente, defina `FORGE_PYTHON` e `FORGE_NODE` para os executáveis completos.
Na ausência deles, o script procura o runtime Codex dentro do perfil do usuário.

Na raiz MODELADOR_3D, execute os comandos install, build e run descritos no README.
Install baixa pacotes pequenos dos registries PyPI/npm e cria `.venv` e `frontend/node_modules`.
Não baixa modelos, CUDA, Blender, ComfyUI ou Unreal e não altera o PATH global.
`pnpm-workspace.yaml` autoriza somente o script de build do esbuild.

`run` serve o frontend compilado e a API na porta 8765. Encerre com Ctrl+C.
`dev` inicia backend e Vite na porta 5173; o backend criado pelo script é encerrado ao sair.
Não execute run e dev juntos na mesma porta.
`test` executa pytest e testes Node. `build` faz typecheck e compilação Vite.

Configuração opcional antes de run: `$env:FORGE_STORAGE='D:\MeusProjetosForge'`.
O diretório é criado na inicialização. Arquivos `.env` não são lidos automaticamente.
O diagnóstico reconhece Blender se `blender.exe` estiver no PATH; não varre o disco todo.
ComfyUI é somente detectado em `127.0.0.1:8188`; detecção não significa provider habilitado.
