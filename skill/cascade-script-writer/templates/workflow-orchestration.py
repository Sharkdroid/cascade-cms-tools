#!/usr/bin/env python3
"""Read an asset's active workflow, then advance it through
a named action.
"""

import os
import uuid

from cascade_cms.cmstypes import (
    CascadeSuccess,
    IdentifierType,
    WorkflowAction,
    workflowInformation,
    workflowTransitionInformation,
)
from cascade_cms.wrapper import (
    CascadeWrapperBase,
    EnvironmentVars,
)

# ----- Configuration -----
environment_variables: EnvironmentVars = {
    "API_KEY": os.environ["CASCADE_API_KEY"],
    "CASCADE_URL": os.environ["CASCADE_URL"],
    "SERVER": os.environ.get("SERVER", "default"),
}

TARGET: IdentifierType = IdentifierType(
    id=uuid.UUID("e868f539ac1001062cfa029c4c5df4d0"),
    type="page",
)
DESIRED_ACTION: str = "approve"


def build_transition(
    info: workflowInformation, action: WorkflowAction
) -> workflowTransitionInformation:
    return workflowTransitionInformation(
        workflow_identifier=info.workflow_info_id,
        action_identifier=action.action_identifier,
        transition_comment="Advanced by automation.",
    )


def main() -> None:
    with CascadeWrapperBase(
        environment_variables
    ) as cascade:
        cascade.operations.readWorkflowInformation(TARGET)

        infos = cascade.submit_requests(workflowInformation)
        # A failed read does not stop the block; skip the
        # transitions so they never run on partial data.
        if infos.failed:
            return

        transitions = []
        for info in infos.success:
            # Only steps in the current position expose
            # usable actions.
            for step in info.ordered_steps:
                if step.label != info.current_step:
                    continue
                for action in step.actions:
                    if (
                        action.action_identifier
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

        results = cascade.submit_requests(CascadeSuccess)

        print(
            f"Advanced {len(results.success)} workflow(s)."
        )


if __name__ == "__main__":
    main()
