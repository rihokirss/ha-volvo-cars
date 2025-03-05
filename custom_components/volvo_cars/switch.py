"""Volvo Cars switch."""

from dataclasses import dataclass
from datetime import UTC, datetime
import logging
from typing import Any, cast

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import ATTR_API_TIMESTAMP, ATTR_LAST_RESULT, DOMAIN
from .coordinator import VolvoCarsConfigEntry, VolvoCarsDataCoordinator
from .entity import VolvoCarsEntity
from .entity_description import VolvoCarsDescription
from .volvo.models import VolvoApiException, VolvoCarsApiBaseModel, VolvoCarsValue

PARALLEL_UPDATES = 0
_LOGGER = logging.getLogger(__name__)

@dataclass(frozen=True, kw_only=True)
class VolvoCarsSwitchDescription(VolvoCarsDescription, SwitchEntityDescription):
    """Describes a Volvo Cars switch entity."""
    api_command_on: str
    api_command_off: str
    required_command_key: str

SWITCHES: tuple[VolvoCarsSwitchDescription, ...] = (
    VolvoCarsSwitchDescription(
        key="climatization",
        translation_key="climatization",
        api_field="climatization_status",
        api_command_on="climatization-start",
        api_command_off="climatization-stop",
        required_command_key="CLIMATIZATION_START",
        icon="mdi:air-conditioner",
    ),
)

async def async_setup_entry(
    _: HomeAssistant,
    entry: VolvoCarsConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switch."""
    coordinator = entry.runtime_data.coordinator

    switches = [
        VolvoCarsSwitch(coordinator, description)
        for description in SWITCHES
        if description.required_command_key in coordinator.commands
    ]

    async_add_entities(switches)

class VolvoCarsSwitch(VolvoCarsEntity, SwitchEntity):
    """Representation of a Volvo Cars switch."""
    entity_description: VolvoCarsSwitchDescription

    def __init__(
        self,
        coordinator: VolvoCarsDataCoordinator,
        description: VolvoCarsSwitchDescription,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, description, Platform.SWITCH)
        self._attr_is_on = False  # Default state, update from API if available

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self._async_handle_command(self.entity_description.api_command_on, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self._async_handle_command(self.entity_description.api_command_off, False)

    async def _async_handle_command(self, command: str, state: bool) -> None:
        """Execute command and update state."""
        try:
            result = await self.coordinator.api.async_execute_command(command)
            status = result.invoke_status if result else ""
            
            if status.upper() in ("COMPLETED", "DELIVERED"):
                self._attr_is_on = state
                self._attr_icon = "mdi:air-conditioner" if state else "mdi:air-conditioner-off"
                self._attr_extra_state_attributes[ATTR_LAST_RESULT] = status.lower()
                self._attr_extra_state_attributes[ATTR_API_TIMESTAMP] = datetime.now(UTC).isoformat()
                self.async_write_ha_state()
            else:
                raise HomeAssistantError(f"Command failed: {status}")

        except VolvoApiException as ex:
            raise HomeAssistantError from ex
        finally:
            await self.coordinator.async_update_request_count(1)
            self.coordinator.async_update_listeners()
