'''[zhang@gator2 examples]$ more s-util.py'''
#!/usr/bin/python

"""
scalableutil.py

This file defines some utility functions for testing S-Mininet

Contributor: Ying Zhang
"""

from mininet.node import Node, Host, OVSSwitch, Controller
from mininet.link import Link, Intf
from mininet.net import Mininet
from mininet.topo import LinearTopo
from mininet.topolib import TreeTopo
from mininet.util import quietRun, makeIntfPair, errRun, retry
from mininet.scalablemininet.scalablecli import CLI
from mininet.log import setLogLevel, debug, info, error

from mininet.scalablemininet.scalablenode import RemoteHost
from mininet.scalablemininet.scalablenode import RemoteOVSSwitch
from mininet.scalablemininet.scalablenet import MininetCluster
from mininet.scalablemininet.scalabletopo.py import Placer

remoteHosts = [ 'h2' ]
remoteSwitches = [ 's2' ]
remoteServer = 'ubuntu2'

"""
Define example placement for switches, hosts
"""

def HostPlacer( name, *args, **params ):
    "Custom Host() constructor which places hosts on servers"
    if name in remoteHosts:
        return RemoteHost( name, *args, server=remoteServer, **params )
    else:
        return Host( name, *args, **params )

def SwitchPlacer( name, *args, **params ):
    "Custom Switch() constructor which places switches on servers"
    if name in remoteSwitches:
        return RemoteOVSSwitch( name, *args, server=remoteServer, **params )
    else:
        return RemoteOVSSwitch( name, *args, **params )

"""
Define controller
"""

def ClusterController( *args, **kwargs):
    "Custom Controller() constructor which updates its eth0 IP address"
    controller = Controller( *args, **kwargs )
    # Find out its IP address so that cluster switches can connect
    Intf( 'eth0', node=controller ).updateIP()
    return controller

"""
Test the topology
"""

def testRemoteTopo():
    "Test remote Node classes using Mininet()/Topo() API"
    topo = LinearTopo( 2 )
    net = Mininet( topo=topo, host=HostPlacer, switch=SwitchPlacer,
                  link=RemoteLink, controller=ClusterController )
    net.start()
    net.pingAll()
    net.stop()

"""
Test case for cross-server hosts and switches
"""

def testRemoteSwitches():
    "Test with local hosts and remote switches"
    servers = [ 'localhost', 'ubuntu2']
    topo = TreeTopo( depth=4, fanout=2 )
    net = MininetCluster( topo=topo, servers=servers,
                          placement=RoundRobinPlacer )
    net.start()
    net.pingAll()
    net.stop()

"""
Test S-Mininet cluster
"""

def testMininetCluster():
    "Test MininetCluster()"
    servers = [ 'localhost', 'ubuntu2' ]
    topo = TreeTopo( depth=3, fanout=3 )
    net = MininetCluster( topo=topo, servers=servers,
                          placement=SwitchBinPlacer )
    net.start()
    net.pingAll()
    net.stop()

def signalTest():
    "Make sure hosts are robust to signals"
    h = RemoteHost( 'h0', server='ubuntu1' )
    h.shell.send_signal( SIGINT )
    h.shell.poll()
    if h.shell.returncode is None:
        print 'OK: ', h, 'has not exited'
    else:
        print 'FAILURE:', h, 'exited with code', h.shell.returncode
    h.stop()

if __name__ == '__main__':
    setLogLevel( 'info' )
    # testRemoteTopo()
    # testRemoteNet()
    # testMininetCluster()
    # testRemoteSwitches()
    signalTest()
