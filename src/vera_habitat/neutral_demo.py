"""Deterministic no-device training-ground walkthrough."""
from .training_ground import NeutralTrainingGround, TrainingAction, render_ascii


def main() -> None:
    ground = NeutralTrainingGround()
    course = [("MOVE", 1.0, 0.0)] * 3  # third move is obstructed
    course += [("MOVE", 0.0, 1.0)] * 7  # detour north
    course += [("MOVE", 1.0, 0.0)] * 6  # east above the wall
    course += [("MOVE", 0.0, 1.0)]      # reach goal
    print("NEUTRAL TRAINING GROUND -- SIMULATION ONLY")
    print("Initial scene (V=avatar, G=goal, #=static obstacle):")
    print(render_ascii(ground.observe()))
    for kind, x, y in course:
        step = ground.step(TrainingAction(kind, x, y, duration_ms=1000))
        print(f"{step.index:02d} {step.disposition} "
              f"pos=({step.observation.avatar.x:.2f},"
              f"{step.observation.avatar.y:.2f}) reward={step.reward:.3f}")
    final = ground.observe()
    print("Final scene:")
    print(render_ascii(final))
    print(f"RESULT reached_goal={final.reached_goal} steps={final.steps_taken} "
          f"revision={final.scene.revision} simulation_only=True")


if __name__ == "__main__":
    main()
