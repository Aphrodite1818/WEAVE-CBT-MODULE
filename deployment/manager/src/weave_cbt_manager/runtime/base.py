"""Base contract for WEAVE CBT runtime providers"""



from __future__ import annotations 

from abc import ABC , abstractmethod
from dataclasses import dataclass
from typing import Sequence

from sqlalchemy import True_

@dataclass(frozen = True , slots = True)
class RuntimeCommandResult:
    """Result returned after executing a command inside a runtime"""


    return_code : int
    stdout : str
    stderr : str

    @property
    def succeeded(self) -> bool:
        return self.return_code == 0

@dataclass(frozen = True , slots = True)
class RuntimePreparationResult:
    """Result of preparing the host for a runtime provider"""

    reboot_required : bool = False

class RuntimeProvider(ABC):
    """
    Base interface for the environment in which WEAVE CBT runs
    The Manager core should depend on this interface rather than knowing 
    whether the runtime is implemented using:

    -WSL2 on Windows
    -the native Linux host
    -a lightweight Linux VM on macOS


    Docker management is intentionally NOT part of this interface.
    Docker runs inside the runtime and will be handled separately by the 
    Docker service
    """


    @property
    @abstractmethod
    def name(self)->str:
        """
        Return a human-readable runtime provider name

        Examples:
            Windows WSL2
            Native Linux
            macOS Linux VM
        """



    @abstractmethod
    def is_available(self)->bool:
        """
        Return whether the host currently has the underlying capability
        required by this runtime provider

        Examples:
        Windows:
            WSL2 is available


        Linux:
            The native Linux environment is available

        macOS:
            The required virtualization capability is available
        """



    @abstractmethod
    def is_installed(self)->bool:
        """
        Return whether the WEAVE-managed runtime environment exists

        Examples:

        Windows:
            The dedicated WEAVE CBT WSL distribution exists

        Linux:
            The native runtime is already available

        macOS:
            The dedicated WEAVE CBT Linux VM exists
        """



    @abstractmethod
    def is_running(self)->bool:
        """Return whether the runtime environment is currently running"""


    @abstractmethod
    def install(self) -> None:
        """
        Provision the runtime environment.

        This method may modify the host machine

        It should only prepare the runtime itself. Docker Engine installation 
        and WEAVE CBT deployment belong to separate layers
        """

    @abstractmethod
    def start(self) -> None:
        """Start the runtime environment if it is not already running."""

    @abstractmethod
    def stop(self) -> None:
        """Stop the runtime environment if it is running."""

    @abstractmethod
    def execute(
        self,
        command: Sequence[str],
        *,
        timeout: float | None = None,
    ) -> RuntimeCommandResult:
        """
        Execute a command inside the runtime environment.

        The caller provides command arguments separately instead of passing
        a shell command string.

        Example:

            runtime.execute(
                ["docker", "compose", "ps"],
                timeout=30,
            )

        On Windows, the Windows WSL provider may internally translate this to:

            wsl.exe -d WeaveCBT -- docker compose ps

        On Linux, the native provider may execute:

            docker compose ps

        The caller does not need to know which implementation is being used.
        """


    @abstractmethod
    def prepare(self) -> None:
        """
        Prepare the host so this runtime provider can operate.

        This may modify the host

        Examples:
            Windows:
                Enable/install WSL2 and required Windows features.

            Linux:
                Usually no action is necessary
            macOS:
                Prepare the required virtualization environment


        A provider may report that a host reboot is required before
        installation can continue
        """


    
    


