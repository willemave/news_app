"""
State machine for podcast processing pipeline.
Defines valid state transitions and provides validation logic.
"""

from typing import Dict, List
from app.models import PodcastStatus
import logging

logger = logging.getLogger(__name__)


class PodcastStateMachine:
    """State machine for podcast processing pipeline."""
    
    # Define valid state transitions
    VALID_TRANSITIONS: Dict[PodcastStatus, List[PodcastStatus]] = {
        PodcastStatus.new: [PodcastStatus.downloaded, PodcastStatus.failed],
        PodcastStatus.downloaded: [PodcastStatus.transcribed, PodcastStatus.failed],
        PodcastStatus.transcribed: [PodcastStatus.summarized, PodcastStatus.failed],
        PodcastStatus.summarized: [],  # Terminal state
        PodcastStatus.failed: [PodcastStatus.new]  # Allow retry from failed state
    }
    
    @classmethod
    def can_transition(cls, from_state: PodcastStatus, to_state: PodcastStatus) -> bool:
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
    def get_valid_next_states(cls, current_state: PodcastStatus) -> List[PodcastStatus]:
        """
        Get list of valid next states from current state.
        
        Args:
            current_state: Current podcast state
            
        Returns:
            List of valid next states
        """
        return cls.VALID_TRANSITIONS.get(current_state, [])
    
    @classmethod
    def is_terminal_state(cls, state: PodcastStatus) -> bool:
        """
        Check if a state is terminal (no further transitions possible).
        
        Args:
            state: State to check
            
        Returns:
            True if state is terminal, False otherwise
        """
        return len(cls.VALID_TRANSITIONS.get(state, [])) == 0
    
    @classmethod
    def get_next_processing_state(cls, current_state: PodcastStatus) -> PodcastStatus:
        """
        Get the next processing state in the normal pipeline flow.
        
        Args:
            current_state: Current podcast state
            
        Returns:
            Next processing state, or raises ValueError if no normal next state
        """
        if current_state == PodcastStatus.new:
            return PodcastStatus.downloaded
        elif current_state == PodcastStatus.downloaded:
            return PodcastStatus.transcribed
        elif current_state == PodcastStatus.transcribed:
            return PodcastStatus.summarized
        else:
            raise ValueError(f"No normal next state for {current_state}")
    
    @classmethod
    def validate_transition(cls, from_state: PodcastStatus, to_state: PodcastStatus) -> None:
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
    def get_worker_for_state(cls, state: PodcastStatus) -> str:
        """
        Get the worker type responsible for processing podcasts in the given state.
        
        Args:
            state: Podcast state
            
        Returns:
            Worker type constant
        """
        from app.constants import WORKER_DOWNLOADER, WORKER_TRANSCRIBER, WORKER_SUMMARIZER
        
        if state == PodcastStatus.new:
            return WORKER_DOWNLOADER
        elif state == PodcastStatus.downloaded:
            return WORKER_TRANSCRIBER
        elif state == PodcastStatus.transcribed:
            return WORKER_SUMMARIZER
        else:
            raise ValueError(f"No worker defined for state {state}")
    
    @classmethod
    def get_processing_order(cls) -> List[PodcastStatus]:
        """
        Get the normal processing order of states.
        
        Returns:
            List of states in processing order
        """
        return [
            PodcastStatus.new,
            PodcastStatus.downloaded,
            PodcastStatus.transcribed,
            PodcastStatus.summarized
        ]
    
    @classmethod
    def get_state_description(cls, state: PodcastStatus) -> str:
        """
        Get human-readable description of a state.
        
        Args:
            state: Podcast state
            
        Returns:
            Description string
        """
        descriptions = {
            PodcastStatus.new: "Newly discovered, ready for download",
            PodcastStatus.downloaded: "Audio file downloaded, ready for transcription",
            PodcastStatus.transcribed: "Transcribed to text, ready for summarization",
            PodcastStatus.summarized: "Fully processed with summary",
            PodcastStatus.failed: "Processing failed, may be retried"
        }
        return descriptions.get(state, f"Unknown state: {state}")


class StateTransitionValidator:
    """Validates and logs state transitions."""
    
    def __init__(self):
        self.state_machine = PodcastStateMachine()
    
    def validate_and_log_transition(self, podcast_id: int, from_state: PodcastStatus, 
                                  to_state: PodcastStatus, worker_id: str) -> bool:
        """
        Validate a state transition and log the result.
        
        Args:
            podcast_id: ID of the podcast
            from_state: Current state
            to_state: Desired new state
            worker_id: Worker attempting the transition
            
        Returns:
            True if transition is valid, False otherwise
        """
        try:
            self.state_machine.validate_transition(from_state, to_state)
            logger.info(f"Valid state transition for podcast {podcast_id}: "
                       f"{from_state} -> {to_state} by {worker_id}")
            return True
        except ValueError as e:
            logger.error(f"Invalid state transition for podcast {podcast_id}: "
                        f"{from_state} -> {to_state} by {worker_id}. Error: {e}")
            return False
    
    def get_transition_summary(self) -> Dict[str, List[str]]:
        """
        Get a summary of all valid transitions for documentation.
        
        Returns:
            Dictionary mapping states to their valid next states
        """
        summary = {}
        for state, next_states in PodcastStateMachine.VALID_TRANSITIONS.items():
            summary[state.value] = [s.value for s in next_states]
        return summary