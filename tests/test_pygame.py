import pygame
pygame.init()
screen = pygame.display.set_mode((400, 300))
pygame.display.set_caption("test")
screen.fill((255, 0, 0))
pygame.display.flip()
running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
pygame.quit()