from mininet.node import Node, Host, OVSSwitch, Controller
from mininet.link import Link, Intf
from mininet.net import Mininet
from mininet.topo import LinearTopo
from mininet.topolib import TreeTopo
from mininet.util import quietRun, makeIntfPair, errRun, retry
from mininet.examples.clustercli import CLI
from mininet.log import setLogLevel, debug, info, error

from signal import signal, SIGINT, SIG_IGN
from subprocess import Popen, PIPE, STDOUT
import os
from random import randrange
from sys import exit
import re




class RemoteLink( Link ):

    "A RemoteLink is a link between nodes which may be on different servers"

    def __init__( self, node1, node2, **kwargs ):
        """Initialize a RemoteLink
           see Link() for parameters"""
        # Create links on remote node
        self.node1 = node1
        self.node2 = node2
        self.tunnel = None
        kwargs.setdefault( 'params1', {} )
        kwargs.setdefault( 'params2', {} )
        Link.__init__( self, node1, node2, **kwargs )

    def stop( self ):
        "Stop this link"
        if self.tunnel:
            self.tunnel.terminate()
        self.tunnel = None

    def makeIntfPair( self, intfname1, intfname2, addr1=None, addr2=None ):
        """Create pair of interfaces
            intfname1: name of interface 1
            intfname2: name of interface 2
            (override this method [and possibly delete()]
            to change link type)"""
        node1, node2 = self.node1, self.node2
        server1 = getattr( node1, 'server', 'localhost' )
        server2 = getattr( node2, 'server', 'localhost' )
        if server1 == 'localhost' and server2 == 'localhost':
            # Local link
            return makeIntfPair( intfname1, intfname2, addr1, addr2 )
        elif server1 == server2:
            # Remote link on same remote server
            return makeIntfPair( intfname1, intfname2, addr1, addr2,
                                 run=node1.rcmd )
        # Otherwise, make a tunnel
        self.tunnel = self.makeTunnel( node1, node2, intfname1, intfname2, addr1, addr2 )
        return self.tunnel

    @staticmethod
    def moveIntf( intf, node, printError=True ):
        """Move remote interface from root ns to node
            intf: string, interface
            dstNode: destination Node
            srcNode: source Node or None (default) for root ns
            printError: if true, print error"""
        intf = str( intf )
        cmd = 'ip link set %s netns %s' % ( intf, node.pid )
        node.rcmd( cmd )
        links = node.cmd( 'ip link show' )
        if not ( ' %s:' % intf ) in links:
            if printError:
                error( '*** Error: RemoteLink.moveIntf: ' + intf +
                      ' not successfully moved to ' + node.name + '\n' )
            return False
        return True

    def makeTunnel( self, node1, node2, intfname1, intfname2,
                    addr1=None, addr2=None ):
        "Make a tunnel across switches on different servers"
        # We should never try to create a tunnel to ourselves!
        assert node1.server != 'localhost' or node2.server != 'localhost'
        # And we can't ssh into this server remotely as 'localhost',
        # so try again swappping node1 and node2
        if node2.server == 'localhost':
            return self.makeTunnel( node2, node1, intfname2, intfname1,
                                    addr2, addr1 )
        # 1. Create tap interfaces
        for node in node1, node2:
            # For now we are hard-wiring tap9, which we will rename
            node.rcmd( 'ip link delete tap9', stderr=PIPE )
            cmd = 'ip tuntap add dev tap9 mode tap user ' + node.user
            node.rcmd( cmd )
            links = node.rcmd( 'ip link show' )
            # print 'after add, links =', links
            assert 'tap9' in links
        # 2. Create ssh tunnel between tap interfaces
        # -n: close stdin
        dest = '%s@%s' % ( node2.user, node2.serverIP )
        cmd = [ 'ssh', '-n', '-o', 'Tunnel=Ethernet', '-w', '9:9',
                dest, 'echo @' ]
        self.cmd = cmd
        tunnel = node1.rpopen( cmd, sudo=False )
        # When we receive the character '@', it means that our
        # tunnel should be set up
        debug( 'Waiting for tunnel to come up...\n' )
        ch = tunnel.stdout.read( 1 )
        if ch != '@':
            error( 'makeTunnel:\n',
                   'Tunnel setup failed for',
                   '%s:%s' % ( node1, node1.dest ), 'to',
                   '%s:%s\n' % ( node2, node2.dest ),
                  'command was:', cmd, '\n' )
            tunnel.terminate()
            tunnel.wait()
            error( ch + tunnel.stdout.read() )
            error( tunnel.stderr.read() )
            exit( 1 )
        # 3. Move interfaces if necessary
        for node in node1, node2:
            if node.inNamespace:
                retry( 3, .01, RemoteLink.moveIntf, 'tap9', node )
        # 4. Rename tap interfaces to desired names
        for node, intf, addr in ( ( node1, intfname1, addr1 ),
                            ( node2, intfname2, addr2 ) ):
            if not addr:
                node.cmd( 'ip link set tap9 name', intf )
            else:
                node.cmd( 'ip link set tap9 name', intf, 'address', addr )
        for node, intf in ( ( node1, intfname1 ), ( node2, intfname2 ) ):
            assert intf in node.cmd( 'ip link show' )
        return tunnel

    def status( self ):
        "Detailed representation of link"
        if self.tunnel:
            if self.tunnel.poll() is not None:
                status = "Tunnel EXITED %s" % self.tunnel.returncode
            else:
                status = "Tunnel Running (%s: %s)" % (
                    self.tunnel.pid, self.cmd )
        else:
            status = "OK"
        result = "%s %s" % ( Link.status( self ), status )
        return result