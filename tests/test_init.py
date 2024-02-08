""" Test keymaster_lite init """
from datetime import timedelta
import logging
from unittest.mock import patch

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.keymaster_lite.const import DOMAIN
from homeassistant import setup
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED, STATE_LOCKED
import homeassistant.util.dt as dt_util

from .common import async_fire_time_changed
from .const import CONFIG_DATA, CONFIG_DATA_ALT_SLOTS, CONFIG_DATA_OLD, CONFIG_DATA_REAL

NETWORK_READY_ENTITY = "binary_sensor.frontdoor_network"
KWIKSET_910_LOCK_ENTITY = "lock.smart_code_with_home_connect_technology"
# NETWORK_READY_ENTITY = "binary_sensor.keymaster_zwave_network_ready"

_LOGGER = logging.getLogger(__name__)


async def test_setup_entry(hass, mock_generate_package_files):
    """Test setting up entities."""

    await setup.async_setup_component(hass, "persistent_notification", {})
    entry = MockConfigEntry(
        domain=DOMAIN, title="frontdoor", data=CONFIG_DATA_REAL, version=2
    )

    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 6
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1


async def test_setup_entry_core_state(hass, mock_generate_package_files):
    """Test setting up entities."""
    with patch.object(hass, "state", return_value="STARTING"):
        await setup.async_setup_component(hass, "persistent_notification", {})
        entry = MockConfigEntry(
            domain=DOMAIN, title="frontdoor", data=CONFIG_DATA_REAL, version=2
        )

        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 6
        entries = hass.config_entries.async_entries(DOMAIN)
        assert len(entries) == 1


async def test_unload_entry(
    hass,
    mock_delete_folder,
    mock_delete_lock_and_base_folder,
):
    """Test unloading entities."""

    await setup.async_setup_component(hass, "persistent_notification", {})
    entry = MockConfigEntry(
        domain=DOMAIN, title="frontdoor", data=CONFIG_DATA, version=2
    )

    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 6
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 6
    assert len(hass.states.async_entity_ids(DOMAIN)) == 0

    assert await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()
    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 0


async def test_setup_migration_with_old_path(hass, mock_generate_package_files):
    """Test setting up entities with old path"""
    with patch.object(hass.config, "path", return_value="/config"):
        entry = MockConfigEntry(
            domain=DOMAIN, title="frontdoor", data=CONFIG_DATA_OLD, version=1
        )

        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 6
        entries = hass.config_entries.async_entries(DOMAIN)
        assert len(entries) == 1


async def test_setup_entry_alt_slots(
    hass,
    mock_generate_package_files,
    client,
    lock_kwikset_910,
    integration,
    mock_zwavejs_get_usercodes,
    mock_using_zwavejs,
    caplog,
):
    """Test setting up entities with alternate slot setting."""
    SENSOR_CHECK_1 = "sensor.frontdoor_code_slot_11"
    SENSOR_CHECK_2 = "sensor.frontdoor_code_slot_10"
    now = dt_util.now()

    node = lock_kwikset_910
    state = hass.states.get(KWIKSET_910_LOCK_ENTITY)
    assert state
    assert state.state == STATE_LOCKED

    await setup.async_setup_component(hass, "persistent_notification", {})
    entry = MockConfigEntry(
        domain=DOMAIN, title="frontdoor", data=CONFIG_DATA_ALT_SLOTS, version=2
    )

    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 7
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1

    # Fire the event
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()

    assert "zwave_js" in hass.config.components
    assert "Z-Wave integration not found" not in caplog.text

    assert hass.states.get(NETWORK_READY_ENTITY)
    assert hass.states.get(NETWORK_READY_ENTITY).state == "on"

    # Fast forward time so that sensors update
    async_fire_time_changed(hass, now + timedelta(seconds=7))
    await hass.async_block_till_done()

    assert hass.states.get(SENSOR_CHECK_1)
    assert hass.states.get(SENSOR_CHECK_1).state == "12345"

    assert hass.states.get(SENSOR_CHECK_2)
    assert hass.states.get(SENSOR_CHECK_2).state == "1234"

    assert "DEBUG: Code slot 12 not enabled" in caplog.text
