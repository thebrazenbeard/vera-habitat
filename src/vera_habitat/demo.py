from .model import ActionProposal, Entity, Position3
from .runtime import HabitatRuntime


def main() -> None:
    runtime = HabitatRuntime()
    runtime.spawn(
        Entity(
            entity_id="vera",
            kind="AVATAR",
            zone="home",
            position=Position3(0.0, 0.0, 0.0),
        )
    )
    receipt = runtime.propose(ActionProposal.move("vera", Position3(1.0, 0.0, 0.0)))
    print(receipt)
    print(runtime.snapshot())


if __name__ == "__main__":
    main()
