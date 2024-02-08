""" Test keymaster services """
from datetime import datetime
import json
import logging
import os
from unittest.mock import patch

from homeassistant.components import binary_sensor, sensor
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util.yaml.loader import load_yaml

_LOGGER = logging.getLogger(__name__)
FILE_PATH = f"{os.path.dirname(__file__)}/../custom_components/keymaster/"


async def test_template_sensors(hass: HomeAssistant):
    """Test template sensors."""
    enabled_entity = "input_boolean.enabled_lockname_templatenum"
    input_pin_entity = "input_text.lockname_pin_templatenum"
    code_slot_entity = "sensor.lockname_code_slot_templatenum"
    active_entity = "binary_sensor.active_lockname_templatenum"
    pin_synched_entity = "binary_sensor.pin_synched_lockname_templatenum"
    connected_entity = "sensor.connected_lockname_templatenum"

    keymaster_file = json.loads(
        json.dumps(
            await hass.async_add_executor_job(load_yaml, f"{FILE_PATH}/keymaster.yaml")
        )
        .replace("LOCKNAME", "lockname")
        .replace("TEMPLATENUM", "templatenum")
    )

    # Set a fixed point in time for the tests so that the tests make sense
    ts = datetime(2021, 1, 30, 12, 0, 0)
    with patch("homeassistant.util.dt.now", return_value=ts):
        await async_setup_component(hass, binary_sensor.DOMAIN, keymaster_file)
        await hass.async_block_till_done()
        await async_setup_component(hass, sensor.DOMAIN, keymaster_file)
        await hass.async_block_till_done()
        await hass.async_start()
        await hass.async_block_till_done()

        # Start with default state of UI when keymaster is first
        # set up. Nothing has been enabled yet.

        hass.states.async_set(enabled_entity, STATE_OFF)

        # We are going to go through every variation of a scenario that could
        # affect the active sensor to ensure it's always set to what we want it to.
        await hass.async_block_till_done()
        assert hass.states.get(active_entity).state == STATE_OFF

        # Enable the slot and the active entity should turn on
        hass.states.async_set(enabled_entity, STATE_ON)

        await hass.async_block_till_done()
        assert hass.states.get(active_entity).state == STATE_ON

        # Now lets simulate a lock that hasn't cleared yet
        hass.states.async_set(code_slot_entity, "1111")

        # We have to block twice because first round impacts active and pin synched
        # entities, second round impacts connected entity since it is dependent on the
        # first two
        await hass.async_block_till_done()
        await hass.async_block_till_done()
        assert hass.states.get(active_entity).state == STATE_OFF
        assert hass.states.get(pin_synched_entity).state == STATE_OFF
        assert hass.states.get(connected_entity).state == "Deleting"
        assert hass.states.get(connected_entity).attributes["icon"] == "mdi:wiper-wash"

        # Now lets simulate a lock that has cleared
        hass.states.async_set(code_slot_entity, "")

        await hass.async_block_till_done()
        await hass.async_block_till_done()
        assert hass.states.get(active_entity).state == STATE_OFF
        assert hass.states.get(pin_synched_entity).state == STATE_ON
        assert hass.states.get(connected_entity).state == "Disconnected"
        assert hass.states.get(connected_entity).attributes["icon"] == "mdi:folder-open"

        # Now lets simulate setting a lock
        hass.states.async_set(input_pin_entity, "1111")
        hass.states.async_set(code_slot_entity, "")

        await hass.async_block_till_done()
        await hass.async_block_till_done()
        assert hass.states.get(active_entity).state == STATE_ON
        assert hass.states.get(pin_synched_entity).state == STATE_OFF
        assert hass.states.get(connected_entity).state == "Adding"
        assert (
            hass.states.get(connected_entity).attributes["icon"]
            == "mdi:folder-key-network"
        )

        # Now lets simulate the lock is set
        hass.states.async_set(code_slot_entity, "1111")

        await hass.async_block_till_done()
        await hass.async_block_till_done()
        assert hass.states.get(active_entity).state == STATE_ON
        assert hass.states.get(pin_synched_entity).state == STATE_ON
        assert hass.states.get(connected_entity).state == "Connected"
        assert hass.states.get(connected_entity).attributes["icon"] == "mdi:folder-key"


async def test_reset_code_slots(hass):
    """Test reset_code_slots."""
    enabled_entity = "input_boolean.enabled_lockname_templatenum"
    reset_codeslot_entity = "input_boolean.reset_codeslot_lockname_templatenum"
    input_pin_entity = "input_text.lockname_pin_templatenum"
    input_name_entity = "input_text.lockname_name_templatenum"

    keymaster_file = json.loads(
        json.dumps(
            await hass.async_add_executor_job(
                load_yaml, f"{FILE_PATH}/keymaster_common.yaml"
            )
        )
        .replace("LOCKNAME", "lockname")
        .replace("TEMPLATENUM", "templatenum")
        .replace("INPUT_RESET_CODE_SLOT_HEADER", reset_codeslot_entity)
    )

    # Set a fixed point in time for the tests so that the tests make sense
    ts = datetime(2021, 1, 30, 12, 0, 0)
    with patch("homeassistant.util.dt.now", return_value=ts):
        await async_setup_component(hass, "automation", keymaster_file)
        await hass.async_block_till_done()
        await async_setup_component(hass, "script", keymaster_file)
        await hass.async_block_till_done()
        await hass.async_start()

        # Make input booleans dict
        bool_entity_dict = {}
        for entity in [
            enabled_entity,
        ]:
            bool_entity_dict[entity.split(".")[1]] = {"initial": True}
        bool_entity_dict[reset_codeslot_entity.split(".")[1]] = {"initial": False}

        # Set up input texts
        entity_dict = {}
        for entity in [input_name_entity, input_pin_entity]:
            entity_dict[entity.split(".")[1]] = {"initial": "9999"}
        await async_setup_component(hass, "input_text", {"input_text": entity_dict})

        # set up input booleans
        await async_setup_component(
            hass, "input_boolean", {"input_boolean": bool_entity_dict}
        )

        await hass.async_block_till_done()

        await hass.services.async_call(
            "input_boolean",
            "turn_on",
            {ATTR_ENTITY_ID: reset_codeslot_entity},
            blocking=True,
        )
        await hass.async_block_till_done()

        # Assert that all states have been reset
        for entity in [
            enabled_entity,
            reset_codeslot_entity,
        ]:
            assert hass.states.get(entity).state == STATE_OFF
        for entity in [input_name_entity, input_pin_entity]:
            _LOGGER.error(entity)
            assert hass.states.get(entity).state == ""
