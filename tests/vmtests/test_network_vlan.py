from . import logger
from .releases import base_vm_classes as relbase
from .releases import centos_base_vm_classes as centos_relbase
from .test_network import TestNetworkBaseTestsAbs

import textwrap
import yaml


class TestNetworkVlanAbs(TestNetworkBaseTestsAbs):
    conf_file = "examples/tests/vlan_network.yaml"
    collect_scripts = TestNetworkBaseTestsAbs.collect_scripts + [
        textwrap.dedent("""
             cd OUTPUT_COLLECT_D
             ip -d link show interface1.2667 |tee ip_link_show_interface1.2667
             ip -d link show interface1.2668 |tee ip_link_show_interface1.2668
             ip -d link show interface1.2669 |tee ip_link_show_interface1.2669
             ip -d link show interface1.2670 |tee ip_link_show_interface1.2670
             """)]

    def get_vlans(self):
        network_state = self.get_network_state()
        logger.debug('get_vlans ns:\n%s', yaml.dump(network_state,
                                                    default_flow_style=False,
                                                    indent=4))
        interfaces = network_state.get('interfaces')
        return [iface for iface in interfaces.values()
                if iface['type'] == 'vlan']

    def test_output_files_exist_vlan(self):
        link_files = ["ip_link_show_%s" % vlan['name']
                      for vlan in self.get_vlans()]
        self.output_files_exist(link_files)

    def test_vlan_installed(self):
        self.assertIn("vlan", self.debian_packages, "vlan deb not installed")

    def test_vlan_enabled(self):
        # we must have at least one
        self.assertGreaterEqual(len(self.get_vlans()), 1)

        # did they get configured?
        for vlan in self.get_vlans():
            link_file = "ip_link_show_" + vlan['name']
            vlan_msg = "vlan.*id " + str(vlan['vlan_id'])
            self.check_file_regex(link_file, vlan_msg)


class CentosTestNetworkVlanAbs(TestNetworkVlanAbs):
    extra_kern_args = "BOOTIF=eth0-d4:be:d9:a8:49:13"
    collect_scripts = TestNetworkVlanAbs.collect_scripts + [
        textwrap.dedent("""
            cd OUTPUT_COLLECT_D
            cp -a /etc/sysconfig/network-scripts .
            cp -a /var/log/cloud-init* .
            cp -a /var/lib/cloud ./var_lib_cloud
            cp -a /run/cloud-init ./run_cloud-init
        """)]

    def test_etc_network_interfaces(self):
        pass

    def test_etc_resolvconf(self):
        pass

    def test_vlan_installed(self):
        """centos has vlan support built-in, no extra packages needed"""
        pass


class TrustyTestNetworkVlan(relbase.trusty, TestNetworkVlanAbs):
    __test__ = True


class TrustyHWEXTestNetworkVlan(relbase.trusty_hwe_x, TestNetworkVlanAbs):
    __test__ = True


class XenialTestNetworkVlan(relbase.xenial, TestNetworkVlanAbs):
    __test__ = True


class ZestyTestNetworkVlan(relbase.zesty, TestNetworkVlanAbs):
    __test__ = True


class ArtfulTestNetworkVlan(relbase.artful, TestNetworkVlanAbs):
    __test__ = True


class BionicTestNetworkVlan(relbase.bionic, TestNetworkVlanAbs):
    __test__ = True


class Centos66TestNetworkVlan(centos_relbase.centos66fromxenial,
                              CentosTestNetworkVlanAbs):
    __test__ = True


class Centos70TestNetworkVlan(centos_relbase.centos70fromxenial,
                              CentosTestNetworkVlanAbs):
    __test__ = True