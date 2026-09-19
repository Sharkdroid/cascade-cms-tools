#!/usr/bin/env python3
"""Read an asset's active workflow, then advance it through
a named action.
"""

import os
import uuid
from typing import Any

from cascade_cms.cmstypes import (
    CascadeError,
    CascadeSuccess,
    IdentifierType,
    workflowInformation,
    workflowTransitionInformation,
)
from cascade_cms.wrapper import CascadeWrapperBase

# ----- Configuration -----
environment_variables: dict[str, str] = {
    "API_KEY": os.environ["CASCADE_API_KEY"],
    "CASCADE_URL": os.environ["CASCADE_URL"],
    "SERVER": os.environ.get("SERVER", "default"),
}
configuration_variables: dict[str, Any] = {
    "cache_name": "./cache/cache.sqlite",
    "allowed_codes": (200,),
    "allowed_methods": ("GET",),
}

TARGET: IdentifierType = IdentifierType(
    id=uuid.UUID("e868f539ac1001062cfa029c4c5df4d0"),
    type="page",
)
DESIRED_ACTION: str = "approve"


def build_transition(
    info: workflowInformation, action: dict[str, Any]
) -> workflowTransitionInformation:
    return workflowTransitionInformation(
        workflowId=info.workflow_info_id,
        actionIdentifier=action["action_identifier"],
        transitionComment="Advanced by automation.",
    )


def main() -> None:
    with CascadeWrapperBase(
        environment_variables, configuration_variables
    ) as cascade:
        cascade.operations.readWorkflowInformation(TARGET)

        try:
            infos = cascade.submit_requests(
                workflowInformation
            )
        except Exception as exc:
            print(f"Workflow read failed: {exc}")
            return

        transitions = []
        for info in infos:
            if isinstance(info, CascadeError):
                print(f"FAILED: {info.message}")
                continue
            # Only steps in the current position expose
            # usable actions.
            for step in info.ordered_steps:
                if step["label"] != info.current_step:
                    continue
                for action in step["actions"]:
                    if (
                        action["action_identifier"]
                        != DESIRED_ACTION
                    ):
                        continue
                    transitions.append(
                        build_transition(info, action)
                    )

        if not transitions:
            print(
                f"No '{DESIRED_ACTION}' action available "
                "at the current step."
            )
            return

        for payload in transitions:
            cascade.operations.performWorkflowTransition(
                TARGET, payload
            )

        try:
            results = cascade.submit_requests(
                CascadeSuccess
            )
        except Exception as exc:
            print(f"Transition failed: {exc}")
            return

        for result in results:
            if isinstance(result, CascadeError):
                print(f"FAILED: {result.message}")
            else:
                print("Workflow advanced.")


if __name__ == "__main__":
    main()
