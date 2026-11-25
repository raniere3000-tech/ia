# EP2.07 — Movimento e tipografia

Status: PARCIAL. Movimento 2D de camadas por keyframes e easing, legenda cinética e ênfase por palavra renderizados. Parallax como técnica com fixture dedicada, elementos 3D, infográficos, rastreamento de texto e política de zonas por rede permanecem abertos.

- Camadas aceitam até 12 posições tipadas e ordenadas, relativas ao início do efeito. Trajetórias fora do quadro são recusadas. O executor interpola posição linear ou suave.
- A legenda reutiliza o construtor ASS. Pulso e ênfase são opções explícitas da timeline v2. O fluxo manual conserva seu estilo e comportamento anteriores.
- `teste_efeitos_reais.py`: 16/16 em 19,077 s. A suite mede a posição em tempos diferentes, a diferença entre interpolação linear e suave e os pixels amarelos somente na palavra selecionada. O ASS contém a transformação temporal esperada.
- Reversão: desabilitar emissão de keyframes e ênfase em planos novos. Manter o leitor de revisões existentes.
- Próxima frente independente: EP2.08, direção artística sobre a biblioteca visual e B-roll já disponíveis.
