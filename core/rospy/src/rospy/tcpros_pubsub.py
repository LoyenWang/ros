# Software License Agreement (BSD License)
#
# Copyright (c) 2008, Willow Garage, Inc.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
#  * Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
#  * Redistributions in binary form must reproduce the above
#    copyright notice, this list of conditions and the following
#    disclaimer in the documentation and/or other materials provided
#    with the distribution.
#  * Neither the name of Willow Garage, Inc. nor the names of its
#    contributors may be used to endorse or promote products derived
#    from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
# FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
# COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
# BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
# ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#
# Revision $Id: transport.py 2941 2008-11-26 03:19:48Z sfkwc $

import logging

from rospy.core import *
from rospy.registration import get_topic_manager
from rospy.tcpros_base import TCPRosTransport, TCPRosTransportProtocol, get_tcpros_server_address, start_tcpros_server
from rospy.transport import ProtocolHandler, INBOUND, OUTBOUND

## Subscription transport implementation for receiving topic data via
## peer-to-peer TCP/IP sockets
class TCPRosSub(TCPRosTransportProtocol):
    """Receive topic data via peer-to-peer TCP/IP sockets"""

    def __init__(self, name, recv_data_class, queue_size=None, buff_size=DEFAULT_BUFF_SIZE):
        super(TCPRosSub, self).__init__(name, recv_data_class, queue_size, buff_size)
        self.direction = INBOUND
    ## @return d dictionary of subscriber fields
    def get_header_fields(self):
        return {'topic': self.name, 'md5sum': self.recv_data_class._md5sum, 'callerid': get_caller_id()}        

#TODO:POLLING: TCPRosPub currently doesn't actually do anything -- not until polling is implemented

## Publisher transport implementation for publishing topic data via
## peer-to-peer TCP/IP sockets. 
class TCPRosPub(TCPRosTransportProtocol):
    """Receive topic data via peer-to-peer TCP/IP sockets"""

    def __init__(self, name, pub_data_class):
        # very small buffer size for publishers as the messages they receive are very small
        super(TCPRosPub, self).__init__(name, None, queue_size=None, buff_size=128)
        self.pub_data_class = pub_data_class
        self.direction = OUTBOUND
        
    def get_header_fields(self):
        return {'type': self.pub_data_class._type, 'md5sum': self.pub_data_class._md5sum, 'callerid': get_caller_id() }

## ROS Protocol handler for TCPROS. Accepts both TCPROS topic
## connections as well as ROS service connections over TCP. TCP server
## socket is run once start_server() is called -- this is implicitly
## called during init_publisher().
class TCPRosHandler(ProtocolHandler):
    ## @param self
    def __init__(self):
        pass
    
    ## stops the TCP/IP server responsible for receiving inbound connections
    ## @param self
    def shutdown(self):
        pass

    ## Create new connection to publisher
    ## @param self
    ## @param topic_name str: topic name
    ## @param pub_uri str: XML-RPC URI of publisher 
    ## @param protocol_params [XmlRpcLegal]: protocol parameters to use for connecting
    def create_connection(self, topic_name, pub_uri, protocol_params):
        
        #Validate protocol params = [TCPROS, address, port]
        if type(protocol_params) != list or len(protocol_params) != 3:
            return 0, "ERROR: invalid TCPROS parameters", 0
        if protocol_params[0] != TCPROS:
            return 0, "INTERNAL ERROR: protocol id is not TCPROS: %s"%id, 0
        id, dest_addr, dest_port = protocol_params

        sub = get_topic_manager().get_subscriber_impl(topic_name)

        #Create connection 
        try:
            protocol = TCPRosSub(topic_name, sub.data_class, \
                                 queue_size=sub.queue_size, buff_size=sub.buff_size)
            conn = TCPRosTransport(protocol, topic_name)
            conn.connect(dest_addr, dest_port, pub_uri)
            thread.start_new_thread(conn.receive_loop, (sub.receive_callback,))
        except TransportInitError, e:
            logging.getLogger('rospy.tcpros').error("unable to create TCPRosSub: %s", e)
            return 0, "Internal error creating inbound TCP connection for [%s]: %s"%(topic_name, e), -1

        # Attach connection to _SubscriberImpl
        if sub.add_connection(conn): #pass tcp connection to handler
            return 1, "Connected topic[%s]. Transport impl[%s]"%(topic_name, conn.__class__.__name__), dest_port
        else:
            conn.close()
            return 0, "ERROR: Race condition failure: duplicate topic subscriber [%s] was created"%(topic_name), 0

    ## @param self
    ## @param protocol str: name of protocol
    ## @return bool: True if protocol is supported
    def supports(self, protocol):
        return protocol == TCPROS
    
    ## @param self
    def get_supported(self):
        return [[TCPROS]]
        
    ## Initialize this node to receive an inbound TCP connection,
    ## i.e. startup a TCP server if one is not already running.
    ## @param self
    ## @param topic_name str
    ## @param protocol [str, value*]: negotiated protocol
    ## parameters. protocol[0] must be the string 'TCPROS'
    ## @return (int, str, list): (code, msg, [TCPROS, addr, port])
    def init_publisher(self, topic_name, protocol): 
        if protocol[0] != TCPROS:
            return 0, "Internal error: protocol does not match TCPROS: %s"%protocol, []
        start_tcpros_server()
        addr, port = get_tcpros_server_address()
        return 1, "ready on %s:%s"%(addr, port), [TCPROS, addr, port]

## Process incoming topic connection. Reads in topic name from
## handshake and creates the appropriate TCPRosPub handler for the
## connection.
## @param sock socket: socket connection
## @param client_addr (str, int): client address
## @param header dict: key/value pairs from handshake header
## @return str: error string or None 
def topic_connection_handler(sock, client_addr, header):
    for required in ['topic', 'md5sum', 'callerid']:
        if not required in header:
            return "Missing required '%s' field"%required
    else:
        topic_name = header['topic']
        md5sum = header['md5sum']
        tm = get_topic_manager()
        topic = tm.get_publisher_impl(topic_name)
        if not topic:
            return "[%s] is not a publisher of  [%s]"%(get_caller_id(), topic_name)
        elif md5sum != TOPIC_ANYTYPE and md5sum != topic.data_class._md5sum:
            return "md5sums do not match: [%s] vs. [%s]"%(md5sum, topic.data_class._md5sum)
        else:
            #TODO:POLLING if polling header is present, have to spin up receive loop as well
            protocol = TCPRosPub(topic.name, topic.data_class)
            transport = TCPRosTransport(protocol, topic_name)
            transport.set_socket(sock, header['callerid'])
            transport.write_header()
            topic.add_connection(transport)
