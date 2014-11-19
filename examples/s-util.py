[zhang@gator2 examples]$ more s-util.py
#!/usr/bin/python

"""
s-util.py
test program with clustering mode
"""

m mininet.node import Node, Host, OVSSwitch, Controller
from mininet.link import Link, Intf
from mininet.net import Mininet
from mininet.topo import LinearTopo
from mininet.topolib import TreeTopo
from mininet.util import quietRun, makeIntfPair, errRun, retry
from mininet.examples.clustercli import CLI
from mininet.log import setLogLevel, debug, info, error

from mininet.examples.cluster import RemoteHost
from mininet.examples.cluster import RemoteOVSSwitch

remoteHosts = [ 'h2' ]
remoteSwitches = [ 's2' ]
remoteServer = 'ubuntu2'

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

def ClusterController( *args, **kwargs):
    "Custom Controller() constructor which updates its eth0 IP address"
    controller = Controller( *args, **kwargs )
    # Find out its IP address so that cluster switches can connect
    Intf( 'eth0', node=controller ).updateIP()
    return controller

def testRemoteTopo():
    "Test remote Node classes using Mininet()/Topo() API"
    topo = LinearTopo( 2 )
    net = Mininet( topo=topo, host=HostPlacer, switch=SwitchPlacer,
                  link=RemoteLink, controller=ClusterController )
    net.start()
    net.pingAll()
    net.stop()

# Need to test backwards placement, where each host is on
# a server other than its switch!! But seriously we could just
# do random switch placement rather than completely random
# host placement.

def testRemoteSwitches():
    "Test with local hosts and remote switches"
    servers = [ 'localhost', 'ubuntu2']
    topo = TreeTopo( depth=4, fanout=2 )
    net = MininetCluster( topo=topo, servers=servers,
                          placement=RoundRobinPlacer )
    net.start()
    net.pingAll()
    net.stop()


#
# For testing and demo purposes it would be nice to draw the
# network graph and color it based on server.

# The MininetCluster() class integrates pluggable placement
# functions, for maximum ease of use. MininetCluster() also
# pre-flights and multiplexes server connections.

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
