# NEON AI (TM) SOFTWARE, Software Development Kit & Application Framework
# All trademark and other rights reserved by their respective owners
# Copyright 2008-2022 Neongecko.com Inc.
# Contributors: Daniel McKnight, Guy Daniels, Elon Gasper, Richard Leeds,
# Regina Bloomstine, Casimiro Ferreira, Andrii Pernatii, Kirill Hrymailo
# BSD-3 License
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
# 1. Redistributions of source code must retain the above copyright notice,
#    this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
# 3. Neither the name of the copyright holder nor the names of its
#    contributors may be used to endorse or promote products derived from this
#    software without specific prior written permission.
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO,
# THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
# PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR
# CONTRIBUTORS  BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
# EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
# PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA,
# OR PROFITS;  OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
# LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
# NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE,  EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import shutil
import unittest
from time import time

import pytest
import os
import json

from os import mkdir
from os.path import dirname, join, exists
from mock import Mock
from mycroft_bus_client import Message
from ovos_utils.messagebus import FakeBus


class TestSkill(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        from mycroft.skills.skill_loader import SkillLoader

        bus = FakeBus()
        bus.run_in_thread()
        skill_loader = SkillLoader(bus, dirname(dirname(__file__)))
        skill_loader.load()
        cls.skill = skill_loader.instance
        cls.test_fs = join(dirname(__file__), "skill_fs")
        if not exists(cls.test_fs):
            mkdir(cls.test_fs)
        cls.skill.settings_write_path = cls.test_fs
        cls.skill.file_system.path = cls.test_fs
        cls.skill._init_settings()
        cls.skill.initialize()
        # Override speak and speak_dialog to test passed arguments
        cls.skill.speak = Mock()
        cls.skill.speak_dialog = Mock()

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.test_fs)

    def test_00_skill_init(self):
        # Test any parameters expected to be set in init or initialize methods
        from neon_utils.skills import NeonSkill

        self.assertIsInstance(self.skill, NeonSkill)

    def test_handle_update_neon(self):
        real_ask_yesno = self.skill.ask_yesno
        self.skill.ask_yesno = Mock()
        self.skill.ask_yesno.return_value = None

        message = Message("recognizer_loop:utterance",
                          context={"neon_should_respond": True})
        installed_ver = None
        new_ver = None

        def check_update(message: Message):
            self.skill.bus.emit(message.response(
                data={"installed_version": installed_ver,
                      "new_version": new_ver}))

        start_update = Mock()

        self.skill.bus.on("neon.core_updater.check_update", check_update)
        self.skill.bus.on("neon.core_updater.start_update", start_update)

        # Version check error
        self.skill.handle_update_device(message)
        self.skill.speak_dialog.assert_called_with("check_error")

        # Already updated, declined
        installed_ver = new_ver = '1.1.1'
        self.skill.handle_update_device(message)
        self.skill.ask_yesno.assert_called_with("up_to_date",
                                                {"version": "1 point 1 point 1"})
        self.skill.speak_dialog.assert_called_with("not_updating")

        # Alpha update avaliable, declined
        new_ver = "1.2.1a4"
        self.skill.handle_update_device(message)
        self.skill.ask_yesno.assert_called_with(
            "update_core", {"new": "1 point 2 point 1 alpha 4",
                            "old": "1 point 1 point 1"})
        self.skill.speak_dialog.assert_called_with("not_updating")
        start_update.assert_not_called()

        # Alpha update approved
        self.skill.ask_yesno.return_value = "yes"
        self.skill.handle_update_device(message)
        self.skill.speak_dialog.assert_called_with("starting_update", wait=True)
        start_update.assert_called_once()
        self.assertEqual(start_update.call_args[0][0].data,
                         {"version": new_ver})

        self.skill.ask_yesno = real_ask_yesno

    def test_handle_create_os_media(self):
        real_ask_yesno = self.skill.ask_yesno
        self.skill.ask_yesno = Mock()
        message = Message("test", context={"test": time()})
        # Test no response
        self.skill.handle_create_os_media(message)
        self.skill.ask_yesno.assert_called_once_with("ask_download_image")
        self.skill.speak_dialog.assert_called_with("not_updating")

        # Test user confirmed Installation
        test_message = None

        def handle_start_download(msg):
            nonlocal test_message
            test_message = msg

        self.skill.bus.once("neon.download_os_image", handle_start_download)
        self.skill.ask_yesno.return_value = "yes"

        self.skill.handle_create_os_media(message)
        self.skill.ask_yesno.assert_called_with("ask_download_image")
        self.assertIsInstance(test_message, Message)
        self.assertEqual(test_message.context, message.context)
        self.skill.speak_dialog.assert_any_call("downloading_image")
        self.skill.speak_dialog.assert_called_with("drive_instructions")
        self.assertEqual(
            len(self.skill.bus.ee.listeners("neon.download_os_image.complete")),
            1)
        self.skill.remove_event("neon.download_os_image.complete")

        # Test user declined installation
        self.skill.ask_yesno.return_value = "no"
        self.skill.handle_create_os_media(message)
        self.skill.ask_yesno.assert_called_with("ask_download_image")
        self.skill.speak_dialog.assert_called_with("not_updating")

        self.skill.ask_yesno = real_ask_yesno

    def test_on_download_complete(self):
        # Mock event handling from intent handler
        self.skill.add_event("neon.download_os_image.complete",
                             self.skill.on_download_complete)
        on_notification_set = Mock()

        # Test successful download
        success = Message("neon.download_os_image.complete",
                          {"success": True,
                           "image_file": "test_path"})
        self.skill.bus.once("ovos.notification.api.set", on_notification_set)
        self.skill.bus.emit(success)
        on_notification_set.assert_called_once()
        message = on_notification_set.call_args[0][0]
        self.assertEqual(message.data['text'], 'OS Download Complete')
        self.assertEqual(message.data['action'],
                         'update.gui.continue_installation')
        self.assertEqual(message.data['callback_data']['notification'],
                         message.data['text'])

        failure = Message("neon.download_os_image.complete",
                          {"success": False,
                           "image_file": "test_path"})
        self.skill.bus.once("ovos.notification.api.set", on_notification_set)
        self.skill.bus.emit(failure)
        message = on_notification_set.call_args[0][0]
        self.assertEqual(message.data['text'], 'OS Download Failed')
        self.assertEqual(message.data['style'], 'error')

    def test_continue_os_installation(self):
        real_dismiss_method = self.skill._dismiss_notification
        real_get_response = self.skill.get_response
        self.skill._dismiss_notification = Mock()
        self.skill.get_response = Mock()

        continue_message = Message("neon.download_os_image.complete",
                                   {"success": True,
                                    "image_file": "test_path",
                                    "notification": "OS Download Completed"})

        # Continue no response
        self.skill.get_response.return_value = None
        self.skill.continue_os_installation(continue_message)
        self.skill._dismiss_notification.assert_called_once_with(
            continue_message)
        get_response_call = self.skill.get_response.call_args
        self.assertEqual(get_response_call[0][0], "ask_overwrite_drive")
        confirm_number = get_response_call[0][1]['confirm']
        self.assertTrue(confirm_number.isnumeric())
        self.assertTrue(get_response_call[0][2](confirm_number))
        self.skill.speak_dialog.assert_called_once_with("not_updating")
        self.skill._dismiss_notification.reset_mock()
        self.skill.speak_dialog.reset_mock()

        # Continue not confirmed
        self.skill.get_response.return_value = False
        self.skill.continue_os_installation(continue_message)
        self.skill._dismiss_notification.assert_called_once_with(
            continue_message)
        get_response_call = self.skill.get_response.call_args
        self.assertEqual(get_response_call[0][0], "ask_overwrite_drive")
        confirm_number = get_response_call[0][1]['confirm']
        self.assertTrue(confirm_number.isnumeric())
        self.assertTrue(get_response_call[0][2](confirm_number))
        self.skill.speak_dialog.assert_called_once_with("not_updating")
        self.skill._dismiss_notification.reset_mock()
        self.skill.speak_dialog.reset_mock()

        # Continue confirmed
        self.skill.get_response.return_value = True
        on_install_os = Mock()
        on_controlled = Mock()
        self.skill.bus.once('neon.install_os_image', on_install_os)
        self.skill.bus.once("ovos.notification.api.set.controlled",
                            on_controlled)

        self.skill.continue_os_installation(continue_message)
        self.skill._dismiss_notification.assert_called_once_with(
            continue_message)
        get_response_call = self.skill.get_response.call_args
        self.assertEqual(get_response_call[0][0], "ask_overwrite_drive")
        confirm_number = get_response_call[0][1]['confirm']
        self.assertTrue(confirm_number.isnumeric())
        self.assertTrue(get_response_call[0][2](confirm_number))
        self.skill.speak_dialog.assert_called_once_with("starting_installation")

        self.assertEqual(
            len(self.skill.bus.ee.listeners("neon.install_os_image.complete")),
            1)
        self.skill.remove_event("neon.install_os_image.complete")
        on_install_os.assert_called_once()
        on_controlled.assert_called_once()

        self.skill._dismiss_notification = real_dismiss_method
        self.skill.get_response = real_get_response

    def test_on_write_complete(self):
        # Mock event handling from intent handler
        self.skill.add_event("neon.install_os_image.complete",
                             self.skill.on_write_complete)
        on_notification_removed = Mock()
        on_notification_set = Mock()
        self.skill.bus.on("ovos.notification.api.remove.controlled",
                          on_notification_removed)

        # Test successful download
        success = Message("neon.install_os_image.complete",
                          {"success": True})

        self.skill.bus.once("ovos.notification.api.set",
                            on_notification_set)
        self.skill.bus.emit(success)
        on_notification_removed.assert_called_once()
        on_notification_set.assert_called_once()
        message = on_notification_set.call_args[0][0]
        self.assertEqual(message.data['text'], 'OS Installation Complete')
        self.assertEqual(message.data['action'],
                         'update.gui.finish_installation')
        self.assertEqual(message.data['callback_data']['notification'],
                         message.data['text'])

        on_notification_set.reset_mock()
        on_notification_removed.reset_mock()

        # Test failed download
        failure = Message("neon.install_os_image.complete",
                          {"success": False})
        self.skill.bus.once("ovos.notification.api.set",
                            on_notification_set)
        self.skill.bus.emit(failure)
        on_notification_removed.assert_called_once()
        on_notification_set.assert_called_once()
        message = on_notification_set.call_args[0][0]
        self.assertEqual(message.data['text'], 'OS Installation Failed')
        self.assertEqual(message.data['style'], 'error')
        self.assertEqual(message.data['action'],
                         'update.gui.finish_installation')

    def test_finish_os_installation(self):
        real_dismiss_method = self.skill._dismiss_notification
        self.skill._dismiss_notification = Mock()
        on_shutdown = Mock()
        self.skill.bus.once("system.shutdown", on_shutdown)

        # Test successful installation
        success_message = Message("test", {"success": True})
        self.skill.finish_os_installation(success_message)
        self.skill._dismiss_notification.assert_called_with(success_message)
        self.skill.speak_dialog.assert_called_with("installation_complete",
                                                   wait=True)
        on_shutdown.assert_called_once()

        # Test failed installation
        failure_message = Message("test", {"success": False})
        self.skill.finish_os_installation(failure_message)
        self.skill._dismiss_notification.assert_called_with(failure_message)
        self.skill.speak_dialog.assert_called_with("error_installing_os")

        self.skill._dismiss_notification = real_dismiss_method


class TestSkillLoading(unittest.TestCase):
    """
    Test skill loading, intent registration, and langauge support. Test cases
    are generic, only class variables should be modified per-skill.
    """
    # Static parameters
    bus = FakeBus()
    messages = list()
    test_skill_id = 'test_skill.test'
    # Default Core Events
    default_events = ["mycroft.skill.enable_intent",
                      "mycroft.skill.disable_intent",
                      "mycroft.skill.set_cross_context",
                      "mycroft.skill.remove_cross_context",
                      "intent.service.skills.deactivated",
                      "intent.service.skills.activated",
                      "mycroft.skills.settings.changed",
                      "skill.converse.ping",
                      "skill.converse.request",
                      f"{test_skill_id}.activate",
                      f"{test_skill_id}.deactivate"
                      ]

    # Import and initialize installed skill
    from skill_update import UpdateSkill
    skill = UpdateSkill()

    # Specify valid languages to test
    supported_languages = ["en-us"]

    # Specify skill intents as sets
    adapt_intents = {"CreateOSMediaIntent"}
    padatious_intents = {"update_device.intent",
                         "update_configuration.intent"}

    # regex entities, not necessarily filenames
    regex = set()
    # vocab is lowercase .voc file basenames
    vocab = {"create", "media", "os"}
    # dialog is .dialog file basenames (case-sensitive)
    dialog = {"alpha", "check_error", "check_updates", "not_updating", "point",
              "starting_update", "up_to_date", "update_core",
              "ask_update_configuration", "ask_download_image",
              "ask_overwrite_drive", "downloading_image", "drive_instructions",
              "error_installing_os", "installation_complete",
              "starting_installation", "notify_download_complete",
              "notify_download_failed", "notify_installation_complete",
              "notify_installation_failed", "notify_writing_image",
              "notify_update_available"}

    @classmethod
    def setUpClass(cls) -> None:
        cls.bus.on("message", cls._on_message)
        cls.skill.config_core["secondary_langs"] = cls.supported_languages
        cls.skill._startup(cls.bus, cls.test_skill_id)
        cls.adapt_intents = {f'{cls.test_skill_id}:{intent}'
                             for intent in cls.adapt_intents}
        cls.padatious_intents = {f'{cls.test_skill_id}:{intent}'
                                 for intent in cls.padatious_intents}

    @classmethod
    def _on_message(cls, message):
        cls.messages.append(json.loads(message))

    def test_skill_setup(self):
        self.assertEqual(self.skill.skill_id, self.test_skill_id)
        for msg in self.messages:
            self.assertEqual(msg["context"]["skill_id"], self.test_skill_id)

    def test_intent_registration(self):
        registered_adapt = list()
        registered_padatious = dict()
        registered_vocab = dict()
        registered_regex = dict()
        for msg in self.messages:
            if msg["type"] == "register_intent":
                registered_adapt.append(msg["data"]["name"])
            elif msg["type"] == "padatious:register_intent":
                lang = msg["data"]["lang"]
                registered_padatious.setdefault(lang, list())
                registered_padatious[lang].append(msg["data"]["name"])
            elif msg["type"] == "register_vocab":
                lang = msg["data"]["lang"]
                if msg['data'].get('regex'):
                    registered_regex.setdefault(lang, dict())
                    regex = msg["data"]["regex"].split(
                        '<', 1)[1].split('>', 1)[0].replace(
                        self.test_skill_id.replace('.', '_'), '').lower()
                    registered_regex[lang].setdefault(regex, list())
                    registered_regex[lang][regex].append(msg["data"]["regex"])
                else:
                    registered_vocab.setdefault(lang, dict())
                    voc_filename = msg["data"]["entity_type"].replace(
                        self.test_skill_id.replace('.', '_'), '').lower()
                    registered_vocab[lang].setdefault(voc_filename, list())
                    registered_vocab[lang][voc_filename].append(
                        msg["data"]["entity_value"])
        self.assertEqual(set(registered_adapt), self.adapt_intents)
        for lang in self.supported_languages:
            if self.padatious_intents:
                self.assertEqual(set(registered_padatious[lang]),
                                 self.padatious_intents)
            if self.vocab:
                self.assertEqual(set(registered_vocab[lang].keys()), self.vocab)
            if self.regex:
                self.assertEqual(set(registered_regex[lang].keys()), self.regex)
            for voc in self.vocab:
                # Ensure every vocab file has at least one entry
                self.assertGreater(len(registered_vocab[lang][voc]), 0)
            for rx in self.regex:
                # Ensure every vocab file has exactly one entry
                self.assertTrue(all((rx in line for line in
                                     registered_regex[lang][rx])))

    def test_skill_events(self):
        events = self.default_events + list(self.adapt_intents)
        for event in events:
            self.assertIn(event, [e[0] for e in self.skill.events])

    def test_dialog_files(self):
        for lang in self.supported_languages:
            for dialog in self.dialog:
                file = self.skill.find_resource(f"{dialog}.dialog", "dialog",
                                                lang)
                self.assertTrue(os.path.isfile(file))


class TestSkillIntentMatching(unittest.TestCase):
    # Import and initialize installed skill
    from skill_update import UpdateSkill
    skill = UpdateSkill()

    import yaml
    test_intents = join(dirname(__file__), 'test_intents.yaml')
    with open(test_intents) as f:
        valid_intents = yaml.safe_load(f)

    from mycroft.skills.intent_service import IntentService
    bus = FakeBus()
    intent_service = IntentService(bus)
    test_skill_id = 'test_skill.test'

    @classmethod
    def setUpClass(cls) -> None:
        cls.skill.config_core["secondary_langs"] = list(cls.valid_intents.keys())
        cls.skill._startup(cls.bus, cls.test_skill_id)

    def test_intents(self):
        for lang in self.valid_intents.keys():
            for intent, examples in self.valid_intents[lang].items():
                intent_event = f'{self.test_skill_id}:{intent}'
                self.skill.events.remove(intent_event)
                intent_handler = Mock()
                self.skill.events.add(intent_event, intent_handler)
                for utt in examples:
                    if isinstance(utt, dict):
                        data = list(utt.values())[0]
                        utt = list(utt.keys())[0]
                    else:
                        data = list()
                    message = Message('test_utterance',
                                      {"utterances": [utt], "lang": lang})
                    self.intent_service.handle_utterance(message)
                    intent_handler.assert_called_once()
                    intent_message = intent_handler.call_args[0][0]
                    self.assertIsInstance(intent_message, Message)
                    self.assertEqual(intent_message.msg_type, intent_event)
                    for datum in data:
                        if isinstance(datum, dict):
                            name = list(datum.keys())[0]
                            value = list(datum.values())[0]
                        else:
                            name = datum
                            value = None
                        if name in intent_message.data:
                            # This is an entity
                            voc_id = name
                        else:
                            # We mocked the handler, data is munged
                            voc_id = f'{self.test_skill_id.replace(".", "_")}' \
                                     f'{name}'
                        self.assertIsInstance(intent_message.data.get(voc_id),
                                              str, intent_message.data)
                        if value:
                            self.assertEqual(intent_message.data.get(voc_id),
                                             value)
                    intent_handler.reset_mock()


if __name__ == '__main__':
    pytest.main()
