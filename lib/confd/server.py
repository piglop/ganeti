#!/usr/bin/python
#

# Copyright (C) 2009, Google Inc.
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


"""Ganeti configuration daemon server library.

Ganeti-confd is a daemon to query master candidates for configuration values.
It uses UDP+HMAC for authentication with a global cluster key.

"""

import logging
import time

from ganeti import constants
from ganeti import objects
from ganeti import errors
from ganeti import utils
from ganeti import serializer


class ConfdProcessor(object):
  """A processor for confd requests.

  """
  DISPATCH_TABLE = {
  }

  def __init__(self, reader):
    """Constructor for ConfdProcessor

    @type reader: L{ssconf.SimpleConfigReader}
    @param reader: ConfigReader to use to access the config

    """
    self.reader = reader
    self.hmac_key = utils.ReadFile(constants.HMAC_CLUSTER_KEY)

  def ExecQuery(self, payload_in, ip, port):
    """Process a single UDP request from a client.

    @type payload_in: string
    @param payload_in: request raw data
    @type ip: string
    @param ip: source ip address
    @param port: integer
    @type port: source port

    """
    try:
      request = self.ExtractRequest(payload_in)
      reply, rsalt = self.ProcessRequest(request)
      payload_out = self.PackReply(reply, rsalt)
      return payload_out
    except errors.ConfdRequestError, err:
      logging.info('Ignoring broken query from %s:%d: %s' % (ip, port, err))
      return None

  def ExtractRequest(self, payload):
    """Extracts a ConfdRequest object from a serialized hmac signed string.

    This functions also performs signature/timestamp validation.

    """
    current_time = time.time()
    logging.debug("Extracting request with size: %d" % (len(payload)))
    try:
      (message, salt) = serializer.LoadSigned(payload, self.hmac_key)
    except errors.SignatureError, err:
      msg = "invalid signature: %s" % err
      raise errors.ConfdRequestError(msg)
    try:
      message_timestamp = int(salt)
    except (ValueError, TypeError):
      msg = "non-integer timestamp: %s" % salt
      raise errors.ConfdRequestError(msg)

    skew = abs(current_time - message_timestamp)
    if skew > constants.CONFD_MAX_CLOCK_SKEW:
      msg = "outside time range (skew: %d)" % skew
      raise errors.ConfdRequestError(msg)

    try:
      request = objects.ConfdRequest.FromDict(message)
    except AttributeError, err:
      raise errors.ConfdRequestError('%s' % err)

    return request

  def ProcessRequest(self, request):
    """Process one ConfdRequest request, and produce an answer

    @type request: L{objects.ConfdRequest}
    @rtype: (L{objects.ConfdReply}, string)
    @return: tuple of reply and salt to add to the signature

    """
    logging.debug("Processing request: %s" % request)
    if request.protocol != constants.CONFD_PROTOCOL_VERSION:
      msg = "wrong protocol version %d" % request.protocol
      raise errors.ConfdRequestError(msg)

    if request.type not in constants.CONFD_REQS:
      msg = "wrong request type %d" % request.type
      raise errors.ConfdRequestError(msg)

    rsalt = request.rsalt
    if not rsalt:
      msg = "missing requested salt"
      raise errors.ConfdRequestError(msg)

    if request.type not in self.DISPATCH_TABLE:
      answer = 'not implemented'
      status = constants.CONFD_REPL_STATUS_NOTIMPLEMENTED
      reply = objects.ConfdReply(
                protocol=constants.CONFD_PROTOCOL_VERSION,
                status=status,
                answer=answer,
                )
    else:
      # TODO: actually dispatch queries to some classes to handle them
      assert False, "DISPATCH_TABLE is populated but handler is not"

    logging.debug("Sending reply: %s" % reply)

    return (reply, rsalt)

  def PackReply(self, reply, rsalt):
    """Serialize and sign the given reply, with salt rsalt

    @type reply: L{objects.ConfdReply}
    @type rsalt: string

    """
    return serializer.DumpSigned(reply.ToDict(), self.hmac_key, rsalt)

