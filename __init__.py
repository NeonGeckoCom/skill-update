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

from ovos_utils.log import LOG
from neon_utils.skills import NeonSkill
from neon_utils.user_utils import get_user_prefs
from mycroft.skills import intent_file_handler


class UpdateSkill(NeonSkill):
    def __init__(self):
        super(UpdateSkill, self).__init__(name="NeonUpdates")
        self.current_ver = None
        self.latest_ver = None

    def initialize(self):
        self.bus.once('mycroft.ready', self._check_latest_core_release)

    def _check_latest_core_release(self, message):
        """
        Handles checking for a new release version
        :param message: message object associated with loaded emit
        """
        response = self.bus.wait_for_response(message.forward("neon.core_updater.check_update"))
        if response:
            self.current_ver = response.data.get("installed_version")
            self.latest_ver = response.data.get("new_version")
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
    def handle_update_neon(self, message):
        """
        Handle a user request to check for updates.
        :param message: message object associated with request
        """
        if get_user_prefs(message)['response_mode'].get('hesitation'):
            self.speak_dialog("check_updates")
        self._check_latest_core_release(message)
        if not all((self.current_ver, self.latest_ver)):
            self.speak_dialog("check_error")
        elif self.current_ver != self.latest_ver:
            resp = self.ask_yesno("update_core",
                                  {"new": self.pronounce_version(self.latest_ver),
                                   "old": self.pronounce_version(self.current_ver)})
            if resp == "yes":
                self.speak_dialog("starting_update", wait=True)
                self.bus.emit(message.forward("neon.core_updater.start_update",
                                              {"version": self.latest_ver}))
            else:
                self.speak_dialog("not_updating")
        else:
            self.speak_dialog("up_to_date",
                              {"version": self.pronounce_version(self.current_ver)})


def create_skill():
    return UpdateSkill()
