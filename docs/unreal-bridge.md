# Unreal Bridge — protocolo preparado, plugin ainda não instalado

O backend já prepara manifest, hashes, nomes técnicos, pacotes ZIP e jobs. Nenhum listener Bridge, plugin C++ ou
integração de importação é fornecido ainda; `format=unreal` retorna 409 e não finge envio.
O futuro plugin será Editor-only e receberá pacotes autenticados em loopback, validando manifest, hash e paths.
UE4 usa perfil FBX 2018 e UE5 usa FBX 2020.2. UE 5.8.1 foi encontrada nesta máquina, mas só será marcada como
conectada depois de plugin compilado responder ao handshake local. Compilação e round trip precisam ser testados
em uma instalação Unreal real antes de anunciar suporte.
