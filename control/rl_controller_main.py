import logging
from control.rl_controller import MultiAgentCoordinator

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--train", action="store_true", help="Train baseline models")
    args = parser.parse_args()

    if args.train:
        logging.basicConfig(level=logging.INFO)
        # Train baseline synthetic network: 4x4 grid intersections
        jids = [f"J{r}_{c}" for r in range(4) for c in range(4)]
        coord = MultiAgentCoordinator(intersection_ids=jids)
        coord.train_all(total_timesteps=20_000, n_envs=4) # Using 20,000 for a quick baseline retrain
        coord.save_all()
