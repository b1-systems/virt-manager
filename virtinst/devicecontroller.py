#
# Copyright 2010  Red Hat, Inc.
# Cole Robinson <crobinso@redhat.com>
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


class VirtualController(VirtualDevice):
    virtual_device_type = VirtualDevice.VIRTUAL_DEV_CONTROLLER

    TYPE_IDE             = "ide"
    TYPE_FDC             = "fdc"
    TYPE_SCSI            = "scsi"
    TYPE_SATA            = "sata"
    TYPE_VIRTIOSERIAL    = "virtio-serial"
    TYPE_USB             = "usb"
    TYPE_PCI             = "pci"
    TYPE_CCID            = "ccid"
    TYPES = [TYPE_IDE, TYPE_FDC,
             TYPE_SCSI, TYPE_SATA,
             TYPE_VIRTIOSERIAL, TYPE_USB,
             TYPE_PCI, TYPE_CCID]

    @staticmethod
    def pretty_type(ctype):
        pretty_mappings = {
            VirtualController.TYPE_IDE           : "IDE",
            VirtualController.TYPE_FDC           : "Floppy",
            VirtualController.TYPE_SCSI          : "SCSI",
            VirtualController.TYPE_SATA          : "SATA",
            VirtualController.TYPE_VIRTIOSERIAL  : "Virtio Serial",
            VirtualController.TYPE_USB           : "USB",
            VirtualController.TYPE_PCI           : "PCI",
            VirtualController.TYPE_CCID          : "CCID",
       }

        if ctype not in pretty_mappings:
            return ctype
        return pretty_mappings[ctype]

    @staticmethod
    def get_usb2_controllers(conn):
        ret = []
        ctrl = VirtualController(conn)
        ctrl.type = "usb"
        ctrl.model = "ich9-ehci1"
        ret.append(ctrl)

        ctrl = VirtualController(conn)
        ctrl.type = "usb"
        ctrl.model = "ich9-uhci1"
        ctrl.master_startport = 0
        ret.append(ctrl)

        ctrl = VirtualController(conn)
        ctrl.type = "usb"
        ctrl.model = "ich9-uhci2"
        ctrl.master_startport = 2
        ret.append(ctrl)

        ctrl = VirtualController(conn)
        ctrl.type = "usb"
        ctrl.model = "ich9-uhci3"
        ctrl.master_startport = 4
        ret.append(ctrl)
        return ret


    _XML_PROP_ORDER = ["type", "index", "model", "master_startport"]

    type = XMLProperty(xpath="./@type")
    model = XMLProperty(xpath="./@model")
    vectors = XMLProperty(xpath="./@vectors", is_int=True)
    ports = XMLProperty(xpath="./@ports", is_int=True)
    master_startport = XMLProperty(xpath="./master/@startport", is_int=True)

    index = XMLProperty(xpath="./@index", is_int=True, default_cb=lambda s: 0)

VirtualController.register_type()
