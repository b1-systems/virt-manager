#
# Copyright (C) 2008 Red Hat, Inc.
# Copyright (C) 2008 Cole Robinson <crobinso@redhat.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
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
#

# pylint: disable=E0611
from gi.repository import GObject
# pylint: enable=E0611

from virtinst import Storage
from virtinst import util

from virtManager.libvirtobject import vmmLibvirtObject
from virtManager.storagevol import vmmStorageVolume


class vmmStoragePool(vmmLibvirtObject):
    __gsignals__ = {
        "refreshed": (GObject.SignalFlags.RUN_FIRST, None, [])
    }

    def __init__(self, conn, backend, key):
        vmmLibvirtObject.__init__(self, conn, backend, key)

        self._uuid = key
        self._active = True

        self._volumes = {}
        self._support_isactive = None

        self.tick()
        self.refresh()

    # Required class methods
    def get_name(self):
        return self._backend.name()
    def _XMLDesc(self, flags):
        return self._backend.XMLDesc(flags)
    def _define(self, xml):
        return self.conn.define_pool(xml)


    def _set_active(self, state):
        if state == self._active:
            return
        self.idle_emit(state and "started" or "stopped")
        self._active = state
        self.refresh_xml()

    def is_active(self):
        return self._active

    def can_change_alloc(self):
        typ = self.get_type()
        return (typ in [Storage.StoragePool.TYPE_LOGICAL])

    def get_uuid(self):
        return self._uuid

    def _kick_conn(self):
        self.conn.schedule_priority_tick(pollpool=True)

    def start(self):
        self._backend.create(0)
        self._kick_conn()
        self.idle_add(self.refresh_xml)

    def stop(self):
        self._backend.destroy()
        self._kick_conn()
        self.idle_add(self.refresh_xml)

    def delete(self, nodelete=True):
        if nodelete:
            self._backend.undefine()
        else:
            self._backend.delete(0)
        self._backend = None
        self._kick_conn()

    def set_autostart(self, value):
        self._backend.setAutostart(value)

    def get_autostart(self):
        return self._backend.autostart()

    def get_target_path(self):
        return util.xpath(self.get_xml(), "/pool/target/path") or ""

    def get_allocation(self):
        return long(util.xpath(self.get_xml(), "/pool/allocation"))
    def get_available(self):
        return long(util.xpath(self.get_xml(), "/pool/available"))
    def get_capacity(self):
        return long(util.xpath(self.get_xml(), "/pool/capacity"))

    def get_pretty_allocation(self):
        return util.pretty_bytes(self.get_allocation())
    def get_pretty_available(self):
        return util.pretty_bytes(self.get_available())
    def get_pretty_capacity(self):
        return util.pretty_bytes(self.get_capacity())

    def get_type(self):
        return util.xpath(self.get_xml(), "/pool/@type")

    def get_volumes(self):
        self.update_volumes()
        return self._volumes

    def get_volume(self, uuid):
        return self._volumes[uuid]

    def _backend_get_active(self):
        if self._support_isactive is None:
            self._support_isactive = self.conn.check_pool_support(
                                        self._backend,
                                        self.conn.SUPPORT_STORAGE_ISACTIVE)

        if not self._support_isactive:
            return True
        return bool(self._backend.isActive())

    def tick(self):
        self._set_active(self._backend_get_active())

    def refresh(self):
        if not self.is_active():
            return

        def cb():
            self.refresh_xml()
            self.update_volumes(refresh=True)
            self.emit("refreshed")

        self._backend.refresh(0)
        self.idle_add(cb)

    def update_volumes(self, refresh=False):
        if not self.is_active():
            self._volumes = {}
            return

        vols = self._backend.listVolumes()
        new_vol_list = {}

        for volname in vols:
            if volname in self._volumes:
                new_vol_list[volname] = self._volumes[volname]
                if refresh:
                    new_vol_list[volname].refresh_xml()
            else:
                new_vol_list[volname] = vmmStorageVolume(self.conn,
                                self._backend.storageVolLookupByName(volname),
                                volname)
        self._volumes = new_vol_list
