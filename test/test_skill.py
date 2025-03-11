# NEON AI (TM) SOFTWARE, Software Development Kit & Application Framework
# All trademark and other rights reserved by their respective owners
# Copyright 2008-2025 Neongecko.com Inc.
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

import pytest

from os import environ
from threading import Event, Thread
from time import time, sleep
from mock import Mock
from ovos_bus_client import Message
from neon_minerva.tests.skill_unit_test_base import SkillTestCase

environ["TEST_SKILL_ENTRYPOINT"] = "skill-update.neongeckocom"


class TestSkill(SkillTestCase):
    def test_00_skill_init(self):
        # Test any parameters expected to be set in init or initialize methods
        from neon_utils.skills import NeonSkill

        self.assertIsInstance(self.skill, NeonSkill)
        self.assertIsInstance(self.skill.default_prerelease, bool)
        self.assertIsInstance(self.skill.os_updates_supported, bool)
        self.assertIsInstance(self.skill.check_initramfs, bool)
        self.assertIsInstance(self.skill.check_squashfs, bool)
        self.assertIsInstance(self.skill.check_python, bool)
        self.assertIsInstance(self.skill.notify_updates, bool)
        self.assertEqual(self.skill.include_prerelease,
                         self.skill.default_prerelease)
        # self.assertIsInstance(self.skill.image_url, str)
        self.assertIsInstance(self.skill.image_drive, str)

        self.skill.include_prerelease = True
        self.assertTrue(self.skill.include_prerelease)
        self.skill.include_prerelease = False
        self.assertFalse(self.skill.include_prerelease)

    def test_handle_core_version(self):
        real_check_release = self.skill._check_latest_release
        self.skill._check_latest_release = Mock()
        test_message = Message("")

        # No alpha version
        self.skill.current_ver = "22.10.0"
        self.skill.handle_core_version(test_message)
        self.skill._check_latest_release.assert_called_once_with(test_message)
        self.skill.speak_dialog.assert_called_with("core_version", {"version": "22 point 10 point 0"})

        # Alpha version
        self.skill.current_ver = "22.10.1a10"
        self.skill.handle_core_version(test_message)
        self.skill._check_latest_release.assert_called_with(test_message)
        self.skill.speak_dialog.assert_called_with("core_version", {"version": "22 point 10 point 1 alpha 10"})

        self.skill._check_latest_release = real_check_release

    def test_handle_update_device(self):
        real_ask_yesno = self.skill.ask_yesno
        self.skill.ask_yesno = Mock()
        self.skill.ask_yesno.return_value = None

        message = Message("recognizer_loop:utterance",
                          context={"neon_should_respond": True})
        installed_ver = None
        new_ver = None
        check_update_event = Event()
        plugin_downloading = True
        download_success = True
        new_version = None

        def check_update(message: Message):
            check_update_event.set()
            self.skill.bus.emit(message.response(
                data={"installed_version": installed_ver,
                      "new_version": new_ver}))

        def get_update_status(message: Message):
            nonlocal plugin_downloading
            nonlocal download_success
            nonlocal new_version
            if download_success and not plugin_downloading:
                self.bus.emit(message.reply("neon.update_squashfs.response",
                                            {"new_version": new_version}))
                sleep(1)  # Allow some time for the skill handler
            self.skill.bus.emit(message.response(
                {"downloading": plugin_downloading}))

        start_update = Mock()
        self.skill.bus.remove_all_listeners("neon.core_updater.check_update")
        self.skill.bus.remove_all_listeners("neon.core_updater.start_update")
        self.skill.bus.on("neon.core_updater.check_update", check_update)
        self.skill.bus.on("neon.core_updater.start_update", start_update)
        self.skill.bus.on("neon.device_updater.get_download_status",
                          get_update_status)
        # Version check error
        self.skill.handle_update_device(message)
        self.skill.speak_dialog.assert_called_with("check_error")

        # Specify Python updates only
        self.skill.settings["update_initramfs"] = False
        self.skill.settings["update_squashfs"] = False
        self.skill.settings["update_python"] = True
        self.assertFalse(self.skill.check_initramfs)
        self.assertFalse(self.skill.check_squashfs)
        self.assertTrue(self.skill.check_python)

        # Already updated, declined
        installed_ver = new_ver = '1.1.1'
        self.skill.handle_update_device(message)
        self.assertTrue(check_update_event.is_set())
        check_update_event.clear()
        self.skill.speak_dialog.assert_any_call(
            "up_to_date", {"version": "1 point 1 point 1"}, wait=True)
        self.skill.ask_yesno.assert_called_with("ask_update_anyways")

        self.skill.speak_dialog.assert_called_with("not_updating")

        # Alpha update avaliable, declined
        new_ver = "1.2.1a4"
        self.skill.handle_update_device(message)
        self.assertTrue(check_update_event.is_set())
        check_update_event.clear()
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

        # Update already in-progress
        self.skill._updating = True
        self.skill.handle_update_device(message)
        self.skill.speak_dialog.assert_called_with("update_in_progress")

        # TODO: Test offline, initramfs update success/error
        self.skill._download_check_interval = 1
        self.skill._updating = False
        self.skill.settings["update_squashfs"] = True
        self.skill.settings["update_python"] = False
        self.skill._check_squashfs_update = Mock(
            return_value={"core": {"version": "old"}, "build_version": "new"})

        # Download error
        real_failure = self.skill._handle_download_failure
        self.skill._handle_download_failure = Mock(side_effect=real_failure)
        t = Thread(target=self.skill.handle_update_device, args=(message,),
                   daemon=True)
        t.start()
        sleep(1)
        self.assertTrue(self.skill._updating)
        self.assertFalse(self.skill._download_completed.is_set())
        download_success = False
        plugin_downloading = False
        t.join(10)
        self.skill._handle_download_failure.assert_called_once()
        self.assertFalse(self.skill._updating)
        self.assertTrue(self.skill._download_completed.is_set())

        # Download failure
        plugin_downloading = True
        t = Thread(target=self.skill.handle_update_device, args=(message,),
                   daemon=True)
        t.start()
        sleep(1)
        self.skill.speak_dialog.assert_called_with("starting_update", wait=True)
        self.assertFalse(self.skill._download_completed.is_set())
        self.skill._updating = True

        download_success = True
        plugin_downloading = False
        t.join(10)
        self.assertTrue(self.skill._download_completed.is_set())
        self.assertFalse(self.skill._updating)
        self.skill.speak_dialog.assert_called_with("error_updating_os",
                                                   {"help": ""})

        # Download success
        new_version = "1.0.0"
        plugin_downloading = True
        t = Thread(target=self.skill.handle_update_device, args=(message,),
                   daemon=True)
        t.start()
        sleep(1)
        self.skill.speak_dialog.assert_called_with("starting_update", wait=True)
        self.assertFalse(self.skill._download_completed.is_set())
        self.skill._updating = True

        download_success = True
        plugin_downloading = False
        t.join(10)
        self.assertTrue(self.skill._download_completed.is_set())
        self.skill.speak_dialog.assert_called_with("update_restarting",
                                                   wait=True)

        self.skill.bus.remove_all_listeners("neon.core_updater.check_update")
        self.skill.bus.remove_all_listeners("neon.core_updater.start_update")
        self.skill.ask_yesno = real_ask_yesno
        self.skill._handle_download_failure = real_failure

    def test_handle_switch_update_track(self):
        real_ask_yesno = self.skill.ask_yesno
        self.skill.ask_yesno = Mock()
        real_check_release = self.skill._check_latest_release
        mock = Mock()
        self.skill._check_latest_release = mock

        # Test switch beta no change
        self.skill.include_prerelease = True
        test_message = Message("test", {"beta": "prerelease"})
        self.skill.handle_switch_update_track(test_message)
        self.skill.ask_yesno.assert_not_called()
        self.skill.speak_dialog.assert_called_with("update_track_already_set",
                                                   {"track": "beta"})

        # Test switch stable no change
        self.skill.include_prerelease = False
        test_message = Message("test", {"stable": "default"})
        self.skill.handle_switch_update_track(test_message)
        self.skill.ask_yesno.assert_not_called()
        self.skill.speak_dialog.assert_called_with("update_track_already_set",
                                                   {"track": "stable"})

        # Test switch beta unconfirmed
        self.skill.ask_yesno.return_value = "no"
        test_message = Message("test", {"beta": "prerelease"})
        self.skill.handle_switch_update_track(test_message)
        self.skill.ask_yesno.assert_called_with("ask_change_update_track",
                                                {"track": "beta"})
        self.skill.speak_dialog.assert_called_with(
            "confirm_no_change_update_track", {"track": "stable"})
        self.assertFalse(self.skill.include_prerelease)

        # Test switch beta confirmed
        self.skill.ask_yesno.return_value = "yes"
        self.skill.handle_switch_update_track(test_message)
        self.skill.ask_yesno.assert_called_with("ask_change_update_track",
                                                {"track": "beta"})
        self.skill.speak_dialog.assert_called_with(
            "confirm_change_update_track", {"track": "beta"})
        self.assertTrue(self.skill.include_prerelease)
        mock.assert_called_once()
        mock.reset_mock()

        # Test switch stable unconfirmed
        self.skill.ask_yesno.return_value = "no"
        test_message = Message("test", {"stable": "default"})
        self.skill.handle_switch_update_track(test_message)
        self.skill.ask_yesno.assert_called_with("ask_change_update_track",
                                                {"track": "stable"})
        self.skill.speak_dialog.assert_called_with(
            "confirm_no_change_update_track", {"track": "beta"})
        self.assertTrue(self.skill.include_prerelease)

        # Test switch stable confirmed
        self.skill.ask_yesno.return_value = "yes"
        self.skill.handle_switch_update_track(test_message)
        self.skill.ask_yesno.assert_called_with("ask_change_update_track",
                                                {"track": "stable"})
        self.skill.speak_dialog.assert_called_with(
            "confirm_change_update_track", {"track": "stable"})
        self.assertFalse(self.skill.include_prerelease)
        mock.assert_called_once()

        self.skill.ask_yesno = real_ask_yesno
        self.skill._check_latest_release = real_check_release

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
        self.assertEqual(message.data['text'],
                         'OS Installation Failed: Unknown Error')
        self.assertEqual(message.data['style'], 'error')
        self.assertEqual(message.data['action'],
                         'update.gui.finish_installation')

        # `no_valid_device`, `no_image_file`, something else
        failure = Message("neon.install_os_image.complete",
                          {"success": False,
                           "error": "no_valid_device"})
        self.skill.bus.once("ovos.notification.api.set",
                            on_notification_set)
        self.skill.bus.emit(failure)
        message = on_notification_set.call_args[0][0]
        self.assertEqual(message.data['text'],
                         'OS Installation Failed: No Device to Write')
        self.assertEqual(message.data['style'], 'error')
        self.assertEqual(message.data['action'],
                         'update.gui.finish_installation')

        failure = Message("neon.install_os_image.complete",
                          {"success": False,
                           "error": "no_image_file"})
        self.skill.bus.once("ovos.notification.api.set",
                            on_notification_set)
        self.skill.bus.emit(failure)
        message = on_notification_set.call_args[0][0]
        self.assertEqual(message.data['text'],
                         'OS Installation Failed: No Image to Write')
        self.assertEqual(message.data['style'], 'error')
        self.assertEqual(message.data['action'],
                         'update.gui.finish_installation')

        failure = Message("neon.install_os_image.complete",
                          {"success": False,
                           "error": "Some error"})
        self.skill.bus.once("ovos.notification.api.set",
                            on_notification_set)
        self.skill.bus.emit(failure)
        message = on_notification_set.call_args[0][0]
        self.assertEqual(message.data['text'],
                         'OS Installation Failed: Some error')
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


if __name__ == '__main__':
    pytest.main()
