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

import os

from random import randint
from typing import Optional
from adapt.intent import IntentBuilder
from neon_utils.validator_utils import numeric_confirmation_validator
from ovos_utils import classproperty
from ovos_utils.log import LOG
from ovos_utils.process_utils import RuntimeRequirements
from ovos_utils.network_utils import is_connected_http
from neon_utils.skills import NeonSkill
from neon_utils.user_utils import get_user_prefs
from ovos_workshop.decorators import intent_file_handler, intent_handler


class UpdateSkill(NeonSkill):
    def __init__(self, **kwargs):
        NeonSkill.__init__(self, **kwargs)
        self.current_core_ver = None
        self.latest_core_ver = None
        self._update_filename = "update_signal"
        self._os_updates_supported = None

        self.add_event('mycroft.ready', self._on_ready)
        self.add_event("update.gui.continue_installation",
                       self.continue_os_installation)
        self.add_event("update.gui.finish_installation",
                       self.finish_os_installation)
        self.add_event("update.gui.install_update", self.handle_update_device)

    @classproperty
    def runtime_requirements(self):
        return RuntimeRequirements(network_before_load=False,
                                   internet_before_load=False,
                                   gui_before_load=False,
                                   requires_internet=True,
                                   requires_network=True,
                                   requires_gui=False,
                                   no_internet_fallback=False,
                                   no_network_fallback=False,
                                   no_gui_fallback=True)

    @property
    def os_updates_supported(self) -> bool:
        if self._os_updates_supported is None:
            try:
                import neon_phal_plugin_device_updater
                self._os_updates_supported = True
            except ImportError:
                self._os_updates_supported = False
        return self._os_updates_supported

    @property
    def check_initramfs(self) -> bool:
        return bool(self.settings.get("update_initramfs",
                                      self.os_updates_supported))

    @property
    def check_squashfs(self) -> bool:
        return bool(self.settings.get("update_squashfs",
                                      self.os_updates_supported))

    @property
    def notify_updates(self):
        return self.settings.get("notify_updates", True)

    @property
    def include_prerelease(self):
        return self.settings.get("include_prerelease", False)

    @include_prerelease.setter
    def include_prerelease(self, value: bool):
        self.settings['include_prerelease'] = value
        self.settings.store()

    @property
    def image_url(self):
        return self.settings.get("image_url")

    @property
    def image_drive(self):
        return self.settings.get("image_drive") or "/dev/sdb"

    def _on_ready(self, message):
        if self.check_squashfs and self._check_squashfs_update(message):
            if self.notify_updates:
                text = self.dialog_renderer.render("notify_os_update_available")
                LOG.info("OS Update Available")
                callback_data = {**message.data, **{"notification": text}}
                self.gui.show_notification(text,
                                           action="update.gui.install_update",
                                           callback_data=callback_data)
        else:
            LOG.debug("Checking latest core version")
            self._check_latest_core_release(message)

        update_stat = self._check_update_status()
        LOG.debug(f"Update status is {update_stat}")
        if not update_stat:
            # No update was attempted
            return
        speak_version = self.pronounce_version(self.current_core_ver)
        if update_stat is True:
            LOG.debug("Update success")
            self.speak_dialog("notify_update_success",
                              {"version": speak_version})
        elif update_stat is False:
            LOG.warning("Update failed")
            self.speak_dialog("notify_update_failure",
                              {"version": speak_version})

    def _check_latest_core_release(self, message):
        """
        Handles checking for a new release version
        :param message: message object associated with loaded emit
        """
        response = self.bus.wait_for_response(
            message.forward("neon.core_updater.check_update",
                            {'include_prerelease': self.include_prerelease}),
            timeout=15)
        if response:
            LOG.debug(f"Got response: {response.data}")
            self.current_core_ver = response.data.get("installed_version")
            self.latest_core_ver = response.data.get("latest_version") or \
                response.data.get("new_version")
            if not self.latest_core_ver:
                LOG.error(f"Expected string version and got none in response: "
                          f"{response.data}")
            elif self.latest_core_ver != self.current_core_ver and \
                    self.notify_updates and \
                    message.msg_type in ("mycroft.ready", "neon.update.check"):
                text = self.dialog_renderer.render(
                    "notify_update_available",
                    {"version": self.latest_core_ver})
                LOG.info("Update Available")
                callback_data = {**message.data, **{"notification": text}}
                self.gui.show_notification(text,
                                           action="update.gui.install_update",
                                           callback_data=callback_data)

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
        # Explicitly enabled for initramfs checks that involve file downloads
        if get_user_prefs(message)['response_mode'].get('hesitation') or \
                self.check_initramfs:
            self.speak_dialog("check_updates")
        initramfs_available = False
        squashfs_available = False

        if self.check_initramfs:
            initramfs_available = self._check_initramfs_update(message)
        if self.check_squashfs:
            squashfs_available = self._check_squashfs_update(message)

        if initramfs_available or squashfs_available:
            resp = self.ask_yesno("update_system")
            if resp == "yes":
                self.speak_dialog("starting_update", wait=True)

                if initramfs_available:
                    LOG.info("Updating initramfs")
                    resp = self.bus.wait_for_response(
                        message.forward("neon.update_initramfs"), timeout=30)
                    if resp and resp.data.get("updated"):
                        LOG.info("initramfs updated")
                        # TODO: Speak?
                    else:
                        error = resp.data.get("error")
                        LOG.error(f"initramfs update failed: {error}")
                        self.speak_dialog("error_updating_os")
                        return
                if squashfs_available:
                    self._write_update_signal("squashfs")

                    self.gui.show_controlled_notification(
                        self.translate("notify_downloading_update"))

                    LOG.info("Updating squashfs")
                    resp = self.bus.wait_for_response(
                        message.forward("neon.update_squashfs"), timeout=1800)
                    if not resp:
                        LOG.warning(f"Timed out waiting for download")
                        self.gui.remove_controlled_notification()
                        self.speak_dialog("error_updating_os")
                        return
                    self.gui.remove_controlled_notification()
                    if resp.data.get("new_version"):
                        LOG.info("squashfs updated")
                        self.speak_dialog("update_restarting", wait=True)
                        self.bus.emit(message.forward("system.reboot"))
                    else:
                        error = "no response"
                        if resp:
                            error = resp.data.get("error")
                        LOG.error(f"squashfs update failed: {error}")
                        self.speak_dialog("error_updating_os")
                        return

                return
        # No OS update available or user declined, check core updates
        self._check_package_update(message)

    def _check_initramfs_update(self, message) -> bool:
        """
        Check for an updated initramfs image
        """
        resp = self.bus.wait_for_response(message.forward(
            "neon.check_update_initramfs"), timeout=10)
        if resp and resp.data.get("update_available"):
            LOG.info("Initramfs update available")
            return True
        LOG.debug("No initramfs update")
        return False

    def _check_squashfs_update(self, message) -> bool:
        """
        Check for an updated squashfs image
        """
        resp = self.bus.wait_for_response(message.forward(
            "neon.check_update_squashfs"), timeout=10)
        if resp and resp.data.get("update_available"):
            LOG.info("Squashfs update available")
            return True
        LOG.debug("No Squashfs update")
        return False

    def _check_package_update(self, message):
        self._check_latest_core_release(message)
        if not all((self.current_core_ver, self.latest_core_ver)):
            self.speak_dialog("check_error")
            return

        # TODO: Support alternate update sources?
        if not is_connected_http("https://github.com"):
            LOG.warning(f"GitHub not available. Skipping update")
            self.speak_dialog("error_offline")
            return

        if self.current_core_ver == self.latest_core_ver:
            resp = self.ask_yesno(
                "up_to_date",
                {"version": self.pronounce_version(self.current_core_ver)})
        else:
            resp = self.ask_yesno(
                "update_core",
                {"new": self.pronounce_version(self.latest_core_ver),
                 "old": self.pronounce_version(self.current_core_ver)})
        if resp == "yes":
            if message.data.get('notification'):
                self._dismiss_notification(message)
            self._write_update_signal(self.latest_core_ver)
            self.speak_dialog("starting_update", wait=True)
            self.bus.emit(message.forward("neon.core_updater.start_update",
                                          {"version": self.latest_core_ver}))
        else:
            self.speak_dialog("not_updating")

    def _write_update_signal(self, new_ver: str):
        """
        Write a file with the version being updated to that can be checked upon
        next boot
        :param new_ver: New core version being updated to
        """
        with self.file_system.open(self._update_filename, 'w+') as f:
            f.write(new_ver)

    def _check_update_status(self) -> Optional[bool]:
        """
        Check if an update was completed on startup.
        Returns:
            None if no update was attempted
            True if an update was successful
            False if an update failed
        """
        update_filepath = os.path.join(self.file_system.path,
                                       self._update_filename)
        if not os.path.exists(update_filepath):
            return None
        with open(update_filepath, 'r') as f:
            expected_ver = f.read()
        os.remove(update_filepath)
        LOG.info(f"Removed update signal at {update_filepath}")
        if expected_ver == "squashfs":
            LOG.info("Updated squashFS")
            return True
        if self.current_core_ver != expected_ver:
            LOG.error(f"Update expected {expected_ver} but "
                      f"{self.current_core_ver} is installed")
            return False
        return True

    @intent_file_handler("core_version.intent")
    def handle_core_version(self, message):
        """
        Handle a user request for the current installed version.
        :param message: message object associated with request
        """
        self._check_latest_core_release(message)
        version = self.pronounce_version(self.current_core_ver)
        LOG.debug(version)
        self.speak_dialog("core_version", {"version": version})

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
            self.gui.show_controlled_notification(
                self.translate("notify_downloading_os"))
        else:
            self.speak_dialog("not_updating")

    @intent_handler(IntentBuilder("SwitchUpdateTrackIntent").require("change")
                    .one_of("stable", "beta").require("updates").build())
    def handle_switch_update_track(self, message):
        """
        Handle a user request to change to beta or stable release tracks
        :param message: message object associated with request
        """
        include_prereleases = True if message.data.get('beta') else False
        LOG.debug(f"Update to include_prerelease={include_prereleases}")
        if include_prereleases:
            update_track = self.translate("word_beta")
        else:
            update_track = self.translate("word_stable")
        if include_prereleases == self.include_prerelease:  # Already Set
            self.speak_dialog("update_track_already_set",
                              {"track": update_track})
            return
        resp = self.ask_yesno("ask_change_update_track",
                              {"track": update_track})

        if resp == "yes":
            self.include_prerelease = include_prereleases
            self.speak_dialog("confirm_change_update_track",
                              {"track": update_track})
            self._check_latest_core_release(
                message.forward("neon.update.check"))
        else:
            if self.include_prerelease:
                update_track = self.translate("word_beta")
            else:
                update_track = self.translate("word_stable")
            self.speak_dialog("confirm_no_change_update_track",
                              {"track": update_track})

    def on_download_complete(self, message):
        """
        After `handle_create_os_media`, this method will be called with the OS
        image download status. Displays a notification for the user to interact
        with to continue installation.
        :param message: message object associated with download completion
        """
        self.gui.remove_controlled_notification()
        if message.data.get("success"):
            LOG.info(f"Showing Download Complete Notification")
            text = self.translate("notify_download_complete")
            self.gui.show_notification(
                content=text,
                action="update.gui.continue_installation",
                callback_data={**message.data, **{"notification": text}})

        else:
            LOG.info(f"Showing Download Failed Notification")
            text = self.translate("notify_download_failed")
            self.gui.show_notification(content=text,
                                       style="error",
                                       callback_data={**message.data,
                                                      **{"notification": text}})

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
        if message.data.get("success"):
            LOG.info("Showing Write Complete Notification")
            text = self.translate("notify_installation_complete")
            self.gui.show_notification(content=text,
                                       action="update.gui.finish_installation",
                                       callback_data={**message.data,
                                                      **{"notification": text}})

        else:
            LOG.info("Showing Write Failed Notification")
            text = self.translate("notify_installation_failed")
            self.gui.show_notification(content=text,
                                       action="update.gui.finish_installation",
                                       style="error",
                                       callback_data={**message.data,
                                                      **{"notification": text}})

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
