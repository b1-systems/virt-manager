# coding=utf-8
#
# Copyright 2011  Red Hat, Inc.
# Cole Robinson <crobinso@redhat.com>
# Marc-André Lureau <marcandre.lureau@redhat.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free  Software Foundation; either version 2 of the License, or
# (at your option)  any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
# MA 02110-1301 USA.

from virtinst import VirtualDevice
from virtinst.xmlbuilder import XMLProperty


class VirtualSmartCardDevice(VirtualDevice):

    virtual_device_type = VirtualDevice.VIRTUAL_DEV_SMARTCARD

    # Default models list
    MODE_DEFAULT = "default"
    MODES = ["passthrough", "host-certificates", "host"]

    TYPE_DEFAULT = "default"
    TYPES = ["tcp", "spicevmc", "default"]


    _XML_PROP_ORDER = ["mode", "type"]

    mode = XMLProperty(xpath="./@mode",
                       default_cb=lambda s: "passthrough",
                       default_name=MODE_DEFAULT)

    def _default_type(self):
        if self.mode == self.MODE_DEFAULT or self.mode == "passthrough":
            return "spicevmc"
        return "tcp"
    type = XMLProperty(xpath="./@type",
                       default_cb=_default_type,
                       default_name=TYPE_DEFAULT)


VirtualSmartCardDevice.register_type()
