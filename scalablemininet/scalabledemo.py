#!/usr/bin/python
"clusterdemo.py: demo of Mininet Cluster Edition prototype"

from mininet.scalablemininet.scalablemininet import MininetCluster
from mininet.scalablemininet.scalabletopo import SwitchBinPlacer
from mininet.topolib import TreeTopo
from mininet.log import setLogLevel
from mininet.scalablemininet.scalablecli import DemoCLI as CLI

def demo():
    "Simple Demo of Cluster Mode"
    servers = [ 'localhost', '192.168.94.129' ]
    topo = TreeTopo( depth=3, fanout=3 )
    net = MininetCluster( topo=topo, servers=servers,
                          placement=SwitchBinPlacer )
    net.start()
    CLI( net )
    net.stop()

if __name__ == '__main__':
    setLogLevel( 'info' )
    demo()

