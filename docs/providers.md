# Providers

Nenhum provider de inferência habilitado na Fase 1. FLUX.1-schnell e Hunyuan3D são apenas o planejamento exposto por `/api/providers`.
Nenhum prompt é enviado e nenhum resultado é fabricado. ComfyUI detectado não implica workflow/modelo instalado.

Fase 2: ConceptProvider, fila/worker, referência e sketch, validação e armazenamento do resultado real.
Antes de habilitar qualquer motor: verificar isLocal/isFree, necessidade de API key/créditos/assinatura,
licença da versão exata, uso comercial, redistribuição dos pesos, atribuição e restrições territoriais/de uso.
Licença incerta deve bloquear habilitação. Não há fallback pago.
RTX 2060 SUPER 8 GB detectada durante implementação; o perfil Economia de VRAM limita resolução a 512 px,
executa sequencialmente e descarrega modelos ao terminar. ComfyUI usa somente loopback e rotas oficiais.
Ele só fica `available` depois de checkpoint local e licença/versão registrados. Sem isso, nenhuma geração é criada.

Blender detectado em `D:\blender.exe`; a exportação FBX chama o executável em background e faz round trip.
UE 5.8.1 foi detectada em `D:\Unreal RUela\UE_5.8`; UE 5.7 também consta no launcher, mas nenhuma versão
tem Bridge compilado. O perfil UE5 usa FBX 2020.2; o perfil UE4 usa FBX 2018. UE 4.0–4.26 e futuras versões
ficam não verificadas até uma instalação correspondente passar o round trip.
