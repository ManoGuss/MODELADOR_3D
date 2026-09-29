# Relatório — Fase 1 Foundation

## IMPLEMENTADO

- Frontend React/TypeScript/Vite em pt-BR, API Python/FastAPI, SQLite WAL, storage filesystem.
- Projetos: criar, listar, abrir, renomear e salvar workspace com controle de revisão.
- Viewport Three.js real: câmera orbital, pan, zoom, restauração de foco na origem, iluminação, céu, nuvens e chão.
- Painel FORGE: arrastar, redimensionar, minimizar, fechar, reabrir; persistência local de layout e aba.
- Alternância de grade/ambiente/overlays; modo limpo com retorno explícito.
- Autosave com debounce e aviso antes de sair com alterações pendentes.
- Diagnóstico real de CPU, memória, GPU NVIDIA, driver, disco, Python, Blender no PATH e ComfyUI loopback.
- Hosts/origens restritos, validação de UUID e JSON, limite de corpo e SQL parametrizado.

## TESTADO

- TypeScript e build Vite de produção.
- 10 testes backend: persistência após reinício, conflito de revisão, diretórios, nomes, coordenadas, origens/hosts, corpo grande, contratos e diagnóstico real.
- 2 testes frontend: recuperação de estado inválido e reposicionamento após mudança de resolução.
- Navegador real: carregamento WebGL, backend conectado, abas, minimizar/expandir, criação e renomeação de projeto e recarga com projeto persistido.
- Scripts PowerShell build/test/run executados neste Windows.

## FUNCIONANDO

Frontend, backend, viewport, projetos, banco/storage e diagnóstico da Fase 1.
Nenhum modelo gerado ou fixture é apresentado como resultado real.

## PENDENTE

Fases 2–10: concept, inputs multimodais, jobs/workers, providers locais, modelos 3D,
seleção/gizmo de assets, materiais/UV/texturas, versões/variantes, rig/animação/timeline,
partículas/shaders/VFX, GLB/FBX/ZIP e Unreal Bridge.
Arquitetura de tradução de todas as strings para outros idiomas ainda pendente; UI atual é pt-BR.

## DEPENDÊNCIAS

React, Three.js, Vite, TypeScript, FastAPI, Uvicorn, psutil; pytest/httpx para testes.
Locks e inventário de pacotes incluídos. Nenhum serviço pago, chave API ou peso baixado.

## LICENÇAS

Dependências diretas MIT/BSD/Apache; detalhes, fontes oficiais e inventário em licenses.md.
Certifi (MPL-2.0, cliente de teste) sinalizado para revisão no empacotamento.
Licenciamento de pesos Hunyuan/FLUX não aprovado nesta fase; providers permanecem desabilitados.

## LIMITAÇÕES

- A entrega cobre a Fase 1; não é ainda o produto integral de produção das dez fases.
- Sem seleção/gizmo porque não há pipeline de assets nesta fase. F restaura a câmera da origem.
- Sem recuperação de mudanças que ainda não chegaram ao autosave, migração entre schemas futuros ou backup automatizado.
- Diagnóstico detecta driver NVIDIA, mas não certifica runtime CUDA/ROCm nem capacidade de inferência.
- Blender é procurado no PATH; ausência detectada não prova que não exista em outro diretório.
- Validação visual/manual não substitui uma suíte E2E completa de todos os gestos/resoluções.
- Aviso de tamanho do chunk Three.js (~500 kB minificado, ~125 kB gzip); carregamento já é lazy.
- Aviso de depreciação Starlette/httpx em testes; todos passam.
- API local de usuário único; não suporta hospedagem pública ou autorização multiusuário.

## PRÓXIMA FASE

Concept: implementar prompt/imagem/sketch, contrato ConceptProvider, fila/worker,
integração de inferência local compatível com os 8 GB de VRAM, validação e armazenamento de imagens reais.
