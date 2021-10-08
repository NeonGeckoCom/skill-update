# NEON AI (TM) SOFTWARE, Software Development Kit & Application Development System
#
# Copyright 2008-2021 Neongecko.com Inc. | All Rights Reserved
#
# Notice of License - Duplicating this Notice of License near the start of any file containing
# a derivative of this software is a condition of license for this software.
# Friendly Licensing:
# No charge, open source royalty free use of the Neon AI software source and object is offered for
# educational users, noncommercial enthusiasts, Public Benefit Corporations (and LLCs) and
# Social Purpose Corporations (and LLCs). Developers can contact developers@neon.ai
# For commercial licensing, distribution of derivative works or redistribution please contact licenses@neon.ai
# Distributed on an "AS IS” basis without warranties or conditions of any kind, either express or implied.
# Trademarks of Neongecko: Neon AI(TM), Neon Assist (TM), Neon Communicator(TM), Klat(TM)
# Authors: Guy Daniels, Daniel McKnight, Regina Bloomstine, Elon Gasper, Richard Leeds
#
# Specialized conversational reconveyance options from Conversation Processing Intelligence Corp.
# US Patents 2008-2021: US7424516, US20140161250, US20140177813, US8638908, US8068604, US8553852, US10530923, US10530924
# China Patent: CN102017585  -  Europe Patent: EU2156652  -  Patents Pending

from adapt.intent import IntentBuilder
from pkg_resources import get_distribution, DistributionNotFound
from neon_utils.skills import NeonSkill


class UpdateSkill(NeonSkill):
    def __init__(self):
        super(UpdateSkill, self).__init__(name="NeonUpdates")
        if self.server:
            raise NotImplementedError("Update skill disabled for server use")
        try:
            self.core_package_version = get_distribution("neon-core").version
        except DistributionNotFound:
            raise NotImplementedError("neon-core not found, disabling skill")

    def initialize(self):
        do_update = IntentBuilder("update_neon").require("update-neon").build()
        self.register_intent(do_update, self.handle_update_neon)

        # TODO: Intent to get current core version, allow/deny alphas? DM

        if self.local_config.get("prefFlags", {}).get("notifyRelease", False) and not self.server:
            self.bus.once('mycroft.ready', self._check_latest_release)

    def _check_latest_release(self, message):
        """
        Handles checking for a new release version
        :param message: message object associated with loaded emit
        """
        # TODO: This should check PyPI for versions and check latest alpha/non-alpha versions against this core DM
        pass

    def handle_update_neon(self, message):
        """
        Checks the version file on the git repository associated with this installation and compares to local version.
        If up to date, will check for a new release in the parent NeonGecko repository and notify user. User will
        be given the option to start an update in cases where there is an update available OR no new release available.
        :param message: message object associated with request
        """
        if self.neon_in_request(message) and not self.server:
            self.speak_dialog("check-updates")


def create_skill():
    return UpdateSkill()
