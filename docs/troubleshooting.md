# Solução de problemas

- **Backend desconectado:** execute run e abra 127.0.0.1:8765. O botão Reconectar tenta novamente sem dados falsos.
- **Porta ocupada:** encerre a instância anterior de run/dev; não mate processos desconhecidos.
- **WebGL indisponível:** habilite aceleração gráfica do navegador, atualize driver e recarregue. Erros ficam visíveis.
- **Projeto mudou em outra janela:** uma revisão mais recente existe no banco; reabra o aplicativo antes de editar. Não há merge automático.
- **Python/Node ausentes:** instale versões listadas em setup ou configure FORGE_PYTHON/FORGE_NODE.
- **Blender não detectado:** diagnóstico usa PATH, não confirma ausência no disco.
- **ComfyUI não detectado:** verifique se está ativo em 127.0.0.1:8188. Nenhum workflow é executado nesta fase.
- **GPU não detectada:** `nvidia-smi` pode faltar ou ter acesso negado. RAM/CPU permanecem disponíveis; CUDA/ROCm não são inferidos como operacionais.
- **Build com aviso de bundle:** Three.js é carregado sob demanda; o bundle da viewport está próximo de 500 kB antes de gzip.
- **Aviso Starlette/httpx:** os testes passam, mas a versão instalada avisa futura migração do cliente de testes.

Backup: pare o servidor e copie storage inteiro. Não copie apenas o SQLite enquanto WAL estiver ativo.
Não há recuperação de alterações ainda não salvas em caso de falha abrupta.
