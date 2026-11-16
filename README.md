# Noite dos 10 Niveis

Jogo de tiro 2D em Python feito com Pygame. O objetivo e sobreviver a 10 niveis eliminando zumbis cada vez mais fortes.

## Como rodar

```bash
pip install -r requirements.txt
python main.py
```

Para recriar os sprites recortados das imagens fornecidas em `assets/source_art`, rode:

```bash
python generate_assets.py
```

## Controles

- `WASD` ou setas: mover
- Mouse: mirar
- Clique esquerdo ou `Espaco`: atirar
- `1` a `5`: selecionar personagem no menu
- `Enter`: iniciar ou reiniciar
- `Esc`: voltar ao menu

## Recursos

- 5 personagens com atributos, uniformes e equipamentos de classe diferentes
- 10 niveis com progressao de vida, velocidade e quantidade de zumbis
- Boss especial no nivel 10
- Arma evolui a cada nivel, mudando dano, cadencia, velocidade e quantidade de tiros
- Personagens, tres tipos de zumbi, caixas e barreiras recortados das imagens fornecidas
- Cenario de pedras com areas de asfalto destruido, destrocos, capsulas e manchas de sangue
- Carro abandonado, sacos de areia e tambores com colisao no mapa
- Projeteis com rastro de fogo animado e particulas de impacto
- Zumbis com barra de vida, colisao e dano ao jogador
- Mapa grande com fundo de pedras, paredes, barreiras e caixas reais que bloqueiam jogador, zumbis e tiros
- Kits medicos espalhados pelo mapa para recuperar vida
- Arena grande com camera seguindo o personagem
- HUD com vida, nivel, abates, arma atual e dicas de controle

## Referencias usadas

- Pygame: https://www.pygame.org/
- Pygame Sprite/Collision concepts: https://www.pygame.org/docs/ref/sprite.html
- Referencia de design de arena shooter/top-down shooter: jogos como *Crimsonland*, *Alien Shooter* e *Vampire Survivors* para progressao de hordas, leitura visual e escalada de dificuldade.
