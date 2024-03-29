# <img src='./logo.svg' card_color="#FF8600" width="50" style="vertical-align:bottom">Neon Updates

## Summary

Skill to update Python packages, configuration, and to create new boot media.

## Description

The update skill provides intents for the user to manage device updates, including
core packages, skills, configuration, and creation of new boot media.

### Software Updates
This skill can be used to check for software updates and to start the update
process on supported devices. For most devices, updates will take 10-30 minutes,
and you will not be able to use your device while it is updating.

### Configuration Updates
For supported distributions, this skill allows getting updated default configuration.
This can be useful for resetting skills configuration to the latest default, or for
troubleshooting after making manual configuration changes.

### Create New Media
For supported distributions, this skill is able to create a new boot drive from
a clean image, similar to what would be distributed with a new device. This involves
downloading a new image and then writing it to an available storage device. This
is a multi-step process.
1. An operating system image is downloaded. Depending on internet connection 
   speeds, this generally takes about 15-20 minutes.
2. After user confirmation, this image is written to a non-boot drive connected
   to the device. **All existing on the new boot drive is lost**. This generally
   takes about 30-45 minutes.
3. After this is complete, the device is shut down so the user may unplug the old
   drive and boot the new one.

## Examples

- Check for updates.
- Do you have any updates?
- Update my default configuration.
- Create a new boot drive.
- Switch to beta releases.
- Change to stable updates.

## Contact Support

Use the [link](https://neongecko.com/ContactUs) or [submit an issue on GitHub](https://help.github.com/en/articles/creating-an-issue)

## Credits
[NeonDaniel](https://github.com/NeonDaniel)
[NeonGeckoCom](https://github.com/NeonGeckoCom)

## Category
**Information**

## Tags
#NeonGecko Original
#NeonAI
#Update
