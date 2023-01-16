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

from random import randint
from adapt.intent import IntentBuilder
from neon_utils.validator_utils import numeric_confirmation_validator
from ovos_utils.log import LOG
from neon_utils.skills import NeonSkill
from neon_utils.user_utils import get_user_prefs
from mycroft.skills import intent_file_handler, intent_handler


class UpdateSkill(NeonSkill):
    def __init__(self):
        super(UpdateSkill, self).__init__(name="NeonUpdates")
        self.current_ver = None
        self.latest_ver = None

    @property
    def notify_updates(self):
        return self.settings.get("notify_updates", True)

    @property
    def include_prerelease(self):
        return self.settings.get("include_prerelease", False)

    @property
    def image_url(self):
        return self.settings.get("image_url")

    @property
    def image_drive(self):
        return self.settings.get("image_drive") or "/dev/sdb"

    def initialize(self):
        self.add_event('mycroft.ready',
                       self._check_latest_core_release, once=True)
        self.add_event("update.gui.continue_installation",
                       self.continue_os_installation)
        self.add_event("update.gui.finish_installation",
                       self.finish_os_installation)
        self.add_event("update.gui.install_update", self.handle_update_device)

    def _check_latest_core_release(self, message):
        """
        Handles checking for a new release version
        :param message: message object associated with loaded emit
        """
        response = self.bus.wait_for_response(
            message.forward("neon.core_updater.check_update",
                            {'include_prerelease': self.include_prerelease}))
        if response:
            LOG.debug(f"Got response: {response.data}")
            self.current_ver = response.data.get("installed_version")
            self.latest_ver = response.data.get("latest_version") or \
                              response.data.get("new_version")
            if self.latest_ver != self.current_ver and self.notify_updates and \
                    message.msg_type == "mycroft.ready":
                # TODO: Consider notification on scheduled checks not just ready
                text = self.dialog_renderer.render("notify_update_available",
                                                   {"version": self.latest_ver})
                LOG.info("Update Available")
                # TODO: Use Notification API from ovos_utils
                notification_data = {
                    "sender": self.skill_id,
                    "text": text,
                    "action": "update.gui.install_update",
                    "type": "transient",
                    "style": "info",
                    "callback_data": {**message.data, **{"notification": text}}
                }
                self.bus.emit(message.forward("ovos.notification.api.set",
                                              notification_data))
        else:
            LOG.error("No response from updater plugin")

    def pronounce_version(self, version: str):
        """
        Format a version spec into a speakable string
        """
        if 'a' in version:
            version = version.replace('a', f' {self.translate("alpha")} ')
        if '.' in version:
            version = version.replace('.', f' {self.translate("point")} ')
        return version

    @intent_file_handler("update_device.intent")
    def handle_update_device(self, message):
        """
        Handle a user request to check for updates.
        :param message: message object associated with request
        """
        if get_user_prefs(message)['response_mode'].get('hesitation'):
            self.speak_dialog("check_updates")
        self._check_latest_core_release(message)
        if not all((self.current_ver, self.latest_ver)):
            self.speak_dialog("check_error")
            return

        if self.current_ver == self.latest_ver:
            resp = self.ask_yesno(
                "up_to_date",
                {"version": self.pronounce_version(self.current_ver)})
        else:
            resp = self.ask_yesno(
                "update_core",
                {"new": self.pronounce_version(self.latest_ver),
                 "old": self.pronounce_version(self.current_ver)})
        if resp == "yes":
            if message.data.get('notification'):
                self._dismiss_notification(message)
            self.speak_dialog("starting_update", wait=True)
            self.bus.emit(message.forward("neon.core_updater.start_update",
                                          {"version": self.latest_ver}))
        else:
            self.speak_dialog("not_updating")

    @intent_file_handler("update_configuration.intent")
    def handle_update_configuration(self, message):
        """
        Handle a user request to update default configuration
        :param message: message object associated with request
        """
        resp = self.ask_yesno("ask_update_configuration")
        if resp == "yes":
            self.speak_dialog("starting_update", wait=True)
            self.bus.emit(message.forward("neon.update_config",
                                          {"skill_config": True,
                                           "core_config": True}))
        else:
            self.speak_dialog("not_updating")

    @intent_handler(IntentBuilder("CreateOSMediaIntent").require("create")
                    .require("os").require("media").build())
    def handle_create_os_media(self, message):
        """
        Handle a user request to create a new bootable drive
        :param message: message object associated with request
        """
        resp = self.ask_yesno("ask_download_image")
        if resp == "yes":
            self.add_event("neon.download_os_image.complete",
                           self.on_download_complete, once=True)
            self.speak_dialog("downloading_image")
            self.bus.emit(message.forward("neon.download_os_image",
                                          {"url": self.image_url}))
            self.speak_dialog("drive_instructions")
        else:
            self.speak_dialog("not_updating")

    def on_download_complete(self, message):
        """
        After `handle_create_os_media`, this method will be called with the OS
        image download status. Displays a notification for the user to interact
        with to continue installation.
        :param message: message object associated with download completion
        """
        # TODO: Use Notification API from ovos_utils
        if message.data.get("success"):
            text = self.translate("notify_download_complete")
            notification_data = {
                "sender": self.skill_id,
                "text": text,
                "action": "update.gui.continue_installation",
                "type": "transient",
                "style": "info",
                "callback_data": {**message.data, **{"notification": text}}
            }
        else:
            text = self.translate("notify_download_failed")
            notification_data = {
                "sender": self.skill_id,
                "text": text,
                "type": "transient",
                "style": "error",
                "callback_data": {**message.data, **{"notification": text}}
            }
        LOG.info(f"Showing Download Complete Notification: {notification_data}")
        self.bus.emit(message.forward("ovos.notification.api.set",
                                      notification_data))

    def continue_os_installation(self, message):
        """
        After the user interacts with the completed download notification,
        prompt confirmation to clear data
        :param message: message object associated with notification interaction
        """
        self._dismiss_notification(message)
        image_file = message.data.get("image_file")
        # TODO: Prompt user to select which device?
        confirm_number = randint(100, 999)
        LOG.debug(str(confirm_number))
        validator = numeric_confirmation_validator(str(confirm_number))
        resp = self.get_response('ask_overwrite_drive',
                                 {'confirm': str(confirm_number)},
                                 validator)
        if resp:
            self.speak_dialog("starting_installation")
            self.add_event("neon.install_os_image.complete",
                           self.on_write_complete, once=True)
            self.bus.emit(message.forward("neon.install_os_image",
                                          {"device": self.image_drive,
                                           "image_file": image_file}))
            self.bus.emit(message.forward(
                "ovos.notification.api.set.controlled",
                {"sender": self.skill_id,
                 "text": self.translate("notify_writing_image")}))
        else:
            self.speak_dialog("not_updating")

    def on_write_complete(self, message):
        """
        After `continue_os_installation`, this method will be called with the
        image write status. Displays a notification telling the user they may
        restart and use the new image.
        """
        self.bus.emit(message.forward(
            "ovos.notification.api.remove.controlled"))
        # TODO: Use Notification API from ovos_utils
        if message.data.get("success"):
            text = self.translate("notify_installation_complete")
            notification_data = {
                "sender": self.skill_id,
                "text": text,
                "action": "update.gui.finish_installation",
                "type": "transient",
                "style": "info",
                "callback_data": {**message.data, **{"notification": text}}
            }
        else:
            text = self.translate("notify_installation_failed")
            notification_data = {
                "sender": self.skill_id,
                "text": text,
                "action": "update.gui.finish_installation",
                "type": "transient",
                "style": "error",
                "callback_data": {**message.data, **{"notification": text}}
            }
        LOG.info(f"Showing Download Complete Notification: {notification_data}")
        self.bus.emit(message.forward("ovos.notification.api.set",
                                      notification_data))

    def finish_os_installation(self, message):
        """
        After the user interacts with the installation complete message, speak
        an error if installation failed or else speak instructions before
        shutting down.
        """
        self._dismiss_notification(message)
        if not message.data.get("success"):
            self.speak_dialog("error_installing_os")
        else:
            self.speak_dialog("installation_complete", wait=True)
            self.bus.emit(message.forward("system.shutdown"))

    def _dismiss_notification(self, message):
        """
        Dismiss the notification the user interacted with to trigger a callback.
        """
        LOG.debug(f"Clearing notification: {message.data}")
        self.bus.emit(message.forward(
            "ovos.notification.api.storage.clear.item",
            {"notification": {"sender": self.skill_id,
                              "text": message.data.get("notification")}}))


def create_skill():
    return UpdateSkill()
