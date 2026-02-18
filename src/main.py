from src.core.game import Game


def main() -> None:
    game = Game(seed=1)  # deterministic shuffle for early testing
    game.setup(num_players=2)
    game.play_single_attack_demo()


if __name__ == "__main__":
    main()
