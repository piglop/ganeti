#!/usr/bin/python
#

# Copyright (C) 2006, 2007, 2010 Google Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.


"""Script for unittesting the config module"""


import unittest
import os
import time
import tempfile
import os.path
import socket

from ganeti import bootstrap
from ganeti import config
from ganeti import constants
from ganeti import errors
from ganeti import objects
from ganeti import utils
from ganeti import netutils

import testutils
import mocks


def _StubGetEntResolver():
  return mocks.FakeGetentResolver()


class TestConfigRunner(unittest.TestCase):
  """Testing case for HooksRunner"""
  def setUp(self):
    fd, self.cfg_file = tempfile.mkstemp()
    os.close(fd)
    self._init_cluster(self.cfg_file)

  def tearDown(self):
    try:
      os.unlink(self.cfg_file)
    except OSError:
      pass

  def _get_object(self):
    """Returns a instance of ConfigWriter"""
    cfg = config.ConfigWriter(cfg_file=self.cfg_file, offline=True,
                              _getents=_StubGetEntResolver)
    return cfg

  def _init_cluster(self, cfg):
    """Initializes the cfg object"""
    me = netutils.Hostname()
    ip = constants.IP4_ADDRESS_LOCALHOST

    cluster_config = objects.Cluster(
      serial_no=1,
      rsahostkeypub="",
      highest_used_port=(constants.FIRST_DRBD_PORT - 1),
      mac_prefix="aa:00:00",
      volume_group_name="xenvg",
      drbd_usermode_helper="/bin/true",
      nicparams={constants.PP_DEFAULT: constants.NICC_DEFAULTS},
      tcpudp_port_pool=set(),
      enabled_hypervisors=[constants.HT_FAKE],
      master_node=me.name,
      master_ip="127.0.0.1",
      master_netdev=constants.DEFAULT_BRIDGE,
      cluster_name="cluster.local",
      file_storage_dir="/tmp",
      uid_pool=[],
      )

    master_node_config = objects.Node(name=me.name,
                                      primary_ip=me.ip,
                                      secondary_ip=ip,
                                      serial_no=1,
                                      master_candidate=True)

    bootstrap.InitConfig(constants.CONFIG_VERSION,
                         cluster_config, master_node_config, self.cfg_file)

  def _create_instance(self):
    """Create and return an instance object"""
    inst = objects.Instance(name="test.example.com", disks=[], nics=[],
                            disk_template=constants.DT_DISKLESS,
                            primary_node=self._get_object().GetMasterNode())
    return inst

  def testEmpty(self):
    """Test instantiate config object"""
    self._get_object()

  def testInit(self):
    """Test initialize the config file"""
    cfg = self._get_object()
    self.failUnlessEqual(1, len(cfg.GetNodeList()))
    self.failUnlessEqual(0, len(cfg.GetInstanceList()))

  def testUpdateCluster(self):
    """Test updates on the cluster object"""
    cfg = self._get_object()
    # construct a fake cluster object
    fake_cl = objects.Cluster()
    # fail if we didn't read the config
    self.failUnlessRaises(errors.ConfigurationError, cfg.Update, fake_cl, None)

    cl = cfg.GetClusterInfo()
    # first pass, must not fail
    cfg.Update(cl, None)
    # second pass, also must not fail (after the config has been written)
    cfg.Update(cl, None)
    # but the fake_cl update should still fail
    self.failUnlessRaises(errors.ConfigurationError, cfg.Update, fake_cl, None)

  def testUpdateNode(self):
    """Test updates on one node object"""
    cfg = self._get_object()
    # construct a fake node
    fake_node = objects.Node()
    # fail if we didn't read the config
    self.failUnlessRaises(errors.ConfigurationError, cfg.Update, fake_node,
                          None)

    node = cfg.GetNodeInfo(cfg.GetNodeList()[0])
    # first pass, must not fail
    cfg.Update(node, None)
    # second pass, also must not fail (after the config has been written)
    cfg.Update(node, None)
    # but the fake_node update should still fail
    self.failUnlessRaises(errors.ConfigurationError, cfg.Update, fake_node,
                          None)

  def testUpdateInstance(self):
    """Test updates on one instance object"""
    cfg = self._get_object()
    # construct a fake instance
    inst = self._create_instance()
    fake_instance = objects.Instance()
    # fail if we didn't read the config
    self.failUnlessRaises(errors.ConfigurationError, cfg.Update, fake_instance,
                          None)

    cfg.AddInstance(inst, "my-job")
    instance = cfg.GetInstanceInfo(cfg.GetInstanceList()[0])
    # first pass, must not fail
    cfg.Update(instance, None)
    # second pass, also must not fail (after the config has been written)
    cfg.Update(instance, None)
    # but the fake_instance update should still fail
    self.failUnlessRaises(errors.ConfigurationError, cfg.Update, fake_instance,
                          None)

  def testNICParameterSyntaxCheck(self):
    """Test the NIC's CheckParameterSyntax function"""
    mode = constants.NIC_MODE
    link = constants.NIC_LINK
    m_bridged = constants.NIC_MODE_BRIDGED
    m_routed = constants.NIC_MODE_ROUTED
    CheckSyntax = objects.NIC.CheckParameterSyntax

    CheckSyntax(constants.NICC_DEFAULTS)
    CheckSyntax({mode: m_bridged, link: 'br1'})
    CheckSyntax({mode: m_routed, link: 'default'})
    self.assertRaises(errors.ConfigurationError,
                      CheckSyntax, {mode: '000invalid', link: 'any'})
    self.assertRaises(errors.ConfigurationError,
                      CheckSyntax, {mode: m_bridged, link: None})
    self.assertRaises(errors.ConfigurationError,
                      CheckSyntax, {mode: m_bridged, link: ''})


if __name__ == '__main__':
  testutils.GanetiTestProgram()
