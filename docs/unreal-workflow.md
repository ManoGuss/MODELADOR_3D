# Fluxo Unreal — planejamento

A fase atual não exporta GLB/FBX nem envia assets à Unreal.
Pipeline previsto: validar asset → preparar FBX/texturas/manifest → pacote → Bridge → APIs do Editor → validar importação.
Não criar `.uasset` manualmente nem converter VFX sem adaptador real.
