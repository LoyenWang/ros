#!/usr/bin/env python
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
# Revision $Id: tcpros.py 1636 2008-07-28 20:58:29Z sfkwc $

import roslib; roslib.load_manifest('test_roslaunch')

import os, sys, unittest

import rostest
import roslaunch.xmlloader 

## Fake RosLaunch object
class RosLaunchMock(object):
    def __init__(self):
        self.nodes_core = []
        self.nodes = []
        self.tests = []
        self.params = []
        self.executables = []        
        self.clear_params = []        
        self.machines = []
        self.master = None
        
    def set_master(self, m):
        self.master = m
    def add_machine(self, m):
        self.machines.append(m)
    def add_node(self, n, core=False):
        if not core:
            self.nodes.append(n)
        else:
            self.nodes_core.append(n)

    def add_test(self, t):
        self.tests.append(t)        
    def add_executable(self, t):
        self.executables.append(t)        

    def add_param(self, p):
        self.params.append(p)        
    def add_clear_param(self, param):
        self.clear_params.append(param)


## Test Roslaunch XML parser
class TestXmlLoader(unittest.TestCase):

    def _load(self, test_file):
        loader = roslaunch.xmlloader.XmlLoader()
        mock = RosLaunchMock()
        self.assert_(os.path.exists(test_file), "cannot locate test file %s"%test_file)
        loader.load(test_file, mock)
        return mock
        
    def _load_valid_nodes(self, tests):
        mock = self._load('test/xml/test-node-valid.xml')
        nodes = [n for n in mock.nodes if n.type in tests]
        self.assertEquals(len(tests), len(nodes))
        return nodes
    
    def _load_valid_machines(self, tests):
        mock = self._load('test/xml/test-machine-valid.xml')        
        machines = [m for m in mock.machines if m.name in tests]
        self.assertEquals(len(tests), len(machines))
        return machines

    def test_params_invalid(self):
        tests = ['test-params-invalid-%s.xml'%i for i in range(1, 6)]
        loader = roslaunch.xmlloader.XmlLoader()
        for filename in tests:
            filename = os.path.join('test', 'xml', filename)
            try:
                self.assert_(os.path.exists(filename))
                loader.load(filename, RosLaunchMock())
                self.fail("xmlloader did not throw an xmlparseexception for [%s]"%filename)
            except roslaunch.xmlloader.XmlParseException, e:
                pass
            except roslaunch.xmlloader.XmlLoadException, e:
                pass

    def test_params(self):
        mock = self._load('test/xml/test-params-valid.xml')
        p = [p for p in mock.params if p.key == '/somestring1'][0]
        self.assertEquals('bar2', p.value)
        p = [p for p in mock.params if p.key == '/somestring2'][0]
        self.assertEquals('10', p.value)
        p = [p for p in mock.params if p.key == '/someinteger1'][0]
        self.assertEquals(1, p.value)
        p = [p for p in mock.params if p.key == '/someinteger2'][0]
        self.assertEquals(2, p.value)
        p = [p for p in mock.params if p.key == '/somefloat1'][0]
        self.assertAlmostEquals(3.14159, p.value, 2)
        p = [p for p in mock.params if p.key == '/somefloat2'][0]
        self.assertAlmostEquals(5.0, p.value, 1)
        p = [p for p in mock.params if p.key == '/wg/wgchildparam'][0]
        self.assertEquals("a child namespace parameter 1", p.value, 1)
        p = [p for p in mock.params if p.key == '/wg2/wg2childparam1'][0]
        self.assertEquals("a child namespace parameter 2", p.value, 1)
        p = [p for p in mock.params if p.key == '/wg2/wg2childparam2'][0]
        self.assertEquals("a child namespace parameter 3", p.value, 1)

        import xmlrpclib
        from roslib.packages import get_pkg_dir
        f = open(os.path.join(get_pkg_dir('roslaunch'), 'example.launch'))
        try:
            contents = f.read()
        finally:
            f.close()
        p = [p for p in mock.params if p.key == '/configfile'][0]
        self.assertEquals(contents, p.value, 1)
        p = [p for p in mock.params if p.key == '/binaryfile'][0]
        self.assertEquals(xmlrpclib.Binary(contents), p.value, 1)

        f = open(os.path.join(get_pkg_dir('rospy'), 'scripts', 'python-reserved-words.txt'))
        try:
            contents = f.read()
        finally:
            f.close()
        p = [p for p in mock.params if p.key == '/commandoutput'][0]
        self.assertEquals(contents, p.value, 1)
        
        
    def test_rosparam_valid(self):
        mock = self._load('test/xml/test-rosparam-valid.xml')        
        exes = [e for e in mock.executables if e.command == 'rosparam']
        self.assertEquals(len(exes), 4, "expected 4 rosparam exes")
        from roslaunch import PHASE_SETUP
        for e in exes:
            self.assertEquals(PHASE_SETUP, e.phase)
            args = e.args
            self.assertEquals(3, len(args), "expected 3 args, got %s"%str(args))
            rp_cmd, rp_file, rp_ctx = args
            self.failIf('$(find' in rp_file, "file attribute was not evaluated")
            if rp_file.endswith('example2.yaml'):
                self.assertEquals('dump', rp_cmd)
            else:
                self.assertEquals('load', rp_cmd, "%s should have been 'load'"%rp_file)
                
            # verify that the context is passed in correctly
            if rp_file.endswith('example1.yaml') or rp_file.endswith('example2.yaml'):
                self.assertEquals('/', rp_ctx)
            elif rp_file.endswith('example3.yaml'):
                self.assertEquals('/rosparam/', rp_ctx)
            elif rp_file.endswith('example4.yaml'):
                self.assertEquals('/node_rosparam/', rp_ctx)
                    
    def test_rosparam_invalid(self):
        tests = ['test-rosparam-invalid-%s.xml'%i for i in range(1, 5)]
        loader = roslaunch.xmlloader.XmlLoader()
        for filename in tests:
            filename = os.path.join('test', 'xml', filename)
            try:
                self.assert_(os.path.exists(filename))
                loader.load(filename, RosLaunchMock())
                self.fail("xmlloader did not throw an xmlparseexception for [%s]"%filename)
            except roslaunch.xmlloader.XmlParseException, e:
                pass
        
    def test_node_valid(self):
        nodes = self._load_valid_nodes([])
        
    def test_node_param(self):
        mock = self._load('test/xml/test-node-valid.xml')
        p = [p for p in mock.params if p.key == '/test_param_name/foo'][0]
        self.assertEquals('bar', p.value)
        
    def test_respawn(self):
        tests = ["test_respawn_true", "test_respawn_TRUE",
                 "test_respawn_false", "test_respawn_FALSE",
                 "test_respawn_none",]
        respawn_nodes = self._load_valid_nodes(tests)
        self.assertEquals(len(tests), len(respawn_nodes))
        for n in respawn_nodes:
            if n.type in ['test_respawn_true', 'test_respawn_TRUE']:
                self.assertEquals(True, n.respawn, "respawn for [%s] should be True"%n.type)
            else:
                self.assertEquals(False, n.respawn, "respawn for [%s] should be False"%n.type)

    def test_clear_params(self):
        true_tests = ["/test_clear_params1/","/test_clear_params2/",
                      "/clear_params_ns/test_clear_params_ns/",
                      "/group_test/","/embed_group_test/embedded_group/",
                      "/include_test/",
                      ]
        mock = self._load('test/xml/test-clear-params.xml')
        self.assertEquals(len(true_tests), len(mock.clear_params), "clear params did not match expected true: %s"%(str(mock.clear_params)))
        for t in true_tests:
            self.assert_(t in mock.clear_params, "%s was not marked for clear: %s"%(t, mock.clear_params))
                
    def test_clear_params_invalid(self):
        tests = ['test-clear-params-invalid-1.xml', 'test-clear-params-invalid-2.xml',
                 'test-clear-params-invalid-3.xml','test-clear-params-invalid-4.xml',]
        loader = roslaunch.xmlloader.XmlLoader()
        for filename in tests:
            filename = os.path.join('test', 'xml', filename)
            try:
                self.assert_(os.path.exists(filename))
                loader.load(filename, RosLaunchMock())
                self.fail("xmlloader did not throw an xmlparseexception for [%s]"%filename)
            except roslaunch.xmlloader.XmlParseException, e:
                pass

    def test_node_base(self):
        nodes = self._load_valid_nodes(['test_base'])
        node = nodes[0]
        self.assertEquals("package", node.package)
        self.assertEquals("test_base", node.type)        

    def test_node_args(self):
        nodes = self._load_valid_nodes(['test_args', 'test_args_empty'])
        for n in nodes:
            if n.type == 'test_args':
                self.assertEquals("args test", n.args)
            elif n.type == 'test_args_empty':
                self.assertEquals("", n.args)                

    def test_node_cwd(self):
        nodes = self._load_valid_nodes(['test_base', 'test_cwd_1', 'test_cwd_2'])
        for n in nodes:
            if n.type == 'test_base':
                self.assertEquals(None, n.cwd)
            elif n.type == 'test_cwd_1':
                self.assertEquals("ros-root", n.cwd)                
            elif n.type == 'test_cwd_2':
                self.assertEquals("node", n.cwd)  

    def test_node_output(self):
        nodes = self._load_valid_nodes(['test_output_log', 'test_output_screen'])
        for n in nodes:
            if n.type == 'test_output_log':
                self.assertEquals("log", n.output)
            elif n.type == 'test_output_screen':
                self.assertEquals("screen", n.output) 


    def test_node_machine(self):
        nodes = self._load_valid_nodes(['test_machine'])
        node = nodes[0]
        self.assertEquals("machine_test", node.machine_name)

    def test_node_ns(self):
        nodes = self._load_valid_nodes(['test_ns1', 'test_ns2','test_ns3'])
        for n in nodes:
            if n.type == 'test_ns1':
                self.assertEquals("/ns_test1/", n.namespace)
            elif n.type == 'test_ns2':
                self.assertEquals("/ns_test2/child2/", n.namespace) 
            elif n.type == 'test_ns3':
                self.assertEquals("/ns_test3/child3/", n.namespace) 

    def test_machines(self):
        tests = ['test-machine-invalid.xml']
        loader = roslaunch.xmlloader.XmlLoader()
        for filename in tests:
            filename = os.path.join('test', 'xml', filename)
            try:
                self.assert_(os.path.exists(filename))
                loader.load(filename, RosLaunchMock())
                self.fail("xmlloader did not throw an xmlparseexception for [%s]"%filename)
            except roslaunch.xmlloader.XmlParseException, e:
                pass


        old_rr = os.environ['ROS_ROOT']
        old_rpp = os.environ.get('ROS_PACKAGE_PATH', None)
        try:
            os.environ['ROS_ROOT'] = '/ros/root/tm'
            os.environ['ROS_PACKAGE_PATH'] = '/ros/package/path/tm'        

            machines = self._load_valid_machines(['machine1', 'machine2', 'machine3'])
            for m in machines:
                if m.name == 'machine1':
                    self.assertEquals(m.address, 'address1')
                    self.failIf(m.ros_ip, "ros ip should not be set")
                    self.assertEquals(m.ros_root, os.environ['ROS_ROOT'])
                    self.assertEquals(m.ros_package_path, os.environ['ROS_PACKAGE_PATH'])
                elif m.name == 'machine2':
                    self.assertEquals(m.address, 'address2')
                    self.assertEquals(m.ros_root, '/ros/root')
                    self.assertEquals(m.ros_package_path, '/ros/package/path')
                    self.assertEquals(m.ros_ip, 'hostname')
                elif m.name == 'machine3':
                    self.assertEquals(m.address, 'address3')
                    self.assertEquals(m.ros_ip, "hostname")
                    # should default to environment if not set
                    self.assertEquals(m.ros_root, os.environ['ROS_ROOT'])
                    self.assertEquals(m.ros_package_path, os.environ['ROS_PACKAGE_PATH'])
        finally:
            os.environ['ROS_ROOT'] = old_rr
            if old_rpp is not None:
                os.environ['ROS_PACKAGE_PATH'] = old_rpp
            else:
                del os.environ['ROS_PACKAGE_PATH']
                
    def test_node_subst(self):
        test_file ='test/xml/test-node-substitution.xml'
        keys = ['PACKAGE', 'TYPE', 'OUTPUT', 'RESPAWN']
        for k in keys:
            if k in os.environ:
                del os.environ[k]
        import random
        r = random.randint(0, 100000)
        if r%2:
            output = 'screen'
            respawn = 'true' 
        else:
            output = 'log'
            respawn = 'false'
        # append all but one required key and make sure we fail
        for k in keys[:-1]:
            if k in ['PACKAGE', 'TYPE']:
                os.environ[k] = "%s-%s"%(k.lower(), r)
            elif k == 'OUTPUT':
                os.environ['OUTPUT'] = output
            try:
                mock = self._load(test_file)
                self.fail("xml loader should have thrown an exception due to missing environment var")
            except roslaunch.xmlloader.XmlParseException, e:
                pass

        # load the last required env var
        os.environ['RESPAWN'] = respawn
        mock = self._load(test_file)
        self.assertEquals(1, len(mock.nodes), "should only be one test node")
        n = mock.nodes[0]
        self.assertEquals(n.package, 'package-%s'%r)
        self.assertEquals(n.type, 'type-%s'%r)
        self.assertEquals(n.output, output)
        if respawn == 'true':
            self.assert_(n.respawn)
        else:
            self.failIf(n.respawn)            

    def test_machine_subst(self):
        test_file ='test/xml/test-machine-substitution.xml'
        old_rr = os.environ['ROS_ROOT']
        old_rpp = os.environ.get('ROS_PACKAGE_PATH', None)

        try:
            keys = ['NAME', 'ADDRESS', 'ROS_HOST_NAME', 'ROS_ROOT', 'ROS_PACKAGE_PATH']        
            for k in keys:
                if k in os.environ:
                    del os.environ[k]
            import random
            r = random.randint(0, 100000)
            # append all but one required key and make sure we fail
            for k in keys[:-1]:
                os.environ[k] = "%s-%s"%(k.lower(), r)
                try:
                    mock = self._load(test_file)
                    self.fail("xml loader should have thrown an exception due to missing environment var")
                except roslaunch.xmlloader.XmlParseException, e:
                    pass

            # load the last required env var
            os.environ['ROS_PACKAGE_PATH'] = '/ros/package/path-%s'%r
            mock = self._load(test_file)
            self.assertEquals(1, len(mock.machines), "should only be one test machine")
            m = mock.machines[0]
            self.assertEquals(m.name, 'name-%s'%r)
            self.assertEquals(m.address, 'address-%s'%r)        
            self.assertEquals(m.ros_root, 'ros_root-%s'%r)
            self.assertEquals(m.ros_package_path, '/ros/package/path-%s'%r)
            self.assertEquals(m.ros_ip, 'ros_host_name-%s'%r)
        finally:
            os.environ['ROS_ROOT'] = old_rr
            if old_rpp is not None:
                os.environ['ROS_PACKAGE_PATH'] = old_rpp
            else:
                del os.environ['ROS_PACKAGE_PATH']

    
    def test_master(self):
        from roslaunch import Master
        old_env = os.environ.get('ROS_MASTER_URI', None)
        try:
            master_uri = 'http://foo:789'
            os.environ['ROS_MASTER_URI'] = master_uri
            
            tests = ['test-master-1.xml','test-master-2.xml',
                     'test-master-3.xml','test-master-4.xml',
                     'test-master-5.xml',        
                     ]
            for x in xrange(1, 6):
                loader = roslaunch.xmlloader.XmlLoader()
                for filename in tests:
                    filename = os.path.join('test', 'xml', 'test-master-%s.xml'%x)
                    self.assert_(os.path.exists(filename))
                    mock = RosLaunchMock()
                    loader.load(filename, mock)
                    if x == 1:
                        self.assertEquals(Master.AUTO_START, mock.master.auto)
                        self.assertEquals(master_uri, mock.master.uri)                        
                    elif x == 2:
                        self.assertEquals(Master.AUTO_RESTART, mock.master.auto)
                        self.assertEquals(master_uri, mock.master.uri)                        
                    elif x == 3:
                        self.assertEquals(Master.AUTO_NO, mock.master.auto)
                        self.assertEquals(master_uri, mock.master.uri)                                                
                    elif x == 4:
                        self.assertEquals(Master.AUTO_NO, mock.master.auto)
                        self.assertEquals(master_uri, mock.master.uri)                                                
                    elif x == 5:
                        self.assertEquals(Master.AUTO_NO, mock.master.auto)
                        host, port = roslib.network.parse_http_host_and_port(mock.master.uri)
                        self.assertEquals(12345, port)
                        # should have been remapped to machine name
                        self.assertNotEquals(host, 'localhost')

            tests = ['test-master-invalid-1.xml','test-master-invalid-2.xml']
            loader = roslaunch.xmlloader.XmlLoader()
            for filename in tests:
                filename = os.path.join('test', 'xml', filename)
                try:
                    self.assert_(os.path.exists(filename))
                    loader.load(filename, RosLaunchMock())
                    self.fail("xmlloader did not throw an xmlparseexception for [%s]"%filename)
                except roslaunch.xmlloader.XmlParseException, e:
                    pass
        finally:
            if old_env is None:
                del os.environ['ROS_MASTER_URI']
            else:
                os.environ['ROS_MASTER_URI'] = old_env
            
                 
    def test_env(self):
        nodes = self._load_valid_nodes(['test_env', 'test_env_empty'])
        for n in nodes:
            if n.type == 'test_env':
                self.assert_(("env1", "env1 value1") in n.env_args)
                self.assert_(("env2", "env2 value2") in n.env_args)
                self.assertEquals(2, len(n.env_args))
            elif n.type == 'test_env_empty':
                self.assert_(("env1", "") in n.env_args)

    def test_node_invalid(self):
        tests = ['test-node-invalid-type.xml','test-node-invalid-type-2.xml',
                 'test-node-invalid-pkg.xml','test-node-invalid-pkg-2.xml',
                 'test-node-invalid-name-1.xml',
                 'test-node-invalid-machine.xml',
                 'test-node-invalid-respawn.xml',
                 'test-node-invalid-ns.xml','test-node-invalid-ns-2.xml',                 
                 'test-node-invalid-env-name.xml','test-node-invalid-env-name-2.xml',
                 'test-node-invalid-env-value.xml',
                 'test-node-invalid-output.xml',
                 'test-node-invalid-cwd.xml',                 
                 ]
        loader = roslaunch.xmlloader.XmlLoader()
        for filename in tests:
            filename = os.path.join('test', 'xml', filename)
            try:
                self.assert_(os.path.exists(filename))
                loader.load(filename, RosLaunchMock())
                self.fail("xmlloader did not throw an xmlparseexception for [%s]"%filename)
            except roslaunch.xmlloader.XmlParseException, e:
                pass
        
if __name__ == '__main__':
    rostest.unitrun('test_roslaunch', sys.argv[0], TestXmlLoader, coverage_packages=['roslaunch.xmlloader'])
    
