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

import glob
import traceback
import unittest

import virtinst

from tests import utils

conn = utils.open_testdriver()
kvmconn = utils.open_testkvmdriver()


def sanitize_file_xml(xml):
    # s/"/'/g from generated XML, matches what libxml dumps out
    # This won't work all the time, but should be good enough for testing
    return xml.replace("'", "\"")


class XMLParseTest(unittest.TestCase):

    def _roundtrip_compare(self, filename):
        expectXML = sanitize_file_xml(file(filename).read())
        guest = virtinst.Guest(conn, parsexml=expectXML)
        actualXML = guest.get_xml_config()
        utils.diff_compare(actualXML, expect_out=expectXML)

    def _alter_compare(self, actualXML, outfile):
        utils.diff_compare(actualXML, outfile)
        utils.test_create(conn, actualXML)

    def testRoundTrip(self):
        """
        Make sure parsing doesn't output different XML
        """
        exclude = ["misc-xml-escaping.xml"]
        failed = False
        error = ""
        for f in glob.glob("tests/xmlconfig-xml/*.xml"):
            if [e for e in exclude if f.endswith(e)]:
                continue

            try:
                self._roundtrip_compare(f)
            except Exception:
                failed = True
                error += "%s:\n%s\n" % (f, "".join(traceback.format_exc()))

        if failed:
            raise AssertionError("Roundtrip parse tests failed:\n%s" % error)

    def _set_and_check(self, obj, param, initval, *args):
        """
        Check expected initial value obj.param == initval, then
        set newval, and make sure it is returned properly
        """
        curval = getattr(obj, param)
        self.assertEqual(initval, curval)

        for newval in args:
            setattr(obj, param, newval)
            curval = getattr(obj, param)
            self.assertEqual(newval, curval)

    def _make_checker(self, obj):
        def check(name, initval, *args):
            return self._set_and_check(obj, name, initval, *args)
        return check

    def _get_test_content(self, basename, kvm=False):
        infile = "tests/xmlparse-xml/%s-in.xml" % basename
        outfile = "tests/xmlparse-xml/%s-out.xml" % basename
        guest = virtinst.Guest(kvm and kvmconn or conn,
                               parsexml=file(infile).read())
        return guest, outfile

    def test000ClearProps(self):
        # pylint: disable=W0212
        # Access to protected member, needed to unittest stuff
        virtinst.xmlbuilder._seenprops = []

    def testAlterGuest(self):
        """
        Test changing Guest() parameters after parsing
        """
        guest, outfile = self._get_test_content("change-guest")

        check = self._make_checker(guest)
        check("name", "TestGuest", "change_name")
        check("description", None, "Hey desc changed&")
        check("vcpus", 5, 12)
        check("curvcpus", None, 10)
        check("cpuset", "1-3", "1-8,^6", "1-5,15")
        check("maxmemory", 409600, 512000)
        check("memory", 204800, 1024000)
        check("maxmemory", 1024000, 2048000)
        check("uuid", "12345678-1234-1234-1234-123456789012",
                      "11111111-2222-3333-4444-555555555555")
        check("emulator", "/usr/lib/xen/bin/qemu-dm", "/usr/binnnn/fooemu")
        check("hugepage", False, True)
        check("type", "kvm", "test")
        check("bootloader", None, "pygrub")
        check("on_poweroff", "destroy", "restart")
        check("on_reboot", "restart", "destroy")
        check("on_crash", "restart", "destroy")

        check = self._make_checker(guest.clock)
        check("offset", "utc", "localtime")

        check = self._make_checker(guest.seclabel)
        check("type", "static", "static")
        check("model", "selinux", "apparmor")
        check("label", "foolabel", "barlabel")
        check("imagelabel", "imagelabel", "fooimage")
        check("relabel", None, True)

        check = self._make_checker(guest.os)
        check("os_type", "hvm", "xen")
        check("arch", "i686", None)
        check("machine", "foobar", "pc-0.11")
        check("loader", None, "/foo/loader")
        check("init", None, "/sbin/init")
        check("bootorder", ["hd"], ["fd"])
        check("enable_bootmenu", None, False)
        check("useserial", None, True)
        check("kernel", None)
        check("initrd", None)
        check("kernel_args", None)

        check = self._make_checker(guest.features)
        check("acpi", True, False)
        check("apic", True, False)
        check("pae", False, True)

        def feature_checker(prop, origval, newval):
            self.assertEqual(guest.features[prop], origval)
            guest.features[prop] = newval
            self.assertEqual(guest.features[prop], newval)

        feature_checker("acpi", False, False)
        feature_checker("apic", False, True)
        feature_checker("pae", True, False)

        check = self._make_checker(guest.cpu)
        check("match", "exact", "strict")
        check("model", "footest", "qemu64")
        check("vendor", "Intel", "qemuvendor")
        check("threads", 2, 1)
        check("cores", 5, 3)
        guest.cpu.sockets = 4.0
        check("sockets", 4)

        check = self._make_checker(guest.cpu.features[0])
        check("name", "x2apic")
        check("policy", "force", "disable")
        rmfeat = guest.cpu.features[3]
        guest.cpu.remove_feature(rmfeat)
        self.assertEqual(rmfeat.get_xml_config(),
                          """<feature name="foo" policy="bar"/>""")
        guest.cpu.add_feature("addfeature")

        check = self._make_checker(guest.numatune)
        check("memory_mode", "interleave", "strict", None)
        check("memory_nodeset", "1-5,^3,7", "2,4,6")

        check = self._make_checker(guest.get_devices("memballoon")[0])
        check("model", "virtio", "none")

        self._alter_compare(guest.get_xml_config(), outfile)

    def testAlterMinimalGuest(self):
        guest, outfile = self._get_test_content("change-minimal-guest")

        check = self._make_checker(guest.features)
        check("acpi", False, True)
        check("pae", False)
        self.assertTrue(
            guest.features.get_xml_config().startswith("<features"))

        check = self._make_checker(guest.clock)
        check("offset", None, "utc")
        self.assertTrue(guest.clock.get_xml_config().startswith("<clock"))

        check = self._make_checker(guest.seclabel)
        check("model", None, "testSecurity")
        check("type", None, "static")
        check("label", None, "frob")
        self.assertTrue(
            guest.seclabel.get_xml_config().startswith("<seclabel"))

        check = self._make_checker(guest.cpu)
        check("model", None, "foobar")
        check("cores", None, 4)
        guest.cpu.add_feature("x2apic", "forbid")
        guest.cpu.set_topology_defaults(guest.vcpus)
        self.assertTrue(guest.cpu.get_xml_config().startswith("<cpu"))

        self.assertTrue(guest.os.get_xml_config().startswith("<os"))

        self._alter_compare(guest.get_xml_config(), outfile)

    def testAlterBootMulti(self):
        guest, outfile = self._get_test_content("change-boot-multi")

        check = self._make_checker(guest.os)
        check("bootorder", ['hd', 'fd', 'cdrom', 'network'], ["cdrom"])
        check("enable_bootmenu", False, True)
        check("kernel", None, "foo.img")
        check("initrd", None, "bar.img")
        check("dtb", None, "/baz.dtb")
        check("kernel_args", None, "ks=foo.ks")

        self._alter_compare(guest.get_xml_config(), outfile)

    def testAlterBootKernel(self):
        guest, outfile = self._get_test_content("change-boot-kernel")

        check = self._make_checker(guest.os)
        check("bootorder", [], ["network", "hd", "fd"])
        check("enable_bootmenu", None)
        check("kernel", "/boot/vmlinuz", None)

        check("initrd", "/boot/initrd", None)
        check("kernel_args", "location", None)

        self._alter_compare(guest.get_xml_config(), outfile)

    def testAlterCpuMode(self):
        guest, outfile = self._get_test_content("change-cpumode")

        check = self._make_checker(guest.cpu)
        check("mode", "host-passthrough", "custom")
        check("mode", "custom", "host-model")
        # mode will be "custom"
        check("model", None, "qemu64")

        self._alter_compare(guest.get_xml_config(), outfile)

    def testAlterDisk(self):
        """
        Test changing VirtualDisk() parameters after parsing
        """
        guest, outfile = self._get_test_content("change-disk")

        # Set size up front. VirtualDisk validation is kind of
        # convoluted. If trying to change a non-existing one and size wasn't
        # already specified, we will error out.
        disks = guest.get_devices("disk")
        disk1 = disks[0]
        disk1.size = 1
        disk3 = disks[2]
        disk3.size = 1
        disk6 = disks[5]
        disk6.size = 1

        check = self._make_checker(disk1)
        check("path", "/tmp/test.img", "/dev/loop0")
        disk1.sync_path_props()
        check("driver_name", None, "test")
        check("driver_type", None, "raw")
        check("serial", "WD-WMAP9A966149", "frob")

        check = self._make_checker(disk3)
        check("type", "block", "dir", "file", "block")
        check("path", "/dev/loop0", None)
        disk3.sync_path_props()
        check("device", "cdrom", "floppy")
        check("read_only", True, False)
        check("target", "hdc", "fde")
        check("bus", "ide", "fdc")
        check("error_policy", "stop", None)

        check = self._make_checker(disk6)
        check("path", None, "/dev/default-pool/default-vol")
        disk6.sync_path_props()
        check("shareable", False, True)
        check("driver_cache", None, "writeback")
        check("driver_io", None, "threads")
        check("driver_io", "threads", "native")
        check("iotune_ris", 1, 0)
        check("iotune_rbs", 2, 0)
        check("iotune_wis", 3, 0)
        check("iotune_wbs", 4, 0)
        check("iotune_tis", None, 5)
        check("iotune_tbs", None, 6)


        self._alter_compare(guest.get_xml_config(), outfile)

    def testSingleDisk(self):
        xml = ("""<disk type="file" device="disk"><source file="/a.img"/>"""
               """<target dev="hda" bus="ide"/></disk>""")
        d = virtinst.VirtualDisk(conn, parsexml=xml)
        self._set_and_check(d, "target", "hda", "hdb")
        self.assertEqual(xml.replace("hda", "hdb"), d.get_xml_config())

    def testAlterChars(self):
        guest, outfile = self._get_test_content("change-chars")

        serial1     = guest.get_devices("serial")[0]
        serial2     = guest.get_devices("serial")[1]
        parallel1   = guest.get_devices("parallel")[0]
        parallel2   = guest.get_devices("parallel")[1]
        console1    = guest.get_devices("console")[0]
        console2    = guest.get_devices("console")[1]
        channel1    = guest.get_devices("channel")[0]
        channel2    = guest.get_devices("channel")[1]

        check = self._make_checker(serial1)
        check("type", "null", "udp")
        check("bind_host", None, "example.com")
        check("bind_port", None, 66)
        check("source_host", None, "example.com.uk")
        check("source_port", None, 77)

        check = self._make_checker(serial2)
        check("type", "tcp")
        check("protocol", "telnet", "raw")
        check("source_mode", "bind", "connect")

        check = self._make_checker(parallel1)
        check("source_mode", "bind")
        check("source_path", "/tmp/foobar", None)
        check("type", "unix", "pty")

        check = self._make_checker(parallel2)
        check("type", "udp")
        check("bind_port", 1111, 1357)
        check("bind_host", "my.bind.host", "my.foo.host")
        check("source_mode", "connect")
        check("source_port", 2222, 7777)
        check("source_host", "my.source.host", "source.foo.host")

        check = self._make_checker(console1)
        check("type", "pty")
        check("target_type", None)

        check = self._make_checker(console2)
        check("type", "file")
        check("source_path", "/tmp/foo.img", None)
        check("source_path", None, "/root/foo")
        check("target_type", "virtio")

        check = self._make_checker(channel1)
        check("type", "pty")
        check("target_type", "virtio", "bar", "virtio")
        check("target_name", "foo.bar.frob", "test.changed")

        check = self._make_checker(channel2)
        check("type", "unix", "foo", "unix")
        check("target_type", "guestfwd")
        check("target_address", "1.2.3.4", "5.6.7.8")
        check("target_port", 4567, 1199)

        self._alter_compare(guest.get_xml_config(), outfile)

    def testAlterControllers(self):
        guest, outfile = self._get_test_content("change-controllers")

        dev1 = guest.get_devices("controller")[0]
        dev2 = guest.get_devices("controller")[1]
        dev3 = guest.get_devices("controller")[2]
        dev4 = guest.get_devices("controller")[3]

        check = self._make_checker(dev1)
        check("type", "ide")
        check("index", 3, 1)

        check = self._make_checker(dev2)
        check("type", "virtio-serial")
        check("index", 0, 7)
        check("ports", 32, 5)
        check("vectors", 17, None)

        check = self._make_checker(dev3)
        check("type", "scsi")
        check("index", 1, 2)

        check = self._make_checker(dev4)
        check("type", "usb", "foo", "usb")
        check("index", 3, 9)
        check("model", "ich9-ehci1", "ich9-uhci1")
        check("master_startport", 4, 2)

        self._alter_compare(guest.get_xml_config(), outfile)

    def testAlterNics(self):
        guest, outfile = self._get_test_content("change-nics")

        dev1 = guest.get_devices("interface")[0]
        dev2 = guest.get_devices("interface")[1]
        dev3 = guest.get_devices("interface")[2]
        dev4 = guest.get_devices("interface")[3]
        dev5 = guest.get_devices("interface")[4]

        check = self._make_checker(dev1)
        check("type", "user")
        check("model", None, "testmodel")
        check("bridge", None, "br0")
        check("network", None, "route")
        check("macaddr", "22:11:11:11:11:11", "AA:AA:AA:AA:AA:AA")
        check("filterref", None, "foo")
        self.assertEqual(dev1.get_source(), None)

        check = self._make_checker(dev2)
        self.assertEqual(dev2.get_source(), "default")
        check("network", "default", None)
        check("bridge", None, "newbr0")
        check("type", "network", "bridge")
        check("model", "e1000", "virtio")

        check = self._make_checker(dev3)
        check("type", "bridge")
        check("bridge", "foobr0", "newfoo0")
        check("network", None, "default")
        check("macaddr", "22:22:22:22:22:22")
        check("target_dev", None, "test1")
        self.assertEqual(dev3.get_source(), "newfoo0")

        check = self._make_checker(dev4)
        check("type", "ethernet")
        check("source_dev", "eth0", "eth1")
        check("target_dev", "nic02", "nic03")
        check("target_dev", "nic03", None)
        self.assertEqual(dev4.get_source(), "eth1")

        check = self._make_checker(dev5)
        check("type", "direct")
        check("source_dev", "eth0.1")
        check("source_mode", "vepa", "bridge")

        virtualport = dev5.virtualport
        check = self._make_checker(virtualport)
        check("type", "802.1Qbg", "foo", "802.1Qbg")
        check("managerid", 12, 11)
        check("typeid", 1193046, 1193047)
        check("typeidversion", 1, 2)
        check("instanceid", "09b11c53-8b5c-4eeb-8f00-d84eaa0aaa3b",
                            "09b11c53-8b5c-4eeb-8f00-d84eaa0aaa4f")

        self._alter_compare(guest.get_xml_config(), outfile)

    def testAlterInputs(self):
        guest, outfile = self._get_test_content("change-inputs")

        dev1 = guest.get_devices("input")[0]
        dev2 = guest.get_devices("input")[1]

        check = self._make_checker(dev1)
        check("type", "mouse", "tablet")
        check("bus", "ps2", "usb")

        check = self._make_checker(dev2)
        check("type", "tablet", "mouse")
        check("bus", "usb", "xen")
        check("bus", "xen", "usb")

        self._alter_compare(guest.get_xml_config(), outfile)

    def testAlterGraphics(self):
        guest, outfile = self._get_test_content("change-graphics")

        dev1 = guest.get_devices("graphics")[0]
        dev2 = guest.get_devices("graphics")[1]
        dev3 = guest.get_devices("graphics")[2]
        dev4 = guest.get_devices("graphics")[3]
        dev5 = guest.get_devices("graphics")[4]
        dev6 = guest.get_devices("graphics")[5]

        check = self._make_checker(dev1)
        check("type", "vnc")
        check("passwd", "foobar", "newpass")
        check("port", 100, 6000)
        check("listen", "0.0.0.0", "1.2.3.4")
        check("keymap", None, "en-us")

        check = self._make_checker(dev2)
        check("type", "sdl")
        check("xauth", "/tmp/.Xauthority", "fooauth")
        check("display", "1:2", "6:1")

        check = self._make_checker(dev3)
        check("type", "rdp", "vnc")

        check = self._make_checker(dev4)
        check("type", "vnc")
        check("port", -1)
        check("socket", "/tmp/foobar", "/var/lib/libvirt/socket/foo")

        check = self._make_checker(dev5)
        check("autoport", True, False)

        check = self._make_checker(dev6)
        check("type", "spice")
        check("passwd", "foobar", "newpass")
        check("port", 100, 6000)
        check("tlsPort", 101, 6001)
        check("listen", "0.0.0.0", "1.2.3.4")
        check("channel_inputs_mode", "insecure", "secure")
        check("channel_main_mode", "secure", "any")
        check("channel_record_mode", "any", "insecure")
        check("channel_display_mode", "any", "secure")
        check("channel_cursor_mode", "any", "any")
        check("channel_playback_mode", "any", "insecure")
        check("passwdValidTo", "2010-04-09T15:51:00", "2011-01-07T19:08:00")

        self._alter_compare(guest.get_xml_config(), outfile)

    def testAlterVideos(self):
        guest, outfile = self._get_test_content("change-videos")

        dev1 = guest.get_devices("video")[0]
        dev2 = guest.get_devices("video")[1]
        dev3 = guest.get_devices("video")[2]

        check = self._make_checker(dev1)
        check("model", "vmvga", "vga")
        check("vram", None, 1000)
        check("heads", None, 1)

        check = self._make_checker(dev2)
        check("model", "cirrus", "vmvga")
        check("vram", 10240, None)
        check("heads", 3, 5)

        check = self._make_checker(dev3)
        check("model", "cirrus", "cirrus", "qxl")
        check("ram", None, 100)

        self._alter_compare(guest.get_xml_config(), outfile)

    def testAlterHostdevs(self):
        infile  = "tests/xmlparse-xml/change-hostdevs-in.xml"
        outfile = "tests/xmlparse-xml/change-hostdevs-out.xml"
        guest = virtinst.Guest(conn,
                               parsexml=file(infile).read())

        dev1 = guest.get_devices("hostdev")[0]
        dev2 = guest.get_devices("hostdev")[1]
        dev3 = guest.get_devices("hostdev")[2]

        check = self._make_checker(dev1)
        check("type", "usb", "foo", "usb")
        check("managed", True, False)
        check("mode", "subsystem", None)
        check("vendor", "0x4321", "0x1111")
        check("product", "0x1234", "0x2222")
        check("bus", None, "1")
        check("device", None, "2")

        check = self._make_checker(dev2)
        check("type", "usb")
        check("managed", False, True)
        check("mode", "capabilities", "subsystem")
        check("bus", "0x12", "0x56")
        check("device", "0x34", "0x78")

        check = self._make_checker(dev3)
        check("type", "pci")
        check("managed", True, True)
        check("mode", "subsystem", "subsystem")
        check("domain", "0x0", "0x4")
        check("bus", "0x1", "0x5")
        check("slot", "0x2", "0x6")
        check("function", "0x3", "0x7")

        self._alter_compare(guest.get_xml_config(), outfile)

    def testAlterWatchdogs(self):
        guest, outfile = self._get_test_content("change-watchdogs")

        dev1 = guest.get_devices("watchdog")[0]
        check = self._make_checker(dev1)
        check("model", "ib700", "i6300esb")
        check("action", "none", "poweroff")

        self._alter_compare(guest.get_xml_config(), outfile)

    def testAlterFilesystems(self):
        guest, outfile = self._get_test_content("change-filesystems")

        dev1 = guest.get_devices("filesystem")[0]
        dev2 = guest.get_devices("filesystem")[1]
        dev3 = guest.get_devices("filesystem")[2]
        dev4 = guest.get_devices("filesystem")[3]

        check = self._make_checker(dev1)
        check("type", None, "mount")
        check("mode", None, "passthrough")
        check("driver", "handle", None)
        check("wrpolicy", None, None)
        check("source", "/foo/bar", "/new/path")
        check("target", "/bar/baz", "/new/target")

        check = self._make_checker(dev2)
        check("type", "template")
        check("mode", None, "mapped")
        check("source", "template_fedora", "template_new")
        check("target", "/bar/baz")

        check = self._make_checker(dev3)
        check("type", "mount", None)
        check("mode", "squash", None)
        check("driver", "path", "handle")
        check("wrpolicy", "immediate", None)
        check("readonly", False, True)

        check = self._make_checker(dev4)
        check("type", "mount", None)
        check("mode", "mapped", None)
        check("driver", "path", "handle")
        check("wrpolicy", None, "immediate")
        check("readonly", False, True)

        self._alter_compare(guest.get_xml_config(), outfile)

    def testAlterSounds(self):
        infile  = "tests/xmlparse-xml/change-sounds-in.xml"
        outfile = "tests/xmlparse-xml/change-sounds-out.xml"
        guest = virtinst.Guest(conn,
                               parsexml=file(infile).read())

        dev1 = guest.get_devices("sound")[0]
        dev2 = guest.get_devices("sound")[1]
        dev3 = guest.get_devices("sound")[2]

        check = self._make_checker(dev1)
        check("model", "sb16", "ac97")

        check = self._make_checker(dev2)
        check("model", "es1370", "es1370")

        check = self._make_checker(dev3)
        check("model", "ac97", "sb16")

        self._alter_compare(guest.get_xml_config(), outfile)

    def testAlterAddr(self):
        guest, outfile = self._get_test_content("change-addr")

        dev1 = guest.get_devices("disk")[0]
        dev2 = guest.get_devices("controller")[0]
        dev3 = guest.get_devices("channel")[0]
        dev4 = guest.get_devices("disk")[1]

        check = self._make_checker(dev1.address)
        check("type", "drive", "pci")
        check("type", "pci", "drive")
        check("controller", 3, 1)
        check("bus", 5, 4)
        check("unit", 33, 32)
        check = self._make_checker(dev1.alias)
        check("name", "foo2", None)

        check = self._make_checker(dev2.address)
        dev2.address.domain = "0x0010"
        self.assertEqual(dev2.address.domain, 16)
        check("type", "pci")
        check("domain", 16, 1)
        check("bus", 0, 4)
        check("slot", 4, 10)
        check("function", 7, 6)
        check = self._make_checker(dev2.alias)
        check("name", None, "frob")

        check = self._make_checker(dev3.address)
        check("type", "virtio-serial")
        check("controller", 0)
        check("bus", 0)
        check("port", 2, 4)
        check = self._make_checker(dev3.alias)
        check("name", "channel0", "channel1")

        dev4.address.clear()

        self._alter_compare(guest.get_xml_config(), outfile)

    def testAlterSmartCard(self):
        guest, outfile = self._get_test_content("change-smartcard")

        dev1 = guest.get_devices("smartcard")[0]
        dev2 = guest.get_devices("smartcard")[1]

        check = self._make_checker(dev1)
        check("type", None, "tcp")

        check = self._make_checker(dev2)
        check("mode", "passthrough", "host")
        check("type", "spicevmc", None)

        self._alter_compare(guest.get_xml_config(), outfile)

    def testAlterRedirdev(self):
        guest, outfile = self._get_test_content("change-redirdev")

        dev1 = guest.get_devices("redirdev")[0]
        dev2 = guest.get_devices("redirdev")[1]

        check = self._make_checker(dev1)
        check("bus", "usb", "baz", "usb")
        check("host", "foo", "bar")
        check("service", 12, 42)

        check = self._make_checker(dev2)
        check("type", "tcp", "spicevmc")

        self._alter_compare(guest.get_xml_config(), outfile)

    def testAlterTPM(self):
        guest, outfile = self._get_test_content("change-tpm")

        dev1 = guest.get_devices("tpm")[0]

        check = self._make_checker(dev1)
        check("type", "passthrough", "foo", "passthrough")
        check("model", "tpm-tis", "tpm-tis")
        check("device_path", "/dev/tpm0", "frob")

        self._alter_compare(guest.get_xml_config(), outfile)

    def testConsoleCompat(self):
        guest, outfile = self._get_test_content("console-compat")

        dev1 = guest.get_devices("console")[0]
        check = self._make_checker(dev1)
        check("source_path", "/dev/pts/4")

        self._alter_compare(guest.get_xml_config(), outfile)

    def testAddRemoveDevices(self):
        guest, outfile = self._get_test_content("add-devices")

        rmdev = guest.get_devices("disk")[2]
        guest.remove_device(rmdev)

        adddev = virtinst.VirtualNetworkInterface(conn=conn)
        adddev.type = "network"
        adddev.network = "default"
        adddev.macaddr = "1A:2A:3A:4A:5A:6A"

        guest.add_device(virtinst.VirtualWatchdog(conn))

        guest.add_device(adddev)
        guest.remove_device(adddev)
        guest.add_device(adddev)

        guest.add_device(virtinst.VirtualAudio(conn,
            parsexml="""<sound model='pcspk'/>"""))

        self._alter_compare(guest.get_xml_config(), outfile)

    def testChangeKVMMedia(self):
        guest, outfile = self._get_test_content("change-media", kvm=True)

        disk = guest.get_devices("disk")[0]
        check = self._make_checker(disk)
        check("path", None, "/dev/default-pool/default-vol")
        disk.sync_path_props()

        disk = guest.get_devices("disk")[1]
        check = self._make_checker(disk)
        check("path", None, "/dev/default-pool/default-vol")
        check("path", "/dev/default-pool/default-vol", "/dev/disk-pool/diskvol1")
        disk.sync_path_props()

        disk = guest.get_devices("disk")[2]
        check = self._make_checker(disk)
        check("path", None, "/dev/disk-pool/diskvol1")
        disk.sync_path_props()

        disk = guest.get_devices("disk")[3]
        check = self._make_checker(disk)
        check("path", None, "/dev/default-pool/default-vol")
        disk.sync_path_props()

        disk = guest.get_devices("disk")[4]
        check = self._make_checker(disk)
        check("path", None, "/dev/disk-pool/diskvol1")
        disk.sync_path_props()

        self._alter_compare(guest.get_xml_config(), outfile)

    def testChangeSnapshot(self):
        basename = "change-snapshot"
        infile = "tests/xmlparse-xml/%s-in.xml" % basename
        outfile = "tests/xmlparse-xml/%s-out.xml" % basename
        snap = virtinst.DomainSnapshot(conn, parsexml=file(infile).read())

        check = self._make_checker(snap)
        check("name", "offline-root-child1", "name-foo")
        check("state", "shutoff", "somestate")
        check("description", "offline desk", "foo\nnewline\n   indent")
        check("parent", "offline-root", "newparent")
        check("creationTime", 1375905916, 1234)

        utils.diff_compare(snap.get_xml_config(), outfile)

    def testzzzzCheckProps(self):
        # pylint: disable=W0212
        # Access to protected member, needed to unittest stuff

        # If a certain environment variable is set, XMLBuilder tracks
        # every property registered and every one of those that is
        # actually altered. The test suite sets that env variable.
        #
        # test000ClearProps resets the 'set' list, and this test
        # ensures that every property we know about has been touched
        # by one of the above tests.
        fail = [p for p in virtinst.xmlbuilder._allprops
                if p not in virtinst.xmlbuilder._seenprops]
        try:
            self.assertEqual([], fail)
        except AssertionError:
            msg = "".join(traceback.format_exc()) + "\n\n"
            msg += ("This means that there are XML properties that are\n"
                    "untested in tests/xmlparse.py. This could be caused\n"
                    "by a previous test suite failure, or if you added\n"
                    "a new property and didn't add corresponding tests!")
            self.fail(msg)

if __name__ == "__main__":
    unittest.main()
