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

from pkg_resources import get_distribution, DistributionNotFound
from neon_utils import LOG
from neon_utils.skills import NeonSkill
from adapt.intent import IntentBuilder
from mycroft import intent_handler


class UpdateSkill(NeonSkill):
    def __init__(self):
        super(UpdateSkill, self).__init__(name="NeonUpdates")
        self.core_package_version = None

    def initialize(self):
        try:
            self.core_package_version = get_distribution(self.settings["core_package"]).version
        except DistributionNotFound:
            LOG.warning(f"neon-core not found; other core packages not currently supported")
            self.core_package_version = ""

        # TODO: Intent to get current core version, allow/deny alphas? DM
        if self.config_core["server"].get("update", False):
            self.bus.once('mycroft.ready', self._check_latest_release)

    def _check_latest_release(self, message):
        """
        Handles checking for a new release version
        :param message: message object associated with loaded emit
        """
        # TODO: This should check PyPI for versions and check latest alpha/non-alpha versions against this core DM
        pass

    @intent_handler(IntentBuilder("UpdateNeon").require("update_neon"))
    def handle_update_neon(self, message):
        """
        Checks the version file on the git repository associated with this installation and compares to local version.
        If up to date, will check for a new release in the parent NeonGecko repository and notify user. User will
        be given the option to start an update in cases where there is an update available OR no new release available.
        :param message: message object associated with request
        """
        if self.neon_in_request(message):
            self.speak_dialog("check_updates")


def create_skill():
    return UpdateSkill()
