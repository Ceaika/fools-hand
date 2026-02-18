from src.core.game import Game


def main() -> None:
    game = Game()
    game.setup(num_players=2)
    game.play()


if __name__ == "__main__":
    main()