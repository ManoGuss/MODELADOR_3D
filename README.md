# FORGE — AI 3D Game Asset Studio

Fase 1 + pipeline de assets local: workspace 3D em português, projetos SQLite, diagnóstico real,
importação/validação GLB, jobs persistidos, manifest/ZIP e exportação FBX validada pelo Blender instalado.
Geração por IA e importação automática na Unreal ainda dependem de provider/checkpoint e plugin Bridge.
Não há modelos de demonstração nem resultados simulados.

## Executar no Windows

Requisitos: Python 3.12+, Node.js 22.12+ (validado com 24.19), pnpm 11 e navegador com WebGL2.
Os scripts também detectam os runtimes locais do Codex quando disponíveis.

```powershell
.\scripts\forge.ps1 install
.\scripts\forge.ps1 build
.\scripts\forge.ps1 run
```

Abra http://127.0.0.1:8765. Depois de instalar e compilar, `run` funciona offline.
Para desenvolvimento: `.\scripts\forge.ps1 dev`. Para testes: `.\scripts\forge.ps1 test`.
Diagnóstico sem abrir o navegador: `.\scripts\forge.ps1 diagnostics`.

## Usar

1. Na aba **Projeto**, informe um nome e crie seu projeto.
2. Arraste na viewport para orbitar; botão direito para pan; rolagem para zoom; **F** restaura a câmera inicial.
3. Arraste o cabeçalho FORGE e seu canto inferior direito para mover/redimensionar. Minimize, feche e reabra pelo botão FORGE.
4. Os controles à direita alternam grade, ambiente e informações. **Tab** alterna o modo limpo; **Esc** sai dele.
5. Câmera, nome e visibilidade do ambiente são salvos automaticamente após 1 segundo. A posição, tamanho e aba do painel são salvos no navegador.
6. **Diagnóstico** consulta CPU, RAM, GPU NVIDIA, Python, Blender no PATH e ComfyUI em loopback.

Os projetos ficam em `storage/forge.sqlite3`, com arquivos grandes reservados em `storage/projects/<uuid>/`.
Não existe exclusão destrutiva de projetos nesta fase. Faça backup de toda a pasta storage com o servidor parado.

Veja [setup](docs/setup.md), [arquitetura](docs/architecture.md), [API](docs/api.md),
[relatório da Fase 1](docs/phase-1.md) e [licenças](docs/licenses.md).
