"""
State machine for link processing pipeline.
Defines valid state transitions and provides validation logic.
"""

from typing import Dict, List
from app.models import LinkStatus
import logging

logger = logging.getLogger(__name__)


class LinkStateMachine:
    """State machine for link processing pipeline."""
    
    # Define valid state transitions
    VALID_TRANSITIONS: Dict[LinkStatus, List[LinkStatus]] = {
        LinkStatus.new: [LinkStatus.processing, LinkStatus.failed],
        LinkStatus.processing: [LinkStatus.processed, LinkStatus.failed, LinkStatus.skipped],
        LinkStatus.processed: [],  # Terminal state
        LinkStatus.failed: [LinkStatus.new],  # Allow retry from failed state
        LinkStatus.skipped: []  # Terminal state
    }
    
    @classmethod
    def can_transition(cls, from_state: LinkStatus, to_state: LinkStatus) -> bool:
        """
        Check if a state transition is valid.
        
        Args:
            from_state: Current state
            to_state: Desired new state
            
        Returns:
            True if transition is valid, False otherwise
        """
        valid_next_states = cls.VALID_TRANSITIONS.get(from_state, [])
        return to_state in valid_next_states
    
    @classmethod
    def get_valid_next_states(cls, current_state: LinkStatus) -> List[LinkStatus]:
        """
        Get list of valid next states from current state.
        
        Args:
            current_state: Current link state
            
        Returns:
            List of valid next states
        """
        return cls.VALID_TRANSITIONS.get(current_state, [])
    
    @classmethod
    def is_terminal_state(cls, state: LinkStatus) -> bool:
        """
        Check if a state is terminal (no further transitions possible).
        
        Args:
            state: State to check
            
        Returns:
            True if state is terminal, False otherwise
        """
        return len(cls.VALID_TRANSITIONS.get(state, [])) == 0
    
    @classmethod
    def get_next_processing_state(cls, current_state: LinkStatus) -> LinkStatus:
        """
        Get the next processing state in the normal pipeline flow.
        
        Args:
            current_state: Current link state
            
        Returns:
            Next processing state, or raises ValueError if no normal next state
        """
        if current_state == LinkStatus.new:
            return LinkStatus.processing
        elif current_state == LinkStatus.processing:
            return LinkStatus.processed
        else:
            raise ValueError(f"No normal next state for {current_state}")
    
    @classmethod
    def validate_transition(cls, from_state: LinkStatus, to_state: LinkStatus) -> None:
        """
        Validate a state transition, raising an exception if invalid.
        
        Args:
            from_state: Current state
            to_state: Desired new state
            
        Raises:
            ValueError: If transition is invalid
        """
        if not cls.can_transition(from_state, to_state):
            valid_states = cls.get_valid_next_states(from_state)
            raise ValueError(
                f"Invalid state transition from {from_state} to {to_state}. "
                f"Valid next states: {valid_states}"
            )
    
    @classmethod
    def get_processing_order(cls) -> List[LinkStatus]:
        """
        Get the normal processing order of states.
        
        Returns:
            List of states in processing order
        """
        return [
            LinkStatus.new,
            LinkStatus.processing,
            LinkStatus.processed
        ]
    
    @classmethod
    def get_state_description(cls, state: LinkStatus) -> str:
        """
        Get human-readable description of a state.
        
        Args:
            state: Link state
            
        Returns:
            Description string
        """
        descriptions = {
            LinkStatus.new: "Newly discovered, ready for processing",
            LinkStatus.processing: "Currently being processed by a worker",
            LinkStatus.processed: "Successfully processed and article created",
            LinkStatus.failed: "Processing failed, may be retried",
            LinkStatus.skipped: "Skipped by LLM filtering"
        }
        return descriptions.get(state, f"Unknown state: {state}")


class StateTransitionValidator:
    """Validates and logs state transitions."""
    
    def __init__(self):
        self.state_machine = LinkStateMachine()
    
    def validate_and_log_transition(self, link_id: int, from_state: LinkStatus, 
                                  to_state: LinkStatus, worker_id: str) -> bool:
        """
        Validate a state transition and log the result.
        
        Args:
            link_id: ID of the link
            from_state: Current state
            to_state: Desired new state
            worker_id: Worker attempting the transition
            
        Returns:
            True if transition is valid, False otherwise
        """
        try:
            self.state_machine.validate_transition(from_state, to_state)
            logger.info(f"Valid state transition for link {link_id}: "
                       f"{from_state} -> {to_state} by {worker_id}")
            return True
        except ValueError as e:
            logger.error(f"Invalid state transition for link {link_id}: "
                        f"{from_state} -> {to_state} by {worker_id}. Error: {e}")
            return False
    
    def get_transition_summary(self) -> Dict[str, List[str]]:
        """
        Get a summary of all valid transitions for documentation.
        
        Returns:
            Dictionary mapping states to their valid next states
        """
        summary = {}
        for state, next_states in LinkStateMachine.VALID_TRANSITIONS.items():
            summary[state.value] = [s.value for s in next_states]
        return summary